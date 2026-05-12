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


class ChecklistItem(BaseModel):
    requisito: str  # descrição do requisito do edital
    atendido: bool  # a empresa atende?
    observacao: str  # justificativa curta


class AnalysisResult(BaseModel):
    edital_id: str
    score: float  # 0-100
    prioridade: str  # "alta" (>=85), "media" (>=60), "baixa" (<60)
    resumo: str  # objeto, exigências técnicas, riscos, prazo impugnação
    checklist: list[ChecklistItem]  # mín 3, máx 10 itens
    justificativa: str  # por que esse score
    rag_context_used: bool  # True quando RAG real, False quando mock
