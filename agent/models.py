from datetime import datetime
from sqlalchemy import Boolean, create_engine, String, Float, DateTime, Integer, Text
from sqlalchemy.orm import declarative_base, Mapped, mapped_column, sessionmaker
from agent.config import settings

Base = declarative_base()


class Bid(Base):
    __tablename__ = "bids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500))
    agency: Mapped[str] = mapped_column(String(255))
    estimated_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    deadline: Mapped[str | None] = mapped_column(String(100), nullable=True)
    url: Mapped[str] = mapped_column(String(1000))
    source_site: Mapped[str] = mapped_column(String(100))
    find_time_seconds: Mapped[float] = mapped_column(Float, default=0)
    analysis_time_seconds: Mapped[float] = mapped_column(Float, default=0)
    score: Mapped[float] = mapped_column(Float)
    justification: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="operator")  # admin | operator
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FilterConfig(Base):
    __tablename__ = "filter_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exclusion_terms: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_capital_social_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    enable_exclusion_terms: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_min_value: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_capital_social: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    cnae_codes: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    tags: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # detection | ai_processing | high_match | human_review | auto_discard
    event_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(500))
    product: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bid_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bid_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)


engine = create_engine(f"sqlite:///{settings.db_file}", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    settings.db_file.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
