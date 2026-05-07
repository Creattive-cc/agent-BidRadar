import time
from datetime import date, timedelta
from typing import Any

import requests  # type: ignore[import-untyped]

from agent.config import settings
from agent.logging_utils import get_logger
from agent.schemas import ScrapedBid

logger = get_logger("bidradar.scraper.pncp")

# Documentacao PNCP: /contratacoes/publicacao exige dataInicial, dataFinal e codigoModalidadeContratacao.
PNCP_PUBLICACAO_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

DEFAULT_HEADERS = {
    "User-Agent": "BidRadar/0.1 (+local-agent)",
    "Accept": "application/json",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


def _log_http_error(response: requests.Response, params: dict[str, Any], url: str) -> None:
    body = (response.text or "")[:800].replace("\n", " ")
    logger.warning(
        "PNCP HTTP %s url=%s params=%s body_snippet=%s",
        response.status_code,
        url,
        params,
        body,
    )


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


def _fetch_pncp_json(url: str, params: dict[str, Any]) -> dict[str, Any] | None:
    for attempt in range(2):
        try:
            response = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=35)
            if response.status_code == 502 and attempt == 0:
                time.sleep(1.0)
                continue
            if not response.ok:
                _log_http_error(response, params, url)
                return None
            return response.json()
        except requests.RequestException as exc:
            if attempt == 0:
                time.sleep(0.5)
                continue
            logger.warning("PNCP request falhou url=%s params=%s err=%s", url, params, exc)
            return None
    return None


def _item_key(item: dict[str, Any]) -> str:
    return str(
        item.get("numeroControlePNCP")
        or item.get("numeroCompra")
        or item.get("linkSistemaOrigem")
        or item.get("linkProcessoEletronico")
        or item.get("id")
        or hash(str(item))
    )


def scrape_comprasnet() -> list[ScrapedBid]:
    start = time.perf_counter()
    end = date.today()
    start_d = end - timedelta(days=30)

    data_inicial = start_d.isoformat()
    data_final = end.isoformat()
    modalidades = _parse_modalidades()

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    for codigo in modalidades:
        params: dict[str, Any] = {
            "pagina": 1,
            "tamanhoPagina": 20,
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "codigoModalidadeContratacao": codigo,
        }
        payload = _fetch_pncp_json(PNCP_PUBLICACAO_URL, params)
        if not payload:
            continue
        found = _items_from_payload(payload)
        if not found:
            continue
        for item in found:
            if not isinstance(item, dict):
                continue
            key = _item_key(item)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
        logger.info(
            "PNCP ok modalidade=%s itens_lote=%s acumulado=%s",
            codigo,
            len(found),
            len(merged),
        )

    bids: list[ScrapedBid] = []
    for item in merged:
        title = item.get("objetoCompra") or item.get("descricao") or item.get("objeto") or "Licitacao sem titulo"
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
        if not url and item.get("numeroControlePNCP"):
            url = f"https://pncp.gov.br/app/editais/{item['numeroControlePNCP']}"

        if not url:
            continue

        bids.append(
            ScrapedBid(
                title=str(title)[:500],
                agency=str(agency)[:255],
                estimated_value=item.get("valorTotalEstimado") or item.get("valorTotal"),
                deadline=item.get("dataEncerramentoProposta")
                or item.get("dataAberturaProposta")
                or item.get("dataPublicacaoPncp"),
                url=url,
                source_site="ComprasNet/PNCP",
                find_time_seconds=0.0,
            )
        )

    elapsed = time.perf_counter() - start
    for bid in bids:
        bid.find_time_seconds = elapsed

    if not bids:
        logger.warning(
            "PNCP: nenhum item. Verifique dataInicial/dataFinal e codigoModalidadeContratacao "
            "(variavel BIDRADAR_PNCP_MODALIDADES). Modalidades testadas: %s",
            modalidades,
        )

    return bids
