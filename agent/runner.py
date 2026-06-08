import time
from collections.abc import Callable
from datetime import datetime

from agent.analyzer.matcher import score_bid_with_profile
from agent.company_profile import read_profile_files
from agent.config import settings
from agent.downloader import download_pending_pdfs
from agent.logging_utils import get_logger
from agent.models import Bid, SessionLocal, init_db
from agent.scraper import scrape_bll, scrape_comprasnet, scrape_conlicitacao, scrape_pncp

logger = get_logger("bidradar.runner")


def run_once() -> dict[str, int]:
    init_db()
    profile = read_profile_files()
    if not profile:
        logger.warning(
            "Nenhum arquivo de company_profile encontrado. Analise pode ficar limitada."
        )

    scraped_count = 0
    saved_count = 0

    scrapers: list[tuple[str, Callable[[], list]]] = []
    if settings.enable_pncp:
        scrapers.append(("PNCP", scrape_pncp))
    if settings.enable_comprasnet:
        scrapers.append(("ComprasNet", scrape_comprasnet))
    if settings.enable_bll:
        scrapers.append(("BLL", scrape_bll))
    if settings.enable_conlicitacao:
        scrapers.append(("ConLicitação", scrape_conlicitacao))

    all_bids = []
    for name, scraper in scrapers:
        try:
            bids = scraper()
            scraped_count += len(bids)
            all_bids.extend(bids)
            logger.info("Scraper %s concluiu com %s itens.", name, len(bids))
        except Exception as exc:
            # Tolerancia a falhas: continua os demais scrapers.
            logger.exception("Falha no scraper %s: %s", name, exc)

    with SessionLocal() as session:
        # Dedup: busca todas as URLs já existentes em batch
        all_urls = [b.url for b in all_bids if b.url]
        existing_urls: set[str] = set()
        if all_urls:
            existing_urls = {
                row[0]
                for row in session.query(Bid.url).filter(Bid.url.in_(all_urls)).all()
            }

        for bid in all_bids:
            if bid.url in existing_urls:
                continue
            analyzed = score_bid_with_profile(bid, profile)
            row = Bid(
                title=analyzed.title,
                agency=analyzed.agency,
                estimated_value=analyzed.estimated_value,
                deadline=analyzed.deadline,
                url=analyzed.url,
                source_site=analyzed.source_site,
                find_time_seconds=analyzed.find_time_seconds,
                analysis_time_seconds=analyzed.analysis_time_seconds,
                score=analyzed.score,
                justification=analyzed.justification,
            )
            session.add(row)
            existing_urls.add(bid.url)
            saved_count += 1
        session.commit()

    # Fora do bloco with session, após o commit.
    # Tenta baixar os PDFs pendentes, que podem incluir os que acabaram de ser inseridos no BigQuery pelos scrapers.
    pdf_results = download_pending_pdfs(limit=20)
    logger.info("Resultado do download de PDFs: %s", pdf_results)
    logger.info(
        "Ciclo finalizado em %s - capturadas=%s salvas=%s",
        datetime.utcnow().isoformat(),
        scraped_count,
        saved_count,
    )

    return {"scraped": scraped_count, "saved": saved_count}


def run_forever() -> None:
    logger.info(
        "Iniciando loop autonomo com intervalo de %s horas.", settings.interval_hours
    )
    while True:
        try:
            run_once()
        except Exception as exc:
            logger.exception("Erro no ciclo do agente: %s", exc)

        sleep_seconds = max(settings.interval_hours, 1) * 3600
        logger.info("Aguardando %s segundos para proximo ciclo.", sleep_seconds)
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    run_forever()
