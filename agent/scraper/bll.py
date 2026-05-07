import time
import re
from urllib.parse import urljoin, urlparse

import requests  # type: ignore[import-untyped]

from agent.logging_utils import get_logger
from agent.schemas import ScrapedBid

logger = get_logger("bidradar.scraper.bll")

BASES = (
    "https://www.bllcompras.com",
    "https://bllcompras.com",
)
DEFAULT_HEADERS = {
    "User-Agent": "BidRadar/0.1 (+local-agent)",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


def _normalize_bll_url(href: str, base_origin: str) -> str | None:
    href = href.strip()
    if not href or href.startswith("#") or href.lower().startswith("javascript:"):
        return None
    if href.startswith("//"):
        href = "https:" + href
    full = urljoin(f"{base_origin}/", href)
    parsed = urlparse(full)
    host = (parsed.netloc or "").lower()
    if "bllcompras.com" not in host:
        return None
    path = (parsed.path or "").lower()
    if "processsearchpublic" in path or "login" in path or "account" in path:
        return None
    if path.rstrip("/").endswith("/process") and "processview" not in path and "details" not in path:
        return None
    if not (
        "processview" in path
        or "details" in path
        or "document" in path
        or "/process/" in path
        or "edital" in path
        or "pregao" in path
    ):
        return None
    return full.split("#")[0]


def _extract_links_with_patterns(html: str, base_origin: str) -> list[str]:
    patterns = [
        re.compile(r'href\s*=\s*"(?P<href>[^"]+)"', re.IGNORECASE),
        re.compile(r"href\s*=\s*'(?P<href>[^']+)'", re.IGNORECASE),
        re.compile(r'(?P<href>/Process/[^\s"\'<>]+)', re.IGNORECASE),
        re.compile(r'(?P<href>https?://[^"\s<>]*bllcompras\.com[^"\s<>]*)', re.IGNORECASE),
        re.compile(r'data-(?:href|url)\s*=\s*"(?P<href>[^"]+)"', re.IGNORECASE),
        # URLs em atributos JS / JSON embutido
        re.compile(r'["\'](?P<href>/Process/[^"\']+)["\']', re.IGNORECASE),
        re.compile(
            r'["\'](?P<href>https?://(?:www\.)?bllcompras\.com[^"\']+)["\']',
            re.IGNORECASE,
        ),
    ]
    seen: set[str] = set()
    out: list[str] = []
    for pat in patterns:
        for m in pat.finditer(html):
            raw = m.group("href")
            norm = _normalize_bll_url(raw, base_origin)
            if norm and norm not in seen:
                seen.add(norm)
                out.append(norm)
            if len(out) >= 15:
                return out
    return out


def _fetch_html(url: str) -> str | None:
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=35)
        if not r.ok:
            logger.warning("BLL HTTP %s url=%s snippet=%s", r.status_code, url, (r.text or "")[:400])
            return None
        return r.text
    except requests.RequestException as exc:
        logger.warning("BLL request falhou url=%s err=%s", url, exc)
        return None


def scrape_bll() -> list[ScrapedBid]:
    start = time.perf_counter()
    search_paths = [
        "/Process/ProcessSearchPublic",
        "/Process/ProcessSearchPublic?SearchTerm=",
        "/",
    ]

    html_parts: list[tuple[str, str]] = []
    for origin in BASES:
        for path in search_paths:
            search_url = origin + path
            text = _fetch_html(search_url)
            if text:
                html_parts.append((origin, text))

    if not html_parts:
        logger.warning("BLL: nenhum HTML retornado das URLs de busca.")
        return []

    links: list[str] = []
    seen: set[str] = set()
    for origin, chunk in html_parts:
        for link in _extract_links_with_patterns(chunk, origin):
            if link not in seen:
                seen.add(link)
                links.append(link)
            if len(links) >= 15:
                break
        if len(links) >= 15:
            break

    html = "\n".join(h for _, h in html_parts)
    if not links:
        logger.warning("BLL: nenhum link extraido (layout pode ter mudado). HTML len=%s", len(html))

    title_pattern = re.compile(r">([^<>]{15,200})<")
    titles: list[str] = []
    keywords = ("pregao", "licit", "concorr", "dispensa", "edital", "compra", "processo")
    for m in title_pattern.finditer(html):
        text = " ".join(m.group(1).split())
        low = text.lower()
        if any(k in low for k in keywords) and len(text) > 14:
            titles.append(text)
        if len(titles) >= len(links):
            break

    bids: list[ScrapedBid] = []
    for idx, link in enumerate(links[:12]):
        title = titles[idx] if idx < len(titles) else f"Processo BLL #{idx + 1}"
        bids.append(
            ScrapedBid(
                title=title[:500],
                agency="Portal BLL Compras",
                estimated_value=None,
                deadline=None,
                url=link,
                source_site="BLL",
                find_time_seconds=0.0,
            )
        )

    elapsed = time.perf_counter() - start
    for bid in bids:
        bid.find_time_seconds = elapsed

    if bids:
        logger.info("BLL scraper concluiu com %s links.", len(bids))

    return bids
