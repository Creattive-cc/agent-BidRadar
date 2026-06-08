import json
import os
import re
import time
from typing import TypedDict


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
    from google import genai as gai
    from google.genai import types as gtypes

    if not settings.vertex_project_id:
        raise ValueError("Defina BIDRADAR_VERTEX_PROJECT_ID no .env para usar Vertex AI.")

    # Credenciais: service_account.json (dev local) ou ADC (Cloud Run / GKE).
    credentials = None
    credentials_file = settings.google_credentials_file
    if credentials_file.exists():
        from google.oauth2 import service_account as _sa
        credentials = _sa.Credentials.from_service_account_file(
            str(credentials_file.resolve()),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        logger.debug("Vertex AI: autenticando via %s", credentials_file)
    else:
        logger.debug("Vertex AI: service_account.json ausente — usando ADC")

    client_kwargs: dict = {
        "vertexai": True,
        "project": settings.vertex_project_id,
        "location": settings.vertex_location,
    }
    if credentials is not None:
        client_kwargs["credentials"] = credentials
    client = gai.Client(**client_kwargs)

    class _BidScoreSchema(TypedDict):
        score: float
        justification: str

    profile_text = "\n\n".join(f"## {name}\n{content}" for name, content in profile_docs.items())
    base_prompt = f"""Voce e um analista de licitacoes publicas.
Avalie aderencia da licitacao ao perfil da empresa.
Regras:
- score: numero decimal de 0 a 100
- justification: texto detalhado em portugues (minimo 20 caracteres) explicando o score

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

    # Desliga thinking para reduzir latência (~7s → <3s) — só funciona no Flash
    _is_flash = "flash" in settings.vertex_model.lower()
    try:
        if _is_flash:
            _thinking = gtypes.ThinkingConfig(thinking_budget=0)
            _gen_config = gtypes.GenerateContentConfig(
                temperature=0,
                max_output_tokens=2048,
                response_mime_type="application/json",
                response_schema=_BidScoreSchema,
                thinking_config=_thinking,
            )
            _fallback_config = gtypes.GenerateContentConfig(
                temperature=0, max_output_tokens=2048, thinking_config=_thinking
            )
        else:
            _gen_config = gtypes.GenerateContentConfig(
                temperature=0,
                max_output_tokens=2048,
                response_mime_type="application/json",
                response_schema=_BidScoreSchema,
            )
            _fallback_config = gtypes.GenerateContentConfig(temperature=0, max_output_tokens=2048)
    except (AttributeError, TypeError):
        _gen_config = gtypes.GenerateContentConfig(
            temperature=0,
            max_output_tokens=2048,
            response_mime_type="application/json",
            response_schema=_BidScoreSchema,
        )
        _fallback_config = gtypes.GenerateContentConfig(temperature=0, max_output_tokens=2048)

    last_err: Exception | None = None
    for attempt in range(1, LLM_MAX_ATTEMPTS + 1):
        try:
            suffix = "\n\nPreencha score E justification. Nao retorne vazio." if attempt > 1 else ""
            response = client.models.generate_content(
                model=settings.vertex_model,
                contents=base_prompt + suffix,
                config=_gen_config,
            )
            data = json.loads(response.text)
            score = float(data["score"])
            justification = str(data["justification"]).strip()
            if len(justification) < 3:
                raise ValueError("Justificativa muito curta.")
            return max(0.0, min(100.0, score)), justification
        except Exception as exc:
            last_err = exc
            logger.warning("Gemini tentativa %s/%s falhou: %s", attempt, LLM_MAX_ATTEMPTS, exc)

    # Fallback: pede JSON como texto simples (sem response_schema)
    json_tail = (
        '\n\nResponda APENAS uma linha JSON valida, sem markdown:\n'
        '{"score": <0-100>, "justification": "<texto em portugues>"}'
    )
    try:
        response = client.models.generate_content(
            model=settings.vertex_model,
            contents=base_prompt + json_tail,
            config=_fallback_config,
        )
        return _parse_score_json_text(response.text)
    except Exception as exc:
        logger.warning("Gemini fallback JSON-text falhou: %s (ultimo: %s)", exc, last_err)
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
