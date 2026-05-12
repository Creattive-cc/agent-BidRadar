import base64
import json
from pathlib import Path

from agent.analyzer.gemini_analyzer import analyze_edital
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.company_profile import PROFILE_DIR, ensure_profile_dir, read_profile_files
from agent.config import settings
from agent.downloader import download_pending_pdfs
from agent.logging_utils import get_logger
from agent.models import Bid, SessionLocal, init_db
from agent.runner import run_once

app = FastAPI(title="BidRadar API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = get_logger("bidradar.api")


class MarkdownUpdate(BaseModel):
    content: str


class PubSubMessage(BaseModel):
    data: str
    messageId: str
    publishTime: str


class PubSubPushPayload(BaseModel):
    message: PubSubMessage
    subscription: str


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    ensure_profile_dir()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/licitacoes")
def list_bids() -> list[dict]:
    with SessionLocal() as session:
        rows = session.query(Bid).order_by(Bid.created_at.desc()).all()
        return [
            {
                "id": row.id,
                "title": row.title,
                "agency": row.agency,
                "estimated_value": row.estimated_value,
                "deadline": row.deadline,
                "url": row.url,
                "source_site": row.source_site,
                "find_time_seconds": row.find_time_seconds,
                "analysis_time_seconds": row.analysis_time_seconds,
                "score": row.score,
                "justification": row.justification,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


@app.get("/licitacoes/{bid_id}")
def get_bid(bid_id: int) -> dict:
    with SessionLocal() as session:
        row = session.query(Bid).filter(Bid.id == bid_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Licitacao nao encontrada")
        return {
            "id": row.id,
            "title": row.title,
            "agency": row.agency,
            "estimated_value": row.estimated_value,
            "deadline": row.deadline,
            "url": row.url,
            "source_site": row.source_site,
            "find_time_seconds": row.find_time_seconds,
            "analysis_time_seconds": row.analysis_time_seconds,
            "score": row.score,
            "justification": row.justification,
            "created_at": row.created_at.isoformat(),
        }


@app.post("/agent/run-once")
def trigger_agent() -> dict[str, int]:
    return run_once()


@app.get("/pubsub/health")
def pubsub_health() -> dict[str, str]:
    """Verifica a saúde do subscriber Pub/Sub."""
    return {"status": "ok", "topic": settings.pubsub_topic}


@app.post("/pubsub/analisar")
def pubsub_analisar(payload: PubSubPushPayload) -> dict[str, str]:
    """Endpoint para receber mensagens push do Pub/Sub e iniciar a análise."""
    edital_id = "unknown"
    try:
        # 1. Decodificar a mensagem
        try:
            data_bytes = base64.b64decode(payload.message.data)
            message_data = json.loads(data_bytes.decode("utf-8"))
            edital_id = message_data.get("edital_id", "missing")
            numero = message_data.get("numero", "missing")
        except (json.JSONDecodeError, UnicodeDecodeError, base64.binascii.Error) as e:
            logger.error("Pub/Sub: Erro ao decodificar mensagem: %s", e)
            raise HTTPException(status_code=400, detail="Invalid message data format")

        logger.info("Pub/Sub recebido: edital_id=%s numero=%s", edital_id, numero)

        # 2. Chamar o pipeline de download (e futuramente, análise)
        # O scraper já inseriu no BQ, o downloader vai buscar pendentes.
        # Limit=1 porque o gatilho é por edital.
        download_results = download_pending_pdfs(limit=1)
        logger.info(
            "Resultado do download de PDF para edital %s: %s",
            edital_id,
            download_results,
        )

        # Placeholder: pdf_text virá do ID-41 (Wagner)
        # Por ora passa string vazia para validar o pipeline
        profile_docs = read_profile_files()
        company_profile_text = "\n\n".join(
            f"## {name}\n{content}" for name, content in profile_docs.items()
        )
        result = analyze_edital(
            edital_id=edital_id,
            pdf_text="",  # TODO ID-41
            bid_metadata={"objetoCompra": numero},
            company_profile=company_profile_text,
        )
        logger.info(
            "Análise concluída: edital=%s score=%.1f prioridade=%s",
            edital_id,
            result.score,
            result.prioridade,
        )

        return {"status": "ok", "edital_id": edital_id}

    except HTTPException:
        # Re-raise HTTP exceptions para que o FastAPI as manipule
        raise
    except Exception:
        # 3. Erros de negócio não devem causar retentativa do Pub/Sub.
        # Logamos o erro e retornamos 200 OK.
        logger.exception(
            "Pub/Sub: Erro no processamento do edital %s. Retornando 200 para evitar retentativa.",
            edital_id,
        )
        return {"status": "error_acknowledged", "edital_id": edital_id}


@app.get("/company-profile/files")
def list_profile_files() -> list[str]:
    ensure_profile_dir()
    return sorted([p.name for p in PROFILE_DIR.glob("*.md")])


@app.get("/company-profile/{filename}")
def get_profile_file(filename: str) -> dict[str, str]:
    ensure_profile_dir()
    if not filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Somente arquivos .md sao aceitos")
    file_path = PROFILE_DIR / Path(filename).name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")
    return {
        "filename": file_path.name,
        "content": file_path.read_text(encoding="utf-8"),
    }


@app.put("/company-profile/{filename}")
def update_profile_file(filename: str, payload: MarkdownUpdate) -> dict[str, str]:
    ensure_profile_dir()
    if not filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Somente arquivos .md sao aceitos")
    file_path = PROFILE_DIR / Path(filename).name
    file_path.write_text(payload.content, encoding="utf-8")
    return {"status": "updated", "filename": file_path.name}
