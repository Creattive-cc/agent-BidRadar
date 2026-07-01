"""Scraper Universo Licitações com Playwright, BigQuery, Pub/Sub e Firestore."""

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from agent.config import settings
from agent.logging_utils import get_logger
from agent.schemas import ScrapedBid

logger = get_logger("bidradar.scraper.universo")

UNIVERSO_BASE = "https://www.universolicitacoes.com.br"
UNIVERSO_LOGIN = f"{UNIVERSO_BASE}/Geral/Login.aspx"
UNIVERSO_LISTING = f"{UNIVERSO_BASE}/Restrito/Licitacoes.aspx"

_bq_client: Any = None
_pubsub_client: Any = None
_firestore_client: Any = None


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


# ---------------------------------------------------------------------------
# Filtros e persistência
# ---------------------------------------------------------------------------

def _load_filters() -> dict[str, Any]:
    try:
        fs = _get_firestore()
        doc = fs.document("config/filters").get()
        return doc.to_dict() or {} if doc.exists else {}
    except Exception as exc:
        logger.warning("Firestore config/filters indisponivel: %s", exc)
        return {}


def _apply_filters(items: list[dict], filters: dict) -> list[dict]:
    valor_minimo: float = float(filters.get("valor_minimo") or 0)
    termos_exclusao: list[str] = [t.lower() for t in (filters.get("termos_exclusao") or [])]
    result = []
    for item in items:
        if valor_minimo and item.get("valor_estimado") and item["valor_estimado"] < valor_minimo:
            continue
        if termos_exclusao and any(t in item.get("objeto", "").lower() for t in termos_exclusao):
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
            query_parameters=[bigquery.ArrayQueryParameter("numeros", "STRING", numeros)]
        )
        rows = bq.query(
            f"SELECT numero FROM `{_bq_full_table()}` WHERE numero IN UNNEST(@numeros)",
            job_config=job_config,
        ).result()
        return {row.numero for row in rows}
    except Exception as exc:
        logger.warning("BigQuery verificacao de duplicatas falhou: %s", exc)
        return set()


def _insert_bq(rows: list[dict]) -> None:
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
        _get_pubsub().publish(topic_path, data).result(timeout=10)
    except Exception as exc:
        logger.warning("Pub/Sub publish falhou edital_id=%s: %s", edital_id, exc)


# ---------------------------------------------------------------------------
# Extração via JS evaluate
# ---------------------------------------------------------------------------

_EXTRACT_JS = """
() => {
    const rows = document.querySelectorAll('div.linha-link.row');
    return Array.from(rows).map(row => {
        const id = row.querySelector('input#codigoLicitacao')?.value || '';
        const cols = row.querySelectorAll('[class*="col-md"]');
        // cols[0] = ícones; [1]=edital; [2]=data_pub; [3]=data_abertura; [4]=modalidade; [5]=órgão; [6]=UF; [7]=objeto
        const get = (i) => (cols[i]?.innerText || '').trim().replace(/\\s+/g, ' ');
        return {
            id,
            edital: get(1),
            data_pub: get(2),
            data_abertura: get(3),
            modalidade: get(4),
            orgao: get(5),
            uf: get(6),
            objeto: get(7),
            url: id ? `https://www.universolicitacoes.com.br/Restrito/Licitacoes.aspx?c=${id}&p=` : ''
        };
    }).filter(item => item.objeto && item.url);
}
"""


def _parse_date(s: str) -> str | None:
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).strftime(
                "%Y-%m-%dT%H:%M:%S" if "H" in fmt else "%Y-%m-%d"
            )
        except ValueError:
            pass
    return None


def _build_bid_and_row(item: dict[str, Any]) -> tuple[ScrapedBid, dict[str, Any]]:
    bid = ScrapedBid(
        title=item["objeto"][:500],
        agency=f"{item['orgao']} ({item['uf']})"[:255],
        estimated_value=None,
        deadline=_parse_date(item.get("data_abertura", "")),
        url=item["url"],
        source_site="Universo Licitações",
        find_time_seconds=0.0,
    )
    bq_row = {
        "edital_id": str(uuid.uuid4()),
        "portal": "Universo Licitações",
        "numero": f"universo-{item['id']}",
        "orgao": f"{item['orgao']} ({item['uf']})"[:500],
        "modalidade": item.get("modalidade", "")[:100],
        "objeto": item["objeto"][:2000],
        "url": item["url"],
        "valor_estimado": None,
        "data_publicacao": _parse_date(item.get("data_pub", "")),
        "data_abertura": _parse_date(item.get("data_abertura", "")),
        "status": "publicado",
        "gcs_path": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return bid, bq_row


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def scrape_universo() -> list[ScrapedBid]:
    start = time.perf_counter()

    if not settings.universo_user or not settings.universo_pass:
        logger.error("Credenciais do Universo Licitações não configuradas. Abortando.")
        return []

    # Janela de data: mesmo BIDRADAR_PNCP_DAYS
    hoje = datetime.now()
    data_inicio = (hoje - timedelta(days=settings.pncp_days)).strftime("%d/%m/%Y")
    data_fim = hoje.strftime("%d/%m/%Y")
    logger.info("Janela de coleta: %s → %s", data_inicio, data_fim)

    all_items: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            logger.info("Autenticando no Universo Licitações...")
            page.goto(UNIVERSO_LOGIN, timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            page.fill('#ctl00_cphDados_txtLogin', settings.universo_user)
            page.fill('#ctl00_cphDados_txtSenha', settings.universo_pass)
            page.click('#ctl00_cphDados_btnLogar')
            page.wait_for_load_state("domcontentloaded", timeout=60000)
            logger.info("Login enviado. URL: %s", page.url)

            page.goto(UNIVERSO_LISTING, timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=30000)

            # Preenche filtro de data via JS — campo pode estar em seção colapsada/oculta
            page.evaluate(
                f"document.querySelector('#ctl00_cphDados_txtAbertura_Inicio').value = '{data_inicio}';"
                f"document.querySelector('#ctl00_cphDados_txtAbertura_Fim').value = '{data_fim}';"
            )

            # Dispara pesquisa
            page.click('#ctl00_cphDados_btnPesquisar')
            page.wait_for_load_state("domcontentloaded", timeout=60000)

            # Carrega a GridView (necessário quando há mais de 200 resultados)
            visualizar = page.locator('#btnVisualizar')
            if visualizar.count() > 0:
                logger.info("Clicando VISUALIZAR para renderizar resultados...")
                visualizar.first.click()
                page.wait_for_load_state("domcontentloaded", timeout=60000)
                page.wait_for_timeout(2000)

            # Extrai os itens da página
            items = page.evaluate(_EXTRACT_JS)
            all_items.extend(items)
            logger.info("Universo: %d itens coletados.", len(items))

            if not items:
                logger.warning("Nenhum item encontrado na listagem do Universo.")

        except PlaywrightTimeoutError as exc:
            logger.error("Timeout no Universo Licitações: %s", exc)
        except Exception as exc:
            logger.exception("Erro inesperado no scraper Universo: %s", exc)
        finally:
            browser.close()

    filters = _load_filters()
    filtered_items = _apply_filters(all_items, filters)

    bids: list[ScrapedBid] = []
    bq_rows_by_numero: dict[str, tuple[ScrapedBid, dict]] = {}
    for item in filtered_items:
        bid, bq_row = _build_bid_and_row(item)
        bids.append(bid)
        bq_rows_by_numero[bq_row["numero"]] = (bid, bq_row)

    existing = _existing_numeros_bq(list(bq_rows_by_numero.keys()))
    new_rows = [row for num, (_, row) in bq_rows_by_numero.items() if num not in existing]
    _insert_bq(new_rows)
    for row in new_rows:
        _publish_edital(row["edital_id"], row["numero"])

    elapsed = time.perf_counter() - start
    for bid in bids:
        bid.find_time_seconds = elapsed

    logger.info(
        "Universo Licitações concluído: coletados=%s filtrados=%s novos_bq=%s tempo=%.1fs",
        len(all_items), len(bids), len(new_rows), elapsed,
    )
    return bids
