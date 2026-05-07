from pydantic import BaseModel


class ScrapedBid(BaseModel):
    title: str
    agency: str
    estimated_value: float | None = None
    deadline: str | None = None
    url: str
    source_site: str
    find_time_seconds: float = 0.0


class AnalyzedBid(ScrapedBid):
    analysis_time_seconds: float
    score: float
    justification: str
