"""Modulo para download de PDFs de editais e upload para o GCS."""

import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import requests
from google.cloud import bigquery, storage
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from agent.config import settings
from agent.logging_utils import get_logger

logger = get_logger("bidradar.downloader")

GCS_BUCKET_NAME = "creattive-licitacoes-dev-editais"

# ---------------------------------------------------------------------------
# Clientes GCP — inicializados sob demanda
# ---------------------------------------------------------------------------

_bq_client: Any = None
_gcs_client: Any = None


def _get_bq() -> bigquery.Client:
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client(project=settings.gcp_project_id)
    return _bq_client


def _get_gcs() -> storage.Client:
    global _gcs_client
    if _gcs_client is None:
        _gcs_client = storage.Client(project=settings.gcp_project_id)
    return _gcs_client


# ---------------------------------------------------------------------------
# Funcoes utilitarias
# ---------------------------------------------------------------------------


def _build_gcs_path(edital_id: str, portal: str, created_at: datetime) -> str:
    """Constroi o path do GCS para um edital."""
    portal_name = portal or "sem_portal"
    year = created_at.year if created_at else datetime.now().year
    month = created_at.month if created_at else datetime.now().month
    return f"editais/{portal_name.lower()}/{year}/{month:02d}/{edital_id}.pdf"


def _blob_exists(bucket: storage.Bucket, gcs_path: str) -> bool:
    """Verifica se um blob ja existe no GCS."""
    blob = bucket.blob(gcs_path)
    return blob.exists()


def _find_pdf_link_in_html(html_content: str, base_url: str) -> str | None:
    """Tenta encontrar um link de PDF em um conteudo HTML."""
    patterns = [
        re.compile(r'href\s*=\s*["\']([^"\']+\.pdf)["\']', re.IGNORECASE),
        re.compile(
            r'href\s*=\s*["\']([^"\']+)["\'].*?(?:download|edital|arquivo|visualizar)',
            re.IGNORECASE,
        ),
    ]
    for pattern in patterns:
        for match in pattern.finditer(html_content):
            link = match.group(1)
            if ".pdf" in link or "download" in link.lower():
                return urljoin(base_url, link)
    return None


def _download_pdf(url: str, max_attempts: int = 3, timeout: int = 30) -> bytes | None:
    """Baixa um PDF de uma URL, com retries e fallback para HTML."""
    session = requests.Session()
    retry_strategy = Retry(
        total=max_attempts,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    try:
        response = session.get(
            url, timeout=timeout, headers={"Accept": "application/pdf, text/html"}
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()

        if "application/pdf" in content_type:
            return response.content

        if "text/html" in content_type:
            logger.debug("URL retornou HTML, procurando por link de PDF: %s", url)
            pdf_link = _find_pdf_link_in_html(response.text, url)
            if pdf_link:
                logger.info("Link de PDF encontrado na pagina: %s", pdf_link)
                pdf_response = session.get(pdf_link, timeout=timeout)
                pdf_response.raise_for_status()
                if (
                    "application/pdf"
                    in pdf_response.headers.get("Content-Type", "").lower()
                ):
                    return pdf_response.content
            logger.warning(
                "Nao foi possivel encontrar um link de PDF na pagina: %s", url
            )
            return None

        logger.warning(
            "Conteudo nao e PDF nem HTML. Content-Type: %s, URL: %s", content_type, url
        )
        return None

    except requests.exceptions.RequestException as e:
        logger.error("Falha ao baixar PDF de %s (apos retries): %s", url, e)
        return None


def _upload_to_gcs(pdf_bytes: bytes, gcs_path: str) -> str | None:
    """Faz upload de bytes de um PDF para o GCS e retorna o path."""
    try:
        gcs = _get_gcs()
        bucket = gcs.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(gcs_path)
        blob.upload_from_string(pdf_bytes, content_type="application/pdf")
        logger.info("PDF salvo em GCS: gs://%s/%s", GCS_BUCKET_NAME, gcs_path)
        return gcs_path
    except Exception as e:
        logger.error("Falha no upload para GCS (path: %s): %s", gcs_path, e)
        return None


def _update_gcs_path_bq(edital_id: str, gcs_path: str) -> None:
    """Atualiza o campo gcs_path de um edital no BigQuery."""
    try:
        bq = _get_bq()
        table_id = f"{settings.gcp_project_id}.{settings.bigquery_dataset}.{settings.bigquery_table}"
        query = f"""
            UPDATE `{table_id}`
            SET gcs_path = @gcs_path
            WHERE edital_id = @edital_id
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("gcs_path", "STRING", gcs_path),
                bigquery.ScalarQueryParameter("edital_id", "STRING", edital_id),
            ]
        )
        query_job = bq.query(query, job_config=job_config)
        query_job.result()
        logger.info("BigQuery atualizado para edital_id %s com gcs_path.", edital_id)
    except Exception as e:
        logger.error("Falha ao atualizar BigQuery para edital_id %s: %s", edital_id, e)


def _fetch_pending_bids_bq(limit: int) -> list[dict[str, Any]]:
    """Busca no BigQuery por editais pendentes de download de PDF."""
    try:
        bq = _get_bq()
        table_id = f"{settings.gcp_project_id}.{settings.bigquery_dataset}.{settings.bigquery_table}"
        query = f"""
            SELECT edital_id, portal, url, created_at
            FROM `{table_id}`
            WHERE gcs_path IS NULL AND url IS NOT NULL
            ORDER BY created_at DESC
            LIMIT {limit}
        """
        rows = bq.query(query).result()
        results = [dict(row) for row in rows]
        logger.info(
            "Encontrados %d editais pendentes de download de PDF.", len(results)
        )
        return results
    except Exception as e:
        logger.error("Falha ao buscar editais pendentes no BigQuery: %s", e)
        return []


def download_pending_pdfs(limit: int = 50) -> dict[str, int]:
    """Baixa PDFs de editais pendentes, salva no GCS e atualiza o BigQuery."""
    start_time = time.perf_counter()
    stats = {"downloaded": 0, "skipped": 0, "errors": 0}

    pending_bids = _fetch_pending_bids_bq(limit)
    if not pending_bids:
        logger.info("Nenhum PDF pendente para download.")
        return stats

    bucket = _get_gcs().bucket(GCS_BUCKET_NAME)

    for bid in pending_bids:
        edital_id, portal, url, created_at = (
            bid["edital_id"],
            bid["portal"],
            bid["url"],
            bid["created_at"],
        )
        try:
            gcs_path = _build_gcs_path(edital_id, portal, created_at)

            if _blob_exists(bucket, gcs_path):
                logger.info("PDF ja existe no GCS, pulando: %s", gcs_path)
                _update_gcs_path_bq(edital_id, gcs_path)
                stats["skipped"] += 1
                continue

            pdf_bytes = _download_pdf(url)
            if not pdf_bytes:
                stats["errors"] += 1
                continue

            uploaded_path = _upload_to_gcs(pdf_bytes, gcs_path)
            if not uploaded_path:
                stats["errors"] += 1
                continue

            _update_gcs_path_bq(edital_id, uploaded_path)
            stats["downloaded"] += 1

        except Exception as e:
            logger.exception("Erro inesperado ao processar edital %s: %s", edital_id, e)
            stats["errors"] += 1

    elapsed = time.perf_counter() - start_time
    logger.info("Download de PDFs concluido em %.2fs. Resultados: %s", elapsed, stats)
    return stats
