from pydantic import BaseModel


class ScrapedBid(BaseModel):
    title: str
    agency: str
    estimated_value: float | None = None
    deadline: str | None = None
    data_publicacao: str | None = None
    data_inicio_propostas: str | None = None
    data_abertura_propostas: str | None = None
    url: str
    source_site: str
    find_time_seconds: float = 0.0


class DataPrazo(BaseModel):
    tipo: str
    data: str


class ItemPOC(BaseModel):
    descricao: str
    ano_escolar: str
    quantidade: str
    observacao: str


class DocumentoObrigatorio(BaseModel):
    nome: str
    exigido_no_edital: bool
    observacao: str


class AnalyzedBid(ScrapedBid):
    analysis_time_seconds: float
    score: float
    justification: str
    resumo: str | None = None
    datas_prazos: list[DataPrazo] = []
    itens_poc: list[ItemPOC] = []
    checklist_documentos: list[DocumentoObrigatorio] = []
    envolve_producao_conteudo: bool = False


class ChecklistItem(BaseModel):
    requisito: str
    atendido: bool
    observacao: str


class AnalysisResult(BaseModel):
    edital_id: str
    score: float
    prioridade: str
    resumo: str
    checklist: list[ChecklistItem]
    justificativa: str
    rag_context_used: bool
    datas_prazos: list[DataPrazo]
    exige_amostra_ou_poc: bool
    detalhe_amostra_poc: str
