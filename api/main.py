import base64
import json
from datetime import datetime
from pathlib import Path

from agent.analyzer.gemini_analyzer import analyze_edital
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agent.company_profile import PROFILE_DIR, ensure_profile_dir, read_profile_files
from agent.config import settings
from agent.downloader import download_pending_pdfs
from agent.logging_utils import get_logger
from agent.models import AgentLog, Bid, FilterConfig, Product, SessionLocal, User, init_db
from agent.runner import run_once
from api.auth import (
    create_access_token,
    get_current_user,
    get_db,
    hash_password,
    require_admin,
    verify_password,
)

app = FastAPI(title="BidRadar API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = get_logger("bidradar.api")

_FRONTEND_BUILD = Path(__file__).parent.parent / "frontend" / "dist"

# ── Pydantic schemas ──────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    email: str
    password: str


class CreateUserRequest(BaseModel):
    email: str
    password: str
    role: str = "operator"


class UpdateUserRequest(BaseModel):
    email: str | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


class FilterConfigUpdate(BaseModel):
    exclusion_terms: list[str] | None = None
    min_value: float | None = None
    max_capital_social_pct: float | None = None
    enable_exclusion_terms: bool | None = None
    enable_min_value: bool | None = None
    enable_capital_social: bool | None = None


class ProductCreate(BaseModel):
    name: str
    description: str = ""
    cnae_codes: list[str] = []
    tags: list[str] = []


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    cnae_codes: list[str] | None = None
    tags: list[str] | None = None
    is_active: bool | None = None


class MarkdownUpdate(BaseModel):
    content: str


class PubSubMessage(BaseModel):
    data: str
    messageId: str
    publishTime: str


class PubSubPushPayload(BaseModel):
    message: PubSubMessage
    subscription: str


# ── Startup ───────────────────────────────────────────────────────────────────


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    ensure_profile_dir()
    _ensure_admin_user()
    _ensure_filter_config()


def _ensure_admin_user() -> None:
    with SessionLocal() as db:
        if not db.query(User).first():
            db.add(
                User(
                    email=settings.admin_email,
                    hashed_password=hash_password(settings.admin_password),
                    role="admin",
                    is_active=True,
                )
            )
            db.commit()
            logger.info("Admin padrão criado: %s", settings.admin_email)


def _ensure_filter_config() -> None:
    with SessionLocal() as db:
        if not db.query(FilterConfig).filter(FilterConfig.id == 1).first():
            db.add(FilterConfig(id=1))
            db.commit()


# ── Health ────────────────────────────────────────────────────────────────────


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ── Auth ──────────────────────────────────────────────────────────────────────


@app.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = (
        db.query(User)
        .filter(User.email == payload.email, User.is_active == True)
        .first()
    )
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    token = create_access_token(user.email, user.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "role": user.role},
    }


@app.get("/auth/me")
def me(current_user: User = Depends(get_current_user)) -> dict:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }


# ── Admin: Users ──────────────────────────────────────────────────────────────


@app.get("/admin/users")
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@app.post("/admin/users", status_code=201)
def create_user(
    payload: CreateUserRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")
    if payload.role not in ("admin", "operator"):
        raise HTTPException(status_code=400, detail="Role inválido: use 'admin' ou 'operator'")
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "email": user.email, "role": user.role, "is_active": user.is_active}


@app.put("/admin/users/{user_id}")
def update_user(
    user_id: int,
    payload: UpdateUserRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if payload.email is not None:
        user.email = payload.email
    if payload.role is not None:
        if payload.role not in ("admin", "operator"):
            raise HTTPException(status_code=400, detail="Role inválido")
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password is not None:
        user.hashed_password = hash_password(payload.password)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "email": user.email, "role": user.role, "is_active": user.is_active}


@app.delete("/admin/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> None:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="Não é possível remover o próprio usuário")
    db.delete(user)
    db.commit()


# ── Stats ─────────────────────────────────────────────────────────────────────


@app.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    bids = db.query(Bid).all()
    total = len(bids)
    analyzed = sum(1 for b in bids if b.analysis_time_seconds > 0)
    hot = sum(1 for b in bids if b.score >= 70)
    total_value = sum(b.estimated_value or 0 for b in bids if b.score >= 70)
    hours_saved = round(total * 0.25, 1)
    return {
        "total_bids": total,
        "hours_saved": hours_saved,
        "opportunities": hot,
        "total_value": total_value,
        "funnel": {
            "captured": total,
            "filtered": analyzed,
            "analyzed": analyzed,
            "hot": hot,
        },
    }


# ── Agent Logs ────────────────────────────────────────────────────────────────


@app.get("/logs")
def get_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    logs = (
        db.query(AgentLog).order_by(AgentLog.timestamp.desc()).limit(limit).all()
    )
    if logs:
        return [_log_to_dict(log) for log in logs]

    # Derive synthetic logs from existing bids when no explicit logs exist
    bids = db.query(Bid).order_by(Bid.created_at.desc()).limit(30).all()
    derived: list[dict] = []
    for bid in bids:
        derived.append(
            {
                "id": f"bid-{bid.id}-detect",
                "timestamp": bid.created_at.isoformat(),
                "event_type": "detection",
                "title": "Novo Edital Detectado",
                "product": bid.source_site,
                "bid_type": bid.title[:60],
                "score": None,
            }
        )
        if bid.analysis_time_seconds > 0:
            if bid.score >= 70:
                derived.append(
                    {
                        "id": f"bid-{bid.id}-match",
                        "timestamp": bid.created_at.isoformat(),
                        "event_type": "high_match",
                        "title": f"Oportunidade Encontrada (Match de {int(bid.score)}%)",
                        "product": bid.source_site,
                        "bid_type": bid.title[:60],
                        "score": bid.score,
                    }
                )
            else:
                derived.append(
                    {
                        "id": f"bid-{bid.id}-discard",
                        "timestamp": bid.created_at.isoformat(),
                        "event_type": "auto_discard",
                        "title": "Edital Descartado (Filtro Automático)",
                        "product": bid.source_site,
                        "bid_type": bid.title[:60],
                        "score": bid.score,
                    }
                )
    return sorted(derived, key=lambda x: x["timestamp"], reverse=True)[:limit]


def _log_to_dict(log: AgentLog) -> dict:
    return {
        "id": log.id,
        "timestamp": log.timestamp.isoformat(),
        "event_type": log.event_type,
        "title": log.title,
        "product": log.product,
        "bid_type": log.bid_type,
        "score": log.score,
    }


# ── Filters ───────────────────────────────────────────────────────────────────


@app.get("/filters")
def get_filters(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    cfg = db.query(FilterConfig).filter(FilterConfig.id == 1).first()
    if not cfg:
        return {
            "exclusion_terms": [],
            "min_value": None,
            "max_capital_social_pct": None,
            "enable_exclusion_terms": True,
            "enable_min_value": True,
            "enable_capital_social": False,
        }
    return _filter_to_dict(cfg)


@app.put("/filters")
def update_filters(
    payload: FilterConfigUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    cfg = db.query(FilterConfig).filter(FilterConfig.id == 1).first()
    if not cfg:
        cfg = FilterConfig(id=1)
        db.add(cfg)
    if payload.exclusion_terms is not None:
        cfg.exclusion_terms = json.dumps(payload.exclusion_terms)
    if payload.min_value is not None:
        cfg.min_value = payload.min_value
    if payload.max_capital_social_pct is not None:
        cfg.max_capital_social_pct = payload.max_capital_social_pct
    if payload.enable_exclusion_terms is not None:
        cfg.enable_exclusion_terms = payload.enable_exclusion_terms
    if payload.enable_min_value is not None:
        cfg.enable_min_value = payload.enable_min_value
    if payload.enable_capital_social is not None:
        cfg.enable_capital_social = payload.enable_capital_social
    cfg.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(cfg)
    return _filter_to_dict(cfg)


def _filter_to_dict(cfg: FilterConfig) -> dict:
    return {
        "exclusion_terms": json.loads(cfg.exclusion_terms),
        "min_value": cfg.min_value,
        "max_capital_social_pct": cfg.max_capital_social_pct,
        "enable_exclusion_terms": cfg.enable_exclusion_terms,
        "enable_min_value": cfg.enable_min_value,
        "enable_capital_social": cfg.enable_capital_social,
    }


# ── Products ──────────────────────────────────────────────────────────────────


@app.get("/products")
def list_products(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    return [_product_to_dict(p) for p in db.query(Product).order_by(Product.created_at).all()]


@app.post("/products", status_code=201)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    product = Product(
        name=payload.name,
        description=payload.description,
        cnae_codes=json.dumps(payload.cnae_codes),
        tags=json.dumps(payload.tags),
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return _product_to_dict(product)


@app.put("/products/{product_id}")
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    if payload.name is not None:
        product.name = payload.name
    if payload.description is not None:
        product.description = payload.description
    if payload.cnae_codes is not None:
        product.cnae_codes = json.dumps(payload.cnae_codes)
    if payload.tags is not None:
        product.tags = json.dumps(payload.tags)
    if payload.is_active is not None:
        product.is_active = payload.is_active
    db.commit()
    db.refresh(product)
    return _product_to_dict(product)


@app.delete("/products/{product_id}", status_code=204)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> None:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    db.delete(product)
    db.commit()


def _product_to_dict(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "cnae_codes": json.loads(p.cnae_codes),
        "tags": json.loads(p.tags),
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat(),
    }


# ── Licitações ────────────────────────────────────────────────────────────────


@app.get("/licitacoes")
def list_bids(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    rows = db.query(Bid).order_by(Bid.created_at.desc()).all()
    return [_bid_to_dict(row) for row in rows]


@app.get("/licitacoes/{bid_id}")
def get_bid(
    bid_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    row = db.query(Bid).filter(Bid.id == bid_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Licitacao nao encontrada")
    return _bid_to_dict(row)


def _bid_to_dict(row: Bid) -> dict:
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
        "resumo": row.resumo,
        "created_at": row.created_at.isoformat(),
    }


# ── Admin bids ────────────────────────────────────────────────────────────────

_SEED_BIDS = [
    {
        "title": "Contratação de plataforma SaaS de gestão escolar para secretaria municipal de educação — módulos de matrícula, frequência e notas",
        "agency": "Secretaria Municipal de Educação de Campinas",
        "estimated_value": 480000.0,
        "deadline": "2026-07-15T14:00:00",
        "url": "https://pncp.gov.br/app/editais/demo-001",
        "source_site": "PNCP",
        "score": 88.0,
        "justification": "O edital solicita uma plataforma SaaS completa de gestão escolar para rede municipal, com módulos de cadastro de alunos, controle de matrículas, frequência e geração de relatórios — alinhamento direto com o Edux.me Plus. A secretaria municipal de educação é o órgão contratante, público-alvo central do produto. Valor estimado dentro da faixa operada pela empresa. Alta aderência.",
    },
    {
        "title": "Aquisição de programa educacional PaaS com conteúdo didático BNCC para recomposição escolar e recuperação de aprendizagem no ensino fundamental",
        "agency": "Prefeitura Municipal de Ribeirão Preto — Secretaria de Educação",
        "estimated_value": 320000.0,
        "deadline": "2026-07-22T10:00:00",
        "url": "https://pncp.gov.br/app/editais/demo-002",
        "source_site": "PNCP",
        "score": 74.0,
        "justification": "Edital voltado para plataforma de recomposição de aprendizagem com conteúdo alinhado à BNCC para alunos do ensino fundamental com distorção idade/série. Aderente ao Konectar.me. Não menciona gestão administrativa escolar (Edux.me Plus) nem preparação para SAEB (Projeto SAEB). Match parcial.",
    },
    {
        "title": "Contratação de solução tecnológica para aplicação de simulados SAEB, processamento de cartões-resposta e analytics educacional para rede estadual",
        "agency": "Secretaria de Estado da Educação de Minas Gerais",
        "estimated_value": 750000.0,
        "deadline": "2026-08-01T09:00:00",
        "url": "https://pncp.gov.br/app/editais/demo-003",
        "source_site": "PNCP",
        "score": 67.0,
        "justification": "O edital trata especificamente de avaliação educacional alinhada ao SAEB com processamento de cartões-resposta e dashboards analíticos — cobertura direta do Projeto SAEB. Valor elevado pode exigir consórcio. Nenhuma menção a gestão escolar ou conteúdo didático, portanto Edux.me Plus e Konectar.me têm baixa relevância aqui.",
    },
    {
        "title": "Contratação de empresa para execução de obras de pavimentação asfáltica em vias urbanas do município",
        "agency": "Prefeitura Municipal de Sorocaba — Secretaria de Obras",
        "estimated_value": 1200000.0,
        "deadline": "2026-07-30T08:00:00",
        "url": "https://pncp.gov.br/app/editais/demo-004",
        "source_site": "PNCP",
        "score": 4.0,
        "justification": "Edital de obra civil para pavimentação asfáltica. Sem qualquer relação com tecnologia educacional, gestão escolar, plataformas SaaS/PaaS ou avaliações pedagógicas. Nenhum dos produtos da empresa possui aderência a este tipo de contratação.",
    },
]


@app.post("/admin/bids/seed", status_code=201)
def seed_bids(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    from datetime import datetime as dt
    inserted = 0
    for data in _SEED_BIDS:
        bid = Bid(
            title=data["title"],
            agency=data["agency"],
            estimated_value=data.get("estimated_value"),
            deadline=data.get("deadline"),
            url=data["url"],
            source_site=data["source_site"],
            find_time_seconds=0.0,
            analysis_time_seconds=0.0,
            score=data["score"],
            justification=data["justification"],
            created_at=dt.utcnow(),
        )
        db.add(bid)
        inserted += 1
    db.commit()
    return {"inserted": inserted}


@app.delete("/admin/bids", status_code=200)
def delete_all_bids(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    count = db.query(Bid).delete()
    db.commit()
    return {"deleted": count}


@app.post("/admin/reprocess", status_code=200)
def reprocess_bids(
    min_score: float = 0,
    _: User = Depends(require_admin),
) -> dict:
    """Re-analisa bids com score >= min_score. Síncrono — aguarda conclusão."""
    from agent.analyzer.matcher import score_bid_with_profile
    from agent.company_profile import read_profile_files
    from agent.schemas import ScrapedBid

    profile = read_profile_files()
    updated = 0
    failed = 0
    with SessionLocal() as session:
        query = session.query(Bid)
        if min_score > 0:
            query = query.filter(Bid.score >= min_score)
        bids = query.order_by(Bid.score.desc()).all()
        total = len(bids)
        logger.info("Reprocessando %d bids (min_score=%.0f)...", total, min_score)
        for i, row in enumerate(bids, 1):
            try:
                scraped = ScrapedBid(
                    title=row.title,
                    agency=row.agency,
                    estimated_value=row.estimated_value,
                    deadline=row.deadline,
                    url=row.url,
                    source_site=row.source_site,
                    find_time_seconds=row.find_time_seconds,
                )
                analyzed = score_bid_with_profile(scraped, profile)
                row.score = analyzed.score
                row.justification = analyzed.justification
                row.resumo = analyzed.resumo
                row.analysis_time_seconds = analyzed.analysis_time_seconds
                updated += 1
                if i % 5 == 0:
                    session.commit()
                    logger.info("Reprocessados %d/%d", i, total)
            except Exception as exc:
                failed += 1
                logger.warning("Falha ao reprocessar bid %d: %s", row.id, exc)
        session.commit()
        logger.info("Reprocessamento concluido: %d atualizados, %d falhas.", updated, failed)
    return {"total": total, "updated": updated, "failed": failed}


# ── Agent ─────────────────────────────────────────────────────────────────────


@app.post("/agent/run-once")
def trigger_agent(_: User = Depends(get_current_user)) -> dict:
    return run_once()


@app.post("/admin/trigger", status_code=202)
def scheduler_trigger(x_scheduler_secret: str = Header(default="")) -> dict:
    if not settings.scheduler_secret or x_scheduler_secret != settings.scheduler_secret:
        raise HTTPException(status_code=403, detail="Forbidden")
    import threading
    threading.Thread(target=run_once, daemon=True).start()
    return {"status": "accepted"}


# ── Pub/Sub ───────────────────────────────────────────────────────────────────


@app.get("/pubsub/health")
def pubsub_health() -> dict:
    return {"status": "ok", "topic": settings.pubsub_topic}


@app.post("/pubsub/analisar")
def pubsub_analisar(payload: PubSubPushPayload) -> dict:
    edital_id = "unknown"
    try:
        try:
            data_bytes = base64.b64decode(payload.message.data)
            message_data = json.loads(data_bytes.decode("utf-8"))
            edital_id = message_data.get("edital_id", "missing")
            numero = message_data.get("numero", "missing")
        except (json.JSONDecodeError, UnicodeDecodeError, base64.binascii.Error) as e:
            logger.error("Pub/Sub: Erro ao decodificar mensagem: %s", e)
            raise HTTPException(status_code=400, detail="Invalid message data format")

        logger.info("Pub/Sub recebido: edital_id=%s numero=%s", edital_id, numero)
        download_results = download_pending_pdfs(limit=1)
        logger.info("Resultado do download: %s", download_results)

        profile_docs = read_profile_files()
        company_profile_text = "\n\n".join(
            f"## {name}\n{content}" for name, content in profile_docs.items()
        )
        result = analyze_edital(
            edital_id=edital_id,
            pdf_text="",
            bid_metadata={"objetoCompra": numero},
            company_profile=company_profile_text,
        )
        logger.info(
            "Análise: edital=%s score=%.1f prioridade=%s",
            edital_id,
            result.score,
            result.prioridade,
        )
        return {"status": "ok", "edital_id": edital_id}

    except HTTPException:
        raise
    except Exception:
        logger.exception("Pub/Sub: Erro no processamento do edital %s.", edital_id)
        return {"status": "error_acknowledged", "edital_id": edital_id}


# ── Company Profile ───────────────────────────────────────────────────────────


@app.get("/company-profile/files")
def list_profile_files(_: User = Depends(get_current_user)) -> list[str]:
    ensure_profile_dir()
    return sorted([p.name for p in PROFILE_DIR.glob("*.md")])


@app.get("/company-profile/{filename}")
def get_profile_file(filename: str, _: User = Depends(get_current_user)) -> dict:
    ensure_profile_dir()
    if not filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Somente arquivos .md sao aceitos")
    file_path = PROFILE_DIR / Path(filename).name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")
    return {"filename": file_path.name, "content": file_path.read_text(encoding="utf-8")}


@app.put("/company-profile/{filename}")
def update_profile_file(
    filename: str,
    payload: MarkdownUpdate,
    _: User = Depends(get_current_user),
) -> dict:
    ensure_profile_dir()
    if not filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Somente arquivos .md sao aceitos")
    file_path = PROFILE_DIR / Path(filename).name
    file_path.write_text(payload.content, encoding="utf-8")
    return {"status": "updated", "filename": file_path.name}


# ── SPA (React build) — must be last ─────────────────────────────────────────


@app.get("/{full_path:path}", include_in_schema=False)
def serve_spa(full_path: str) -> FileResponse:
    if not _FRONTEND_BUILD.exists():
        raise HTTPException(status_code=404, detail="Frontend not built. Run: cd frontend && npm run build")
    target = _FRONTEND_BUILD / full_path
    if target.is_file():
        return FileResponse(str(target))
    return FileResponse(str(_FRONTEND_BUILD / "index.html"))
