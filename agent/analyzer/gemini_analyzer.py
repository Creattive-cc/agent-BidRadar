import time
from datetime import datetime, timezone
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.cloud import bigquery
from google.genai import types
from pydantic import BaseModel, ValidationError

from agent.config import settings
from agent.logging_utils import get_logger
from agent.schemas import AnalysisResult, ChecklistItem

logger = get_logger("bidradar.analyzer.gemini")

# Lazy init GCP client
_bq_client: Any = None


def _get_bq() -> bigquery.Client | None:
    """Lazy-inits and returns the BigQuery client. Returns None if unavailable."""
    global _bq_client
    if _bq_client is None:
        try:
            _bq_client = bigquery.Client(project=settings.gcp_project_id)
        except Exception as exc:
            exc_str = str(exc)
            if any(
                k in exc_str
                for k in ("JWT", "oauth2", "credentials", "UNAUTHENTICATED")
            ):
                logger.debug(
                    "BigQuery client unavailable (local credentials missing): %s",
                    exc_str[:120],
                )
            else:
                logger.warning("Failed to initialize BigQuery client: %s", exc)
            return None
    return _bq_client


def _save_analysis_bq(result: AnalysisResult) -> None:
    """Saves the analysis result to a BigQuery table as a JSON object."""
    bq = _get_bq()
    if not bq:
        logger.debug(
            "BigQuery client not available, skipping analysis save for edital %s.",
            result.edital_id,
        )
        return

    table_id = f"{settings.gcp_project_id}.{settings.bigquery_dataset}.analises"
    row_to_insert = {
        "edital_id": result.edital_id,
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        "analysis_data": result.model_dump_json(),
        "score": result.score,
        "prioridade": result.prioridade,
    }

    try:
        errors = bq.insert_rows_json(table_id, [row_to_insert])
        if errors:
            logger.error(
                "BigQuery insert errors for edital %s: %s", result.edital_id, errors
            )
        else:
            logger.info("Analysis for edital %s saved to BigQuery.", result.edital_id)
    except Exception as exc:
        logger.error(
            "Failed to save analysis to BigQuery for edital %s: %s",
            result.edital_id,
            exc,
        )


class AnalysisResultInternal(BaseModel):
    """Schema for the data returned by the LLM, without manually added fields."""

    score: float
    prioridade: str
    resumo: str
    checklist: list[ChecklistItem]
    justificativa: str


def _run_agent(agent: LlmAgent, user_prompt: str) -> dict | None:
    """Executa o agente ADK e retorna o dict do resultado ou None em caso de falha."""
    try:
        session_service = InMemorySessionService()
        session = session_service.create_session_sync(
            app_name="bidradar", user_id="system"
        )
        runner = Runner(
            agent=agent,
            app_name="bidradar",
            session_service=session_service,
        )
        for event in runner.run(
            user_id="system",
            session_id=session.id,
            new_message=types.Content(
                role="user", parts=[types.Part(text=user_prompt)]
            ),
        ):
            pass  # consumir eventos
        final = session_service.get_session_sync(
            app_name="bidradar", user_id="system", session_id=session.id
        )
        return final.state.get("analysis")
    except Exception as exc:
        logger.error("ADK runner falhou: %s", exc)
        return None


def analyze_edital(
    edital_id: str,
    pdf_text: str,
    bid_metadata: dict,
    company_profile: str,
    rag_context: str | None = None,
) -> AnalysisResult:
    """
    Analyzes a bid using Google ADK LlmAgent to determine adherence.
    """
    max_retries = 3
    retry_delay = 1  # seconds

    system_prompt = """Você é um analista de licitações sênior da empresa INX/Creattive. Sua tarefa é analisar o texto de um edital de licitação, cruzá-lo com o perfil da empresa e o contexto RAG fornecido, e gerar uma análise estruturada em JSON.

Regras da Análise:
1.  **Score (0-100):** Calcule um score de aderência. O score é a porcentagem de requisitos críticos e desejáveis atendidos, ponderado pela importância de cada um.
    - Requisitos obrigatórios não atendidos (certificações, exclusividade ME/EPP, etc.) devem reduzir drasticamente o score.
    - Leve em conta a experiência prévia da empresa no setor (ex: prefeituras, educação).
2.  **Prioridade:**
    - "alta": score >= 85
    - "media": score >= 60 e < 85
    - "baixa": score < 60
3.  **Resumo:** Crie um resumo conciso contendo:
    - Objeto da licitação.
    - Principais exigências técnicas (funcionalidades, certificações).
    - Riscos potenciais (prazos curtos, multas altas, requisitos ambíguos).
    - Prazo para impugnação, se encontrado.
4.  **Checklist (mínimo 3, máximo 10 itens):** Identifique os requisitos mais importantes do edital. Para cada um, avalie se a empresa atende.
    - `requisito`: Descrição clara do requisito do edital.
    - `atendido`: `true` ou `false`.
    - `observacao`: Justificativa curta para o status de atendimento.
5.  **Justificativa:** Explique o porquê do score atribuído, conectando os pontos fortes e fracos do perfil da empresa com as exigências do edital.
6.  **rag_context_used**: Retorne `true` se o contexto RAG foi usado, `false` se foi usado o mock.

O output DEVE ser um único objeto JSON válido, sem nenhum texto ou formatação adicional."""

    rag_context_used = rag_context is not None
    if not rag_context_used:
        rag_context = """[CONTEXTO MOCK - substituir pelo Vertex AI Search no ID-42]
A empresa oferece plataforma SaaS de gestão escolar com módulos de:
matrícula, frequência, notas, comunicação escola-família, relatórios MEC.
Experiência comprovada em prefeituras e secretarias de educação.
Certificações: ISO 27001, LGPD compliance."""

    user_prompt = f"""Analise o seguinte edital com base no perfil da empresa e no contexto RAG.

## Perfil da Empresa
{company_profile}

## Contexto RAG
{rag_context}

## Metadados do Edital
- Objeto: {bid_metadata.get("objetoCompra", "Não informado")}
- Valor Estimado: {bid_metadata.get("valorTotalEstimado", "Não informado")}
- Modalidade: {bid_metadata.get("modalidadeNome", "Não informado")}
- Órgão: {bid_metadata.get("orgao", "Não informado")}

## Texto do Edital (parcial ou completo)
```
{pdf_text or "O texto completo do edital não foi fornecido para esta análise. Baseie-se nos metadados e no contexto."}
```

Gere a análise em formato JSON conforme as regras do sistema."""

    agent = LlmAgent(
        name="bid_analyzer",
        model=settings.vertex_model,
        instruction=system_prompt,
        output_schema=AnalysisResultInternal,
        output_key="analysis",
    )

    result_dict = None
    for attempt in range(1, max_retries + 1):
        result_dict = _run_agent(agent, user_prompt)
        if result_dict:
            break
        logger.warning(
            "Tentativa %d/%d sem resultado para edital %s",
            attempt,
            max_retries,
            edital_id,
        )
        if attempt < max_retries:
            time.sleep(retry_delay)

    if result_dict:
        try:
            result_dict["edital_id"] = edital_id
            result_dict["rag_context_used"] = rag_context_used
            analysis_result = AnalysisResult.model_validate(result_dict)
            _save_analysis_bq(analysis_result)
            return analysis_result
        except ValidationError as exc:
            logger.error(
                "Falha ao validar resultado do ADK para edital %s: %s", edital_id, exc
            )

    logger.error(
        "Falha total na análise automática do edital %s após %d tentativas.",
        edital_id,
        max_retries,
    )
    fallback_result = AnalysisResult(
        edital_id=edital_id,
        score=0.0,
        prioridade="baixa",
        resumo="A análise automática falhou em processar este edital.",
        checklist=[],
        justificativa="Falha na análise automática. O modelo de IA não conseguiu gerar uma resposta válida.",
        rag_context_used=rag_context_used,
    )
    _save_analysis_bq(fallback_result)
    return fallback_result
