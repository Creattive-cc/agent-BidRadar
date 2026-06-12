import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from agent.analyzer.matcher import score_bid_with_profile
from agent.company_profile import read_profile_files
from agent.config import settings
from agent.downloader import download_pending_pdfs
from agent.logging_utils import get_logger
from agent.models import Bid, SessionLocal, init_db
from agent.schemas import ScrapedBid
from agent.scraper import scrape_bll, scrape_comprasnet, scrape_conlicitacao, scrape_pncp

logger = get_logger("bidradar.runner")

# Termos que indicam aderência potencial ao portfólio educacional.
# Editais sem nenhum desses termos no título são descartados antes do Gemini.
_EDUCATION_KEYWORDS = [
    "educação", "educacional", "educaçao",
    "escolar", "escola", "escolas",
    "ensino", "aprendizagem", "aprendizado",
    "pedagógico", "pedagógica", "pedagogico", "pedagogica",
    "aluno", "alunos", "professor", "professores",
    "secretaria de educação", "secretaria municipal",
    "gestão escolar", "gestao escolar",
    "sistema de ensino", "sistema escolar",
    "saeb", "bncc", "ideb", "pnae",
    "ead", "eja", "alfabetização", "alfabetizacao",
    "recomposição", "recomposicao",
    "simulado", "avaliação educacional", "avaliacao educacional",
    "plataforma educacional", "software educacional",
    "material didático", "material didatico",
    "conteúdo didático", "conteudo didatico",
    "licença de software", "licenca de software",
    "plataforma de gestão", "plataforma de ensino",
    "tecnologia educacional", "tecnologia da educação",
]

_GEMINI_WORKERS = 20  # chamadas paralelas ao Gemini


def _is_education_related(bid: ScrapedBid) -> bool:
    """Descarta editais claramente fora do escopo educacional antes de chamar o Gemini."""
    text = (bid.title + " " + bid.agency).lower()
    return any(kw in text for kw in _EDUCATION_KEYWORDS)


def _score_one(bid: ScrapedBid, profile: dict) -> Bid | None:
    """Chama o Gemini para um bid e retorna o objeto Bid pronto para insert. Thread-safe."""
    try:
        analyzed = score_bid_with_profile(bid, profile)
        return Bid(
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
            resumo=analyzed.resumo,
        )
    except Exception as exc:
        logger.warning("Falha ao analisar bid '%s': %s", bid.title[:60], exc)
        return None


def run_once() -> dict[str, int]:
    init_db()
    profile = read_profile_files()
    if not profile:
        logger.warning("Nenhum arquivo de company_profile encontrado.")

    scraped_count = 0

    scrapers: list[tuple[str, Callable[[], list]]] = []
    if settings.enable_pncp:
        scrapers.append(("PNCP", scrape_pncp))
    if settings.enable_comprasnet:
        scrapers.append(("ComprasNet", scrape_comprasnet))
    if settings.enable_bll:
        scrapers.append(("BLL", scrape_bll))
    if settings.enable_conlicitacao:
        scrapers.append(("ConLicitação", scrape_conlicitacao))

    all_bids: list[ScrapedBid] = []
    for name, scraper in scrapers:
        try:
            bids = scraper()
            scraped_count += len(bids)
            all_bids.extend(bids)
            logger.info("Scraper %s concluiu com %s itens.", name, len(bids))
        except Exception as exc:
            logger.exception("Falha no scraper %s: %s", name, exc)

    # Dedup por URL contra o banco
    with SessionLocal() as session:
        all_urls = [b.url for b in all_bids if b.url]
        existing_urls: set[str] = set()
        if all_urls:
            existing_urls = {
                row[0]
                for row in session.query(Bid.url).filter(Bid.url.in_(all_urls)).all()
            }

    new_bids = [b for b in all_bids if b.url not in existing_urls]
    logger.info("Total scraped=%d | novos (sem dedup)=%d", scraped_count, len(new_bids))

    # Pré-filtro educacional — descarta editais sem nenhuma keyword relevante
    education_bids = [b for b in new_bids if _is_education_related(b)]
    discarded = len(new_bids) - len(education_bids)
    logger.info(
        "Pré-filtro educacional: %d relevantes | %d descartados",
        len(education_bids),
        discarded,
    )

    if not education_bids:
        logger.info("Nenhum edital educacional novo encontrado.")
        return {"scraped": scraped_count, "saved": 0, "discarded": discarded}

    # Scoring paralelo com Gemini — salva em mini-lotes de 50 para aparecer progressivamente
    _FLUSH_SIZE = 50
    saved_count = 0
    pending: list[Bid] = []
    seen_urls = set(existing_urls)

    def _flush(rows: list[Bid]) -> int:
        if not rows:
            return 0
        with SessionLocal() as session:
            session.add_all(rows)
            session.commit()
        return len(rows)

    with ThreadPoolExecutor(max_workers=_GEMINI_WORKERS) as executor:
        futures = {
            executor.submit(_score_one, bid, profile): bid
            for bid in education_bids
            if bid.url not in seen_urls
        }
        done = 0
        for future in as_completed(futures):
            done += 1
            row = future.result()
            if row is not None:
                pending.append(row)
            if done % 10 == 0:
                logger.info("Scoring: %d/%d concluídos", done, len(futures))
            if len(pending) >= _FLUSH_SIZE:
                saved_count += _flush(pending)
                pending.clear()
                logger.info("Flush parcial: %d salvos até agora", saved_count)

    # Flush final do restante
    saved_count += _flush(pending)
    pending.clear()

    pdf_results = download_pending_pdfs(limit=20)
    logger.info("Download de PDFs: %s", pdf_results)
    logger.info(
        "Ciclo finalizado em %s — scraped=%d educacionais=%d salvos=%d descartados=%d",
        datetime.utcnow().isoformat(),
        scraped_count,
        len(education_bids),
        saved_count,
        discarded,
    )

    return {
        "scraped": scraped_count,
        "education_filtered": len(education_bids),
        "saved": saved_count,
        "discarded": discarded,
    }


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
