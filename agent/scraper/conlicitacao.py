"""Scraper ConLicitação com Playwright, BigQuery, Pub/Sub e Firestore."""

import json
import re
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

CONLICITACAO_URL = "https://consulteonline.conlicitacao.com.br"
_MAX_PAGES = 20

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
    """Credenciais: env vars primeiro, Secret Manager como fallback."""
    if settings.conlicitacao_user and settings.conlicitacao_pass:
        return {"user": settings.conlicitacao_user, "password": settings.conlicitacao_pass}
    creds = {"user": "", "password": ""}
    try:
        sm = _get_secret_manager()
        project_id = settings.gcp_project_id
        user_response = sm.access_secret_version(
            request={"name": f"projects/{project_id}/secrets/CONLICITACAO_USER/versions/latest"}
        )
        creds["user"] = user_response.payload.data.decode("UTF-8")
        pass_response = sm.access_secret_version(
            request={"name": f"projects/{project_id}/secrets/CONLICITACAO_PASS/versions/latest"}
        )
        creds["password"] = pass_response.payload.data.decode("UTF-8")
    except Exception as exc:
        logger.error("Falha ao buscar credenciais do ConLicitação no Secret Manager: %s", exc)
    return creds


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
    const cards = document.querySelectorAll('div.card');
    return Array.from(cards).map(card => {
        const body = card.querySelector('.tour-bidding-info');
        if (!body) return null;

        // Objeto: div.flex-grow-1 dentro do primeiro bloco bidding-info
        const objeto = (body.querySelector('.flex-grow-1')?.innerText || '').trim();

        // Prazo: span dentro de div.text-secondary.d-flex
        let prazo = '';
        const prazoBruto = body.querySelector('.text-secondary.d-flex span')?.innerText || '';
        const prazoMatch = prazoBruto.match(/Prazo:\\s*(.+)/);
        if (prazoMatch) prazo = prazoMatch[1].trim();

        // Órgão: button.databalloon — remove trailing "info" do ícone
        const orgaoRaw = body.querySelector('button.databalloon')?.innerText || '';
        const orgao = orgaoRaw.replace(/\\s*info\\s*$/, '').trim();

        // Edital: text-secondary na row com título "Edital:"
        let edital = '';
        body.querySelectorAll('.bidding-info-title').forEach(title => {
            if (title.innerText.trim() === 'Edital:') {
                const sibling = title.nextElementSibling;
                if (sibling) edital = sibling.innerText.trim();
            }
        });

        // Nº Conlicitação
        let numero = '';
        card.querySelectorAll('p, span, div').forEach(el => {
            if ((el.innerText || '').includes('Nº Conlicitação:') && el.children.length < 3) {
                const match = el.innerText.match(/Nº Conlicitação:\\s*(\\d+)/);
                if (match) numero = match[1];
            }
        });

        // Link "Ver mais" — React Router usa href relativo
        let url = numero ? `https://consulteonline.conlicitacao.com.br/banco_de_dados/${numero}` : '';
        const verMaisLink = Array.from(card.querySelectorAll('a')).find(a =>
            (a.innerText || '').includes('Ver mais informações'));
        if (verMaisLink) {
            const href = verMaisLink.getAttribute('href');
            if (href && !href.startsWith('#') && !href.startsWith('javascript')) {
                url = href.startsWith('http') ? href : `https://consulteonline.conlicitacao.com.br${href}`;
            }
        }

        return {objeto, prazo, orgao, edital, numero, url};
    }).filter(Boolean).filter(item => item.objeto && item.url);
}
"""


def _extract_bids_from_page(page: Page) -> list[dict[str, Any]]:
    try:
        return page.evaluate(_EXTRACT_JS)
    except Exception as exc:
        logger.warning("JS evaluate falhou na extração de cards: %s", exc)
        return []


def _parse_datetime(s: str) -> str | None:
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
        agency=item["orgao"][:255],
        estimated_value=None,
        deadline=_parse_datetime(item.get("prazo", "")),
        url=item["url"],
        source_site="ConLicitação",
        find_time_seconds=0.0,
    )
    bq_row = {
        "edital_id": str(uuid.uuid4()),
        "portal": "ConLicitação",
        "numero": item["numero"],
        "orgao": item["orgao"][:500],
        "modalidade": item.get("edital", "")[:100],
        "objeto": item["objeto"][:2000],
        "url": item["url"],
        "valor_estimado": None,
        "data_publicacao": None,
        "data_abertura": _parse_datetime(item.get("prazo", "")),
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

    all_items: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            logger.info("Autenticando no ConLicitação...")
            page.goto(CONLICITACAO_URL, timeout=60000)
            page.wait_for_selector('input[name="login"]', timeout=30000)
            page.fill('input[name="login"]', creds["user"])
            page.fill('input[name="senha"]', creds["password"])
            page.click('input[name="commit"]')
            page.wait_for_url(f"{CONLICITACAO_URL}/painel", timeout=60000)
            logger.info("Autenticação bem-sucedida. Navegando ao banco de dados...")

            page.goto(f"{CONLICITACAO_URL}/banco_de_dados", timeout=60000)
            page.wait_for_selector("div.card", timeout=30000)
            page.wait_for_timeout(3000)

            # Fecha modal de boas-vindas se existir
            modal_close = page.locator('button[aria-label="Close"], .modal button[type="button"]')
            if modal_close.count() > 0:
                modal_close.first.click()
                page.wait_for_timeout(500)

            for page_num in range(1, _MAX_PAGES + 1):
                logger.info("Coletando página %d...", page_num)
                items_on_page = _extract_bids_from_page(page)
                if not items_on_page:
                    logger.info("Nenhum item na página %d. Finalizando.", page_num)
                    break
                all_items.extend(items_on_page)
                logger.info("Página %d: %d itens.", page_num, len(items_on_page))

                next_btn = page.locator('button[aria-label="Próximo"]')
                if next_btn.count() == 0 or next_btn.first.get_attribute("disabled") is not None:
                    logger.info("Fim da paginação na página %d.", page_num)
                    break
                next_btn.first.click()
                page.wait_for_selector("div.card", timeout=30000)
                page.wait_for_timeout(2000)

        except PlaywrightTimeoutError as exc:
            logger.error("Timeout no ConLicitação: %s", exc)
        except Exception as exc:
            logger.exception("Erro inesperado no scraper ConLicitação: %s", exc)
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
        "ConLicitação concluído: coletados=%s filtrados=%s novos_bq=%s tempo=%.1fs",
        len(all_items), len(bids), len(new_rows), elapsed,
    )
    return bids
