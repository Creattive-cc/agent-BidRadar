from datetime import datetime
from sqlalchemy import create_engine, String, Float, DateTime, Integer, Text
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


engine = create_engine(f"sqlite:///{settings.db_file}", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    settings.db_file.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
