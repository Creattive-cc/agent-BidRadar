"""Scraper PNCP com paginação completa, rate limiting, BigQuery, Pub/Sub e Firestore."""

import json
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests  # type: ignore[import-untyped]

from agent.config import settings
from agent.logging_utils import get_logger
from agent.schemas import ScrapedBid

logger = get_logger("bidradar.scraper.pncp")

PNCP_PUBLICACAO_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
_PAGE_SIZE = 50  # máximo aceito na prática pela API PNCP (documentação diz 500 mas rejeita)
_INTER_PAGE_DELAY = 0.4  # segundos entre requisicoes de pagina
_INTER_MODALIDADE_DELAY = 1.0  # segundos entre modalidades

DEFAULT_HEADERS = {
    "User-Agent": "BidRadar/0.1 (+local-agent)",
    "Accept": "application/json",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# ---------------------------------------------------------------------------
# Clientes GCP — inicializados sob demanda para nao quebrar importacoes
# ---------------------------------------------------------------------------

_bq_client: Any = None
_pubsub_client: Any = None
_firestore_client: Any = None


def _get_bq() -> Any:
    global _bq_client
    if _bq_client is None:
        from google.cloud import bigquery  # type: ignore[import-untyped]

        _bq_client = bigquery.Client(project=settings.gcp_project_id)
    return _bq_client


def _get_pubsub() -> Any:
    global _pubsub_client
    if _pubsub_client is None:
        from google.cloud.pubsub_v1 import (
            PublisherClient,  # type: ignore[import-untyped]
        )

        _pubsub_client = PublisherClient()
    return _pubsub_client


def _get_firestore() -> Any:
    global _firestore_client
    if _firestore_client is None:
        from google.cloud import firestore  # type: ignore[import-untyped]

        _firestore_client = firestore.Client(project=settings.gcp_project_id)
    return _firestore_client


# ---------------------------------------------------------------------------
# Firestore — leitura de filtros
# ---------------------------------------------------------------------------


def _load_filters() -> dict[str, Any]:
    try:
        fs = _get_firestore()
        doc = fs.document("config/filters").get()
        return doc.to_dict() or {} if doc.exists else {}
    except Exception as exc:
        exc_str = str(exc)
        # Erros de credencial local (JWT, oauth2) sao esperados fora do GCP — silencioso.
        if any(
            k in exc_str for k in ("JWT", "oauth2", "credentials", "UNAUTHENTICATED")
        ):
            logger.debug("Firestore indisponivel (credencial local): %s", exc_str[:120])
        else:
            logger.warning("Firestore config/filters indisponivel: %s", exc)
        return {}


def _apply_filters(
    items: list[dict[str, Any]], filters: dict[str, Any]
) -> list[dict[str, Any]]:
    valor_minimo: float = float(filters.get("valor_minimo") or 0)
    termos_exclusao: list[str] = [
        t.lower() for t in (filters.get("termos_exclusao") or [])
    ]
    excluir_me_epp: bool = bool(filters.get("excluir_me_epp", False))

    result = []
    for item in items:
        identifier = _item_key(item)

        # 1. Filtro de ME/EPP: descarta se for exclusivo para ME/EPP
        if excluir_me_epp and item.get("tipoBeneficioId") == 1:
            logger.debug("[FILTRO] edital exclusivo ME/EPP descartado: %s", identifier)
            continue

        # 2. Filtro de valor mínimo
        if valor_minimo:
            valor = item.get("valorTotalEstimado") or item.get("valorTotal") or 0
            if valor and float(valor) < valor_minimo:
                logger.debug(
                    "[FILTRO] valor abaixo do mínimo: %s (valor=%.2f, minimo=%.2f)",
                    identifier,
                    float(valor),
                    valor_minimo,
                )
                continue

        # 3. Filtro de termos de exclusão
        if termos_exclusao:
            objeto = (item.get("objetoCompra") or item.get("descricao") or "").lower()
            matched_term = next(
                (termo for termo in termos_exclusao if termo in objeto), None
            )
            if matched_term:
                logger.debug(
                    "[FILTRO] termo de exclusão '%s' encontrado: %s",
                    matched_term,
                    identifier,
                )
                continue

        result.append(item)
    return result


# ---------------------------------------------------------------------------
# BigQuery — deduplicacao e insercao
# ---------------------------------------------------------------------------


def _bq_full_table() -> str:
    return f"{settings.gcp_project_id}.{settings.bigquery_dataset}.{settings.bigquery_table}"


def _existing_numeros_bq(numeros: list[str]) -> set[str]:
    if not numeros:
        return set()
    try:
        from google.cloud import bigquery  # type: ignore[import-untyped]

        bq = _get_bq()
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("numeros", "STRING", numeros)
            ]
        )
        query = (
            f"SELECT numero FROM `{_bq_full_table()}` WHERE numero IN UNNEST(@numeros)"
        )
        rows = bq.query(query, job_config=job_config).result()
        return {row.numero for row in rows}
    except Exception as exc:
        logger.warning("BigQuery verificacao de duplicatas falhou: %s", exc)
        return set()


def _insert_bq(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    try:
        bq = _get_bq()
        errors = bq.insert_rows_json(_bq_full_table(), rows)
        if errors:
            logger.warning(
                "BigQuery insert retornou erros (primeiros 3): %s", errors[:3]
            )
        else:
            logger.info("BigQuery: %s editais inseridos.", len(rows))
    except Exception as exc:
        logger.warning("BigQuery insert falhou: %s", exc)


# ---------------------------------------------------------------------------
# Pub/Sub — publicacao por edital novo
# ---------------------------------------------------------------------------


def _pubsub_topic_path() -> str:
    return f"projects/{settings.gcp_project_id}/topics/{settings.pubsub_topic}"


def _publish_edital(edital_id: str, numero: str) -> None:
    try:
        ps = _get_pubsub()
        data = json.dumps({"edital_id": edital_id, "numero": numero}).encode("utf-8")
        future = ps.publish(_pubsub_topic_path(), data)
        future.result(timeout=10)
    except Exception as exc:
        logger.warning("Pub/Sub publish falhou edital_id=%s: %s", edital_id, exc)


# ---------------------------------------------------------------------------
# HTTP com retry exponencial
# ---------------------------------------------------------------------------


def _log_http_error(
    response: requests.Response, params: dict[str, Any], url: str
) -> None:
    body = (response.text or "")[:800].replace("\n", " ")
    logger.warning(
        "PNCP HTTP %s url=%s params=%s body_snippet=%s",
        response.status_code,
        url,
        params,
        body,
    )


def _fetch_pncp_json(
    url: str, params: dict[str, Any], max_attempts: int = 4
) -> dict[str, Any] | None:
    for attempt in range(max_attempts):
        try:
            resp = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=35)

            if resp.status_code == 429:
                wait = min(2 ** (attempt + 1) * 2, 60)
                logger.warning(
                    "PNCP rate limit (429) — aguardando %ss (tentativa %d)",
                    wait,
                    attempt + 1,
                )
                time.sleep(wait)
                continue

            if resp.status_code in (502, 503, 504):
                wait = 2**attempt
                if attempt < max_attempts - 1:
                    logger.warning(
                        "PNCP %s — retry em %ss (tentativa %d)",
                        resp.status_code,
                        wait,
                        attempt + 1,
                    )
                    time.sleep(wait)
                    continue

            if not resp.ok:
                _log_http_error(resp, params, url)
                return None

            return resp.json()

        except requests.RequestException as exc:
            wait = 2**attempt
            if attempt < max_attempts - 1:
                logger.warning(
                    "PNCP request erro (tentativa %d/%d): %s",
                    attempt + 1,
                    max_attempts,
                    exc,
                )
                time.sleep(wait)
                continue
            logger.warning(
                "PNCP request falhou definitivamente params=%s err=%s", params, exc
            )
            return None

    return None


# ---------------------------------------------------------------------------
# Extracao de itens e chave de dedup
# ---------------------------------------------------------------------------


def _items_from_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    raw = (
        payload.get("data")
        or payload.get("content")
        or payload.get("resultado")
        or payload.get("items")
        or []
    )
    if isinstance(raw, dict) and "content" in raw:
        raw = raw.get("content") or []
    return raw if isinstance(raw, list) else []


def _total_pages(payload: dict[str, Any]) -> int | None:
    return payload.get("totalPaginas") or payload.get("totalPages")


def _item_key(item: dict[str, Any]) -> str:
    return str(
        item.get("numeroControlePNCP")
        or item.get("numeroCompra")
        or item.get("linkSistemaOrigem")
        or item.get("linkProcessoEletronico")
        or item.get("id")
        or hash(str(item))
    )


def _parse_modalidades() -> list[int]:
    out: list[int] = []
    for part in settings.pncp_modalidades.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            logger.warning("Modalidade PNCP ignorada (nao numerica): %s", part)
    return out or [8, 1, 3, 6, 4, 2, 5, 7, 9, 10]


# ---------------------------------------------------------------------------
# Paginacao completa por modalidade
# ---------------------------------------------------------------------------


def _fetch_all_for_modalidade(
    codigo: int, data_inicial: str, data_final: str
) -> list[dict[str, Any]]:
    all_items: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    page = 1

    while True:
        params: dict[str, Any] = {
            "pagina": page,
            "tamanhoPagina": _PAGE_SIZE,
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "codigoModalidadeContratacao": codigo,
        }
        payload = _fetch_pncp_json(PNCP_PUBLICACAO_URL, params)
        if not payload:
            break

        items = _items_from_payload(payload)
        if not items:
            break

        for item in items:
            if not isinstance(item, dict):
                continue
            key = _item_key(item)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            all_items.append(item)

        total = _total_pages(payload)
        if total is not None and page >= total:
            break
        if len(items) < _PAGE_SIZE:
            break

        page += 1
        time.sleep(_INTER_PAGE_DELAY)

    return all_items


# ---------------------------------------------------------------------------
# Conversao de item PNCP → ScrapedBid + linha BigQuery
# ---------------------------------------------------------------------------


def _pncp_portal_url(numero_controle: str) -> str:
    """Constroi a URL do portal PNCP a partir do numeroControlePNCP."""
    try:
        # Ex: "05472936000139-1-000082/2026"
        parts = numero_controle.split("-")
        if len(parts) < 3:
            return ""

        cnpj = parts[0]
        seq_ano_part = parts[2]

        # Ex: "000082/2026"
        seq_ano_split = seq_ano_part.split("/")
        if len(seq_ano_split) < 2:
            return ""

        sequencial = int(seq_ano_split[0])
        ano = seq_ano_split[1]

        return f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}"
    except (ValueError, IndexError) as e:
        logger.warning("Formato PNCP URL invalido: %s. Erro: %s", numero_controle, e)
        return ""


def _parse_date_str(val: str | None) -> str | None:
    return val[:10] if val and len(val) >= 10 else None


def _parse_datetime_str(val: str | None) -> str | None:
    return val[:19] if val and len(val) >= 19 else None


def _build_bid_and_row(
    item: dict[str, Any], codigo: int
) -> tuple[ScrapedBid, dict[str, Any]] | None:
    title = (
        item.get("objetoCompra")
        or item.get("descricao")
        or item.get("objeto")
        or "Licitacao sem titulo"
    )
    orgao = item.get("orgaoEntidade") or {}
    agency = (
        (orgao.get("razaoSocial") if isinstance(orgao, dict) else None)
        or item.get("nomeOrgaoEntidade")
        or item.get("orgao")
        or "Orgao nao informado"
    )
    url = (
        item.get("linkSistemaOrigem")
        or item.get("linkProcessoEletronico")
        or item.get("linkCompra")
        or item.get("url")
        or ""
    )
    numero = str(
        item.get("numeroControlePNCP") or item.get("numeroCompra") or _item_key(item)
    )
    if not url and item.get("numeroControlePNCP"):
        url = _pncp_portal_url(item["numeroControlePNCP"])
    if not url:
        return None

    modalidade_nome = (
        item.get("modalidade") or item.get("nomeModalidade") or str(codigo)
    )
    estimated_value = item.get("valorTotalEstimado") or item.get("valorTotal")
    data_publicacao = _parse_date_str(item.get("dataPublicacaoPncp"))
    data_abertura = _parse_datetime_str(
        item.get("dataEncerramentoProposta") or item.get("dataAberturaProposta")
    )

    bid = ScrapedBid(
        title=str(title)[:500],
        agency=str(agency)[:255],
        estimated_value=estimated_value,
        deadline=item.get("dataEncerramentoProposta")
        or item.get("dataAberturaProposta"),
        url=url,
        source_site="ComprasNet/PNCP",
        find_time_seconds=0.0,
    )

    bq_row: dict[str, Any] = {
        "edital_id": str(uuid.uuid4()),
        "portal": "PNCP",
        "numero": numero,
        "orgao": str(agency)[:500],
        "modalidade": str(modalidade_nome)[:100],
        "objeto": str(title)[:2000],
        "valor_estimado": float(estimated_value)
        if estimated_value is not None
        else None,
        "data_publicacao": data_publicacao,
        "data_abertura": data_abertura,
        "status": "publicado",
        "gcs_path": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    return bid, bq_row


# ---------------------------------------------------------------------------
# Funcao principal
# ---------------------------------------------------------------------------


def scrape_pncp() -> list[ScrapedBid]:
    start = time.perf_counter()
    end_date = date.today()
    data_inicial = (end_date - timedelta(days=2)).strftime("%Y%m%d")
    data_final = end_date.strftime("%Y%m%d")

    modalidades = _parse_modalidades()
    filters = _load_filters()

    # Coleta paginada por modalidade
    all_items: list[dict[str, Any]] = []
    global_seen: set[str] = set()

    for idx, codigo in enumerate(modalidades):
        items = _fetch_all_for_modalidade(codigo, data_inicial, data_final)
        items = _apply_filters(items, filters)

        novos = 0
        for item in items:
            key = _item_key(item)
            if key in global_seen:
                continue
            global_seen.add(key)
            all_items.append(item)
            novos += 1

        logger.info(
            "PNCP modalidade=%s paginas_coletadas=%s itens_novos=%s total=%s",
            codigo,
            novos,
            novos,
            len(all_items),
        )
        if idx < len(modalidades) - 1:
            time.sleep(_INTER_MODALIDADE_DELAY)

    # Constroi ScrapedBids e linhas BigQuery em paralelo
    bids: list[ScrapedBid] = []
    bq_rows_by_numero: dict[str, tuple[ScrapedBid, dict[str, Any]]] = {}

    for item in all_items:
        result = _build_bid_and_row(
            item, codigo=int(item.get("codigoModalidadeContratacao", 0))
        )
        if result is None:
            continue
        bid, bq_row = result
        bids.append(bid)
        bq_rows_by_numero[bq_row["numero"]] = (bid, bq_row)

    # Verifica duplicatas no BigQuery
    existing = _existing_numeros_bq(list(bq_rows_by_numero.keys()))
    new_rows = [
        bq_row
        for numero, (_, bq_row) in bq_rows_by_numero.items()
        if numero not in existing
    ]

    # Persiste no BigQuery e publica no Pub/Sub
    _insert_bq(new_rows)
    for row in new_rows:
        _publish_edital(row["edital_id"], row["numero"])

    elapsed = time.perf_counter() - start
    for bid in bids:
        bid.find_time_seconds = elapsed

    logger.info(
        "PNCP concluido: coletados=%s novos_bq=%s tempo=%.1fs",
        len(bids),
        len(new_rows),
        elapsed,
    )
    if not bids:
        logger.warning(
            "PNCP: nenhum item retornado. Verifique dataInicial/dataFinal e "
            "BIDRADAR_PNCP_MODALIDADES. Modalidades testadas: %s",
            modalidades,
        )

    return bids


# Alias para retrocompatibilidade com runner.py e qualquer importacao direta
scrape_comprasnet = scrape_pncp
