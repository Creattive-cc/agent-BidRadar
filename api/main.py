from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from agent.models import SessionLocal, Bid, init_db
from agent.runner import run_once
from agent.company_profile import PROFILE_DIR, ensure_profile_dir

app = FastAPI(title="BidRadar API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MarkdownUpdate(BaseModel):
    content: str


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
    return {"filename": file_path.name, "content": file_path.read_text(encoding="utf-8")}


@app.put("/company-profile/{filename}")
def update_profile_file(filename: str, payload: MarkdownUpdate) -> dict[str, str]:
    ensure_profile_dir()
    if not filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Somente arquivos .md sao aceitos")
    file_path = PROFILE_DIR / Path(filename).name
    file_path.write_text(payload.content, encoding="utf-8")
    return {"status": "updated", "filename": file_path.name}
