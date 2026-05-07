import json
import os
import re
import time

from pydantic import BaseModel, Field

from agent.config import settings
from agent.logging_utils import get_logger
from agent.schemas import AnalyzedBid, ScrapedBid

logger = get_logger("bidradar.analyzer")

LLM_MAX_ATTEMPTS = 3


def _heuristic_score(bid: ScrapedBid, profile_docs: dict[str, str]) -> tuple[float, str]:
    haystack = "\n".join(profile_docs.values()).lower()
    title = bid.title.lower()

    positive_keywords = ["ti", "suporte", "sistema", "dados", "bi", "software", "cloud", "analise"]
    negative_keywords = ["obra civil", "medicamento", "merenda", "transporte escolar"]

    score = 35.0

    for keyword in positive_keywords:
        if keyword in title and keyword in haystack:
            score += 10

    for keyword in negative_keywords:
        if keyword in title:
            score -= 25

    score = max(0.0, min(100.0, score))

    if score >= 75:
        rationale = "Alta aderencia: objeto alinhado com servicos e experiencia descritos no perfil."
    elif score >= 45:
        rationale = "Aderencia moderada: existem pontos de compatibilidade, mas revisar escopo e restricoes."
    else:
        rationale = "Baixa aderencia: pouco alinhamento com as areas de atuacao e/ou possiveis restricoes."

    return score, rationale


def _parse_score_json_text(raw: str) -> tuple[float, str]:
    cleaned = raw.strip()
    if isinstance(raw, list):
        cleaned = "".join(str(p) for p in raw).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL | re.IGNORECASE)
        if fence:
            data = json.loads(fence.group(1))
        else:
            brace = re.search(r"(\{[^{}]*\"score\"[^{}]*\})", cleaned, re.DOTALL)
            if not brace:
                brace = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if not brace:
                raise ValueError("JSON nao encontrado na resposta.")
            data = json.loads(brace.group(1))
    score = float(data["score"])
    justification = str(data["justification"])
    return max(0.0, min(100.0, score)), justification


def _vertex_gemini_score(bid: ScrapedBid, profile_docs: dict[str, str]) -> tuple[float, str]:
    from langchain_google_genai import ChatGoogleGenerativeAI

    class BidScoreOutput(BaseModel):
        score: float = Field(ge=0, le=100)
        justification: str = Field(min_length=3)

    credentials_file = settings.google_credentials_file
    if not credentials_file.exists():
        raise FileNotFoundError(
            f"Arquivo de credenciais nao encontrado: {credentials_file.as_posix()}"
        )

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_file.resolve())
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"

    if not settings.vertex_project_id:
        raise ValueError("Defina BIDRADAR_VERTEX_PROJECT_ID no .env para usar Vertex AI.")
    os.environ["GOOGLE_CLOUD_PROJECT"] = settings.vertex_project_id
    os.environ["GOOGLE_CLOUD_LOCATION"] = settings.vertex_location

    llm = ChatGoogleGenerativeAI(
        model=settings.vertex_model,
        temperature=0,
        max_tokens=512,
    )
    structured_llm = llm.with_structured_output(BidScoreOutput)

    profile_text = "\n\n".join(f"## {name}\n{content}" for name, content in profile_docs.items())
    base_prompt = f"""Voce e um analista de licitacoes publicas.
Avalie aderencia da licitacao ao perfil da empresa.
Regras:
- score: numero decimal de 0 a 100
- justification: texto curto em portugues (minimo 10 caracteres)

Perfil da empresa:
{profile_text}

Licitacao:
- titulo: {bid.title}
- orgao: {bid.agency}
- valor_estimado: {bid.estimated_value}
- prazo: {bid.deadline}
- url: {bid.url}
- origem: {bid.source_site}
"""

    last_err: Exception | None = None
    for attempt in range(1, LLM_MAX_ATTEMPTS + 1):
        try:
            suffix = (
                "\n\nObrigatorio: preencha score e justification. Nao retorne objeto vazio."
                if attempt > 1
                else ""
            )
            response = structured_llm.invoke(base_prompt + suffix)
            if response is None:
                raise ValueError("Resposta estruturada vazia (None).")
            if not isinstance(response, BidScoreOutput):
                raise ValueError(f"Tipo de resposta inesperado: {type(response)}")
            score = float(response.score)
            justification = str(response.justification).strip()
            if len(justification) < 3:
                raise ValueError("Justificativa muito curta.")
            return max(0.0, min(100.0, score)), justification
        except Exception as exc:
            last_err = exc
            logger.warning("Gemini structured tentativa %s/%s falhou: %s", attempt, LLM_MAX_ATTEMPTS, exc)

    json_tail = (
        '\n\nResponda APENAS uma linha JSON valida, sem markdown, neste formato exato:\n'
        '{"score": <0-100>, "justification": "<texto>"}'
    )
    try:
        raw = llm.invoke(base_prompt + json_tail).content
        if isinstance(raw, list):
            raw = "".join(str(p) for p in raw)
        return _parse_score_json_text(str(raw))
    except Exception as exc:
        logger.warning("Gemini fallback JSON-text falhou: %s (ultimo structured: %s)", exc, last_err)
        raise last_err or exc


def score_bid_with_profile(bid: ScrapedBid, profile_docs: dict[str, str]) -> AnalyzedBid:
    start = time.perf_counter()

    try:
        if settings.llm_provider.lower() == "vertex_gemini":
            score, rationale = _vertex_gemini_score(bid, profile_docs)
        else:
            score, rationale = _heuristic_score(bid, profile_docs)
    except Exception as exc:
        logger.warning("Falha no analisador LLM (%s). Usando fallback heuristico.", exc)
        score, rationale = _heuristic_score(bid, profile_docs)

    analysis_time = time.perf_counter() - start
    return AnalyzedBid(
        **bid.model_dump(),
        analysis_time_seconds=analysis_time,
        score=round(score, 2),
        justification=rationale,
    )
