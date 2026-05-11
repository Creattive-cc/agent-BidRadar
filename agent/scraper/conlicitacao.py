"""Scraper ConLicitação com Playwright, BigQuery, Pub/Sub e Firestore."""

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from agent.config import settings
from agent.logging_utils import get_logger
from agent.schemas import ScrapedBid

logger = get_logger("bidradar.scraper.conlicitacao")

CONLICITACAO_URL = "https://conlicitacao.com.br"
_PAGE_SIZE = 50  # Tamanho da pagina na interface do ConLicitação
_MAX_PAGES = 20  # Limite de paginas para evitar loops infinitos

# ---------------------------------------------------------------------------
# Clientes GCP e Secret Manager — inicializados sob demanda
# ---------------------------------------------------------------------------

_bq_client: Any = None
_pubsub_client: Any = None
_firestore_client: Any = None
_secret_manager_client: Any = None


def _get_bq() -> Any:
    global _bq_client
    if _bq_client is None:
        from google.cloud import bigquery

        _bq_client = bigquery.Client(project=settings.gcp_project_id)
    return _bq_client


def _get_pubsub() -> Any:
    global _pubsub_client
    if _pubsub_client is None:
        from google.cloud.pubsub_v1 import PublisherClient

        _pubsub_client = PublisherClient()
    return _pubsub_client


def _get_firestore() -> Any:
    global _firestore_client
    if _firestore_client is None:
        from google.cloud import firestore

        _firestore_client = firestore.Client(project=settings.gcp_project_id)
    return _firestore_client


def _get_secret_manager() -> Any:
    global _secret_manager_client
    if _secret_manager_client is None:
        from google.cloud import secretmanager

        _secret_manager_client = secretmanager.SecretManagerServiceClient()
    return _secret_manager_client


def _get_conlicitacao_credentials() -> dict[str, str]:
    """Busca credenciais do Secret Manager."""
    creds = {"user": "", "password": ""}
    try:
        sm = _get_secret_manager()
        project_id = settings.gcp_project_id
        user_secret_name = (
            f"projects/{project_id}/secrets/CONLICITACAO_USER/versions/latest"
        )
        pass_secret_name = (
            f"projects/{project_id}/secrets/CONLICITACAO_PASS/versions/latest"
        )

        user_response = sm.access_secret_version(request={"name": user_secret_name})
        creds["user"] = user_response.payload.data.decode("UTF-8")

        pass_response = sm.access_secret_version(request={"name": pass_secret_name})
        creds["password"] = pass_response.payload.data.decode("UTF-8")
    except Exception as exc:
        logger.error(
            "Falha ao buscar credenciais do ConLicitação no Secret Manager: %s", exc
        )
    return creds


# ---------------------------------------------------------------------------
# Lógica de persistência e filtros (reuso de pncp.py)
# ---------------------------------------------------------------------------


def _load_filters() -> dict[str, Any]:
    try:
        fs = _get_firestore()
        doc = fs.document("config/filters").get()
        return doc.to_dict() or {} if doc.exists else {}
    except Exception as exc:
        logger.warning("Firestore config/filters indisponivel: %s", exc)
        return {}


def _apply_filters(
    items: list[dict[str, Any]], filters: dict[str, Any]
) -> list[dict[str, Any]]:
    valor_minimo: float = float(filters.get("valor_minimo") or 0)
    termos_exclusao: list[str] = [
        t.lower() for t in (filters.get("termos_exclusao") or [])
    ]
    result = []
    for item in items:
        if (
            valor_minimo
            and item.get("valor_estimado")
            and item["valor_estimado"] < valor_minimo
        ):
            continue
        if termos_exclusao and any(
            termo in item.get("objeto", "").lower() for termo in termos_exclusao
        ):
            continue
        result.append(item)
    return result


def _bq_full_table() -> str:
    return f"{settings.gcp_project_id}.{settings.bigquery_dataset}.{settings.bigquery_table}"


def _existing_numeros_bq(numeros: list[str]) -> set[str]:
    if not numeros:
        return set()
    try:
        from google.cloud import bigquery

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
        errors = _get_bq().insert_rows_json(_bq_full_table(), rows)
        if errors:
            logger.warning("BigQuery insert retornou erros: %s", errors[:3])
        else:
            logger.info("BigQuery: %s editais inseridos.", len(rows))
    except Exception as exc:
        logger.warning("BigQuery insert falhou: %s", exc)


def _publish_edital(edital_id: str, numero: str) -> None:
    topic_path = f"projects/{settings.gcp_project_id}/topics/{settings.pubsub_topic}"
    try:
        data = json.dumps({"edital_id": edital_id, "numero": numero}).encode("utf-8")
        future = _get_pubsub().publish(topic_path, data)
        future.result(timeout=10)
    except Exception as exc:
        logger.warning("Pub/Sub publish falhou edital_id=%s: %s", edital_id, exc)


# ---------------------------------------------------------------------------
# Extração com Playwright
# ---------------------------------------------------------------------------


def _extract_bids_from_page(page: Page) -> list[dict[str, Any]]:
    items = []
    bids = page.locator("div.card-general-info").all()
    for bid_locator in bids:
        try:
            title = bid_locator.locator("p.card-title").inner_text()
            agency = bid_locator.locator("p.card-órgão").inner_text()
            modalidade = bid_locator.locator("div.modalidade > span").inner_text()
            url = CONLICITACAO_URL + bid_locator.locator(
                "a.btn-see-more"
            ).get_attribute("href")

            valor_str = bid_locator.locator("div.valor > span").inner_text()
            valor = (
                float(
                    valor_str.replace("R$", "")
                    .replace(".", "")
                    .replace(",", ".")
                    .strip()
                )
                if valor_str
                else None
            )

            data_pub_str = bid_locator.locator(
                "div.data-publicacao > span"
            ).inner_text()
            data_abertura_str = bid_locator.locator(
                "div.data-abertura > span"
            ).inner_text()

            items.append(
                {
                    "objeto": title,
                    "orgao": agency,
                    "modalidade": modalidade,
                    "url": url,
                    "numero": url.split("/")[-1],
                    "valor_estimado": valor,
                    "data_publicacao": datetime.strptime(
                        data_pub_str, "%d/%m/%Y"
                    ).strftime("%Y-%m-%d")
                    if data_pub_str
                    else None,
                    "data_abertura": datetime.strptime(
                        data_abertura_str, "%d/%m/%Y %H:%M"
                    ).strftime("%Y-%m-%dT%H:%M:%S")
                    if data_abertura_str
                    else None,
                }
            )
        except (PlaywrightTimeoutError, Exception) as exc:
            logger.warning("Erro ao extrair um item do ConLicitação: %s", exc)
    return items


def _build_bid_and_row(item: dict[str, Any]) -> tuple[ScrapedBid, dict[str, Any]]:
    bid = ScrapedBid(
        title=item["objeto"][:500],
        agency=item["orgao"][:255],
        estimated_value=item.get("valor_estimado"),
        deadline=item.get("data_abertura"),
        url=item["url"],
        source_site="ConLicitação",
        find_time_seconds=0.0,
    )
    bq_row = {
        "edital_id": str(uuid.uuid4()),
        "portal": "ConLicitação",
        "numero": item["numero"],
        "orgao": item["orgao"][:500],
        "modalidade": item["modalidade"][:100],
        "objeto": item["objeto"][:2000],
        "url": item["url"],
        "valor_estimado": item.get("valor_estimado"),
        "data_publicacao": item.get("data_publicacao"),
        "data_abertura": item.get("data_abertura"),
        "status": "publicado",
        "gcs_path": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return bid, bq_row


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------


def scrape_conlicitacao() -> list[ScrapedBid]:
    start = time.perf_counter()
    creds = _get_conlicitacao_credentials()
    if not creds.get("user") or not creds.get("password"):
        logger.error("Credenciais do ConLicitação não encontradas. Abortando scraper.")
        return []

    all_items = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            logger.info("Autenticando no ConLicitação...")
            page.goto(f"{CONLICITACAO_URL}/login", timeout=60000)
            page.fill('input[name="email"]', creds["user"])
            page.fill('input[name="password"]', creds["password"])
            page.click('button[type="submit"]')
            page.wait_for_url(f"{CONLICITACAO_URL}/licitacoes", timeout=60000)
            logger.info("Autenticação bem-sucedida.")

            for page_num in range(1, _MAX_PAGES + 1):
                logger.info("Coletando página %d...", page_num)
                page.wait_for_selector("div.card-general-info", timeout=30000)

                items_on_page = _extract_bids_from_page(page)
                if not items_on_page:
                    logger.info(
                        "Nenhum item encontrado na página %d. Finalizando coleta.",
                        page_num,
                    )
                    break
                all_items.extend(items_on_page)

                next_button = page.locator('a[rel="next"]')
                if not next_button.is_visible():
                    logger.info("Botão 'próximo' não encontrado. Fim da paginação.")
                    break

                next_button.click()
                page.wait_for_load_state("networkidle", timeout=30000)

        except PlaywrightTimeoutError as exc:
            logger.error("Timeout durante a navegação com Playwright: %s", exc)
        except Exception as exc:
            logger.exception("Erro inesperado no scraper ConLicitação: %s", exc)
        finally:
            browser.close()

    filters = _load_filters()
    filtered_items = _apply_filters(all_items, filters)

    bids: list[ScrapedBid] = []
    bq_rows_by_numero: dict[str, tuple[ScrapedBid, dict[str, Any]]] = {}
    for item in filtered_items:
        bid, bq_row = _build_bid_and_row(item)
        bids.append(bid)
        bq_rows_by_numero[bq_row["numero"]] = (bid, bq_row)

    existing = _existing_numeros_bq(list(bq_rows_by_numero.keys()))
    new_rows = [
        row for num, (_, row) in bq_rows_by_numero.items() if num not in existing
    ]

    _insert_bq(new_rows)
    for row in new_rows:
        _publish_edital(row["edital_id"], row["numero"])

    elapsed = time.perf_counter() - start
    for bid in bids:
        bid.find_time_seconds = elapsed

    logger.info(
        "ConLicitação concluído: coletados=%s filtrados=%s novos_bq=%s tempo=%.1fs",
        len(all_items),
        len(bids),
        len(new_rows),
        elapsed,
    )
    return bids
