import json
import re
import time
from datetime import datetime, timezone
from typing import Any, TypedDict

from google.cloud import bigquery
from pydantic import BaseModel

from agent.config import settings
from agent.logging_utils import get_logger
from agent.schemas import (
    AnalysisResult,
    AnalyzedBid,
    ChecklistItem,
    DataPrazo,
    DocumentoObrigatorio,
    ItemPOC,
    ScrapedBid,
)

logger = get_logger("bidradar.analyzer.gemini")

LLM_MAX_ATTEMPTS = 3

_bq_client: Any = None


def _get_bq() -> bigquery.Client | None:
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


class _DataPrazoSchema(TypedDict):
    tipo: str
    data: str


class _ItemPOCSchema(TypedDict):
    descricao: str
    ano_escolar: str
    quantidade: str
    observacao: str


class _DocumentoObrigatorioSchema(TypedDict):
    nome: str
    exigido_no_edital: bool
    observacao: str


class _ChecklistItemSchema(TypedDict):
    requisito: str
    atendido: bool
    observacao: str


class _BidAnalysisSchema(TypedDict):
    score: float
    resumo: str
    justification: str
    datas_prazos: list[_DataPrazoSchema]
    itens_poc: list[_ItemPOCSchema]
    checklist_documentos: list[_DocumentoObrigatorioSchema]
    envolve_producao_conteudo: bool
    checklist: list[_ChecklistItemSchema]


class AnalysisResultInternal(BaseModel):
    score: float
    resumo: str
    justification: str
    datas_prazos: list[DataPrazo]
    itens_poc: list[ItemPOC]
    checklist_documentos: list[DocumentoObrigatorio]
    envolve_producao_conteudo: bool
    checklist: list[ChecklistItem]


def _prioridade_from_score(score: float) -> str:
    if score >= 85:
        return "alta"
    if score >= 60:
        return "media"
    return "baixa"


def _create_genai_client():
    from google import genai as gai

    if not settings.vertex_project_id:
        raise ValueError("Defina BIDRADAR_VERTEX_PROJECT_ID no .env para usar Vertex AI.")

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
    return gai.Client(**client_kwargs)


def _build_base_prompt(
    company_profile: str,
    pdf_text: str | None,
    *,
    bid_title: str | None = None,
    bid_agency: str | None = None,
    bid_value: str | float | None = None,
    bid_deadline: str | None = None,
    bid_url: str | None = None,
    bid_source: str | None = None,
    bid_metadata: dict | None = None,
    rag_context: str | None = None,
) -> str:
    _pdf_section = ""
    if pdf_text:
        _pdf_text_truncated = pdf_text[:12000]
        _pdf_section = f"\n\nConteudo extraido do edital (PDF):\n{_pdf_text_truncated}\n"

    if bid_metadata:
        licitacao_section = f"""Licitacao a analisar:
- objeto: {bid_metadata.get("objetoCompra", "Não informado")}
- valor_estimado: {bid_metadata.get("valorTotalEstimado", "Não informado")}
- modalidade: {bid_metadata.get("modalidadeNome", "Não informado")}
- orgao: {bid_metadata.get("orgao", "Não informado")}
{_pdf_section}"""
    else:
        licitacao_section = f"""Licitacao a analisar:
- titulo: {bid_title or "Não informado"}
- orgao: {bid_agency or "Não informado"}
- valor_estimado: {bid_value if bid_value is not None else "Não informado"}
- prazo: {bid_deadline or "Não informado"}
- url: {bid_url or "Não informado"}
- origem: {bid_source or "Não informado"}
{_pdf_section}"""

    rag_section = ""
    if rag_context:
        rag_section = f"\n\n## Contexto RAG\n{rag_context}\n"

    return f"""Voce e um analista senior de licitacoes publicas com 15 anos de experiencia, avaliando oportunidades para uma empresa de tecnologia educacional.

**Regras anti-alucinacao (obrigatorias):**
- Baseie-se EXCLUSIVAMENTE no texto do edital (pdf_text) e no perfil da empresa fornecidos.
- NUNCA infira sistemas, produtos, siglas ou avaliacoes (ex.: SAEB) que nao estejam EXPLICITAMENTE escritos no texto do edital.
- Ausencia de informacao = "nao informado", nunca suposicao.
- Nos campos resumo e justification, e proibido citar produtos, sistemas ou siglas que nao aparecam literalmente no texto do edital analisado.

Retorne um JSON com os campos abaixo:

1. "score" (0-100): aderencia do edital ao perfil da empresa.
   - 90-100: objeto identico ao core da empresa, habilitacao alcancavel, sem impeditivos
   - 70-89: alta aderencia, 1-2 pontos de atencao superaveis
   - 50-69: aderencia parcial, riscos relevantes a avaliar antes de decidir
   - 30-49: baixa aderencia, apenas tangencia a atuacao da empresa
   - 0-29: sem aderencia ou com impedimento real (obra civil, saude, transporte, exclusivo fabricante, etc.)

2. "resumo" (3-5 frases): descricao executiva do edital.
   - O que exatamente esta sendo contratado e para qual finalidade
   - Principais funcionalidades ou entregas esperadas
   - Modalidade, valor estimado e prazo de vigencia ou implantacao
   - Perfil do orgao contratante e contexto da necessidade

3. "justification" (minimo 800 caracteres, estruturado em topicos): analise aprofundada cobrindo TODOS os itens abaixo.

   1. OBJETO E ESCOPO
      Descreva com precisao o que sera entregue: sistema, servico, consultoria, licenca, implantacao, treinamento, suporte. Quantas unidades, usuarios, localidades. Identifique se e fornecimento de solucao propria ou revenda.

   2. ADERENCIA AO PERFIL
      Quais produtos ou servicos do portfolio da empresa atendem diretamente ao objeto. Cite funcionalidades especificas que coincidem. Avalie se e fit total, parcial ou superficial.

   3. HABILITACAO TECNICA
      Liste os atestados de capacidade tecnica exigidos (quantidades, valores, prazos). Indique se a empresa provavelmente possui ou precisaria buscar. Mencione certificacoes, registros ou declaracoes especificas exigidas.

   4. HABILITACAO ECONOMICO-FINANCEIRA
      Capital social minimo exigido (se informado). Indices financeiros (liquidez, endividamento). Seguro-garantia ou caucao. Avalie se sao barreiras reais.

   5. DIFERENCIAIS COMPETITIVOS
      O que a empresa tem de diferencial para este edital: experiencia no setor publico, integracao com sistemas governamentais, referencias em orgaos similares, certificacoes relevantes, equipe tecnica especializada.

   6. RISCOS E PONTOS DE ATENCAO
      Requisitos tecnicos que podem nao ser atendidos. Prazos de implantacao agressivos. Penalidades contratuais elevadas. SLA exigente. Dependencia de terceiros. Restricoes geograficas. Clausulas de exclusividade de fabricante.

   7. COMPETITIVIDADE E MERCADO
      Tipo de disputa: ME/EPP exclusivo, ampla concorrencia, sistema de registro de preco, ata vigente. Estimativa de concorrentes potenciais. Nivel de dificuldade para vencer.

   8. RECOMENDACAO FINAL
      Decisao clara: PARTICIPAR / AVALIAR MELHOR / DESCARTAR. Justifique em 2-3 frases. Se "avaliar melhor", liste exatamente o que precisa ser verificado antes de decidir.

   Seja cirurgico — cite nomes de sistemas, modulos, orgaos, CNAEs, valores e prazos reais quando disponiveis. Evite generalizacoes.

4. "datas_prazos": lista de {{"tipo", "data"}} — todas as datas/prazos explicitos do edital (sessao publica, impugnacao, entrega de amostra/POC, vigencia, entrega de proposta). Use "nao informado" quando ausente, nunca inventar.

5. "itens_poc": lista de {{"descricao", "ano_escolar", "quantidade", "observacao"}} — detalhamento de exigencias de amostra fisica/POC/kits didaticos, incluindo volumetria e segmento/ano escolar quando informado no edital. Lista vazia se nao houver exigencia.

6. "checklist_documentos": lista de {{"nome", "exigido_no_edital", "observacao"}} — verificacao explicita da presenca de: "cronograma executivo", "plano fisico-financeiro", "atestado de capacidade tecnica", "prazo para entrega de propostas", "garantia contratual", mais outros documentos obrigatorios citados no edital.

7. "envolve_producao_conteudo": bool — true se o objeto envolve criacao/producao de material didatico/conteudo pedagogico/kits impressos (nao apenas licenciamento de software).

8. "checklist": lista de {{"requisito", "atendido", "observacao"}} (minimo 3, maximo 10 itens) — requisitos mais importantes do edital avaliados contra o perfil da empresa.

Perfil da empresa:
{company_profile}
{rag_section}
{licitacao_section}"""


def _build_gen_configs(gtypes):
    _is_flash = "flash" in settings.vertex_model.lower()
    try:
        if _is_flash:
            _thinking = gtypes.ThinkingConfig(thinking_budget=0)
            gen_config = gtypes.GenerateContentConfig(
                temperature=0,
                max_output_tokens=8192,
                response_mime_type="application/json",
                response_schema=_BidAnalysisSchema,
                thinking_config=_thinking,
            )
            fallback_config = gtypes.GenerateContentConfig(
                temperature=0, max_output_tokens=8192, thinking_config=_thinking
            )
        else:
            gen_config = gtypes.GenerateContentConfig(
                temperature=0,
                max_output_tokens=8192,
                response_mime_type="application/json",
                response_schema=_BidAnalysisSchema,
            )
            fallback_config = gtypes.GenerateContentConfig(
                temperature=0, max_output_tokens=4096
            )
    except (AttributeError, TypeError):
        gen_config = gtypes.GenerateContentConfig(
            temperature=0,
            max_output_tokens=8192,
            response_mime_type="application/json",
            response_schema=_BidAnalysisSchema,
        )
        fallback_config = gtypes.GenerateContentConfig(
            temperature=0, max_output_tokens=4096
        )
    return gen_config, fallback_config


def _parse_analysis_response(data: dict) -> AnalysisResultInternal:
    score = float(data["score"])
    justification = str(data["justification"]).strip()
    resumo = str(data.get("resumo", "")).strip()
    if len(justification) < 20:
        raise ValueError("Justificativa muito curta.")

    return AnalysisResultInternal(
        score=max(0.0, min(100.0, score)),
        resumo=resumo,
        justification=justification,
        datas_prazos=[DataPrazo.model_validate(d) for d in data.get("datas_prazos", [])],
        itens_poc=[ItemPOC.model_validate(i) for i in data.get("itens_poc", [])],
        checklist_documentos=[
            DocumentoObrigatorio.model_validate(c)
            for c in data.get("checklist_documentos", [])
        ],
        envolve_producao_conteudo=bool(data.get("envolve_producao_conteudo", False)),
        checklist=[ChecklistItem.model_validate(c) for c in data.get("checklist", [])],
    )


def _parse_json_text(raw: str) -> dict:
    cleaned = raw.strip()
    if isinstance(raw, list):
        cleaned = "".join(str(p) for p in raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        fence = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL | re.IGNORECASE
        )
        if fence:
            return json.loads(fence.group(1))
        brace = re.search(r"(\{[^{}]*\"score\"[^{}]*\})", cleaned, re.DOTALL)
        if not brace:
            brace = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if not brace:
            raise ValueError("JSON nao encontrado na resposta.")
        return json.loads(brace.group(1))


def _vertex_gemini_analyze(
    company_profile: str,
    pdf_text: str | None = None,
    *,
    bid: ScrapedBid | None = None,
    bid_metadata: dict | None = None,
    rag_context: str | None = None,
) -> AnalysisResultInternal:
    from google.genai import types as gtypes

    client = _create_genai_client()

    if bid is not None:
        base_prompt = _build_base_prompt(
            company_profile,
            pdf_text,
            bid_title=bid.title,
            bid_agency=bid.agency,
            bid_value=bid.estimated_value,
            bid_deadline=bid.deadline,
            bid_url=bid.url,
            bid_source=bid.source_site,
            rag_context=rag_context,
        )
    else:
        base_prompt = _build_base_prompt(
            company_profile,
            pdf_text,
            bid_metadata=bid_metadata or {},
            rag_context=rag_context,
        )

    gen_config, fallback_config = _build_gen_configs(gtypes)

    last_err: Exception | None = None
    for attempt in range(1, LLM_MAX_ATTEMPTS + 1):
        try:
            suffix = (
                "\n\nPreencha TODOS os campos do JSON. Nao retorne vazio."
                if attempt > 1
                else ""
            )
            response = client.models.generate_content(
                model=settings.vertex_model,
                contents=base_prompt + suffix,
                config=gen_config,
            )
            return _parse_analysis_response(json.loads(response.text))
        except Exception as exc:
            last_err = exc
            logger.warning(
                "Gemini tentativa %s/%s falhou: %s", attempt, LLM_MAX_ATTEMPTS, exc
            )

    json_tail = (
        "\n\nResponda APENAS um JSON valido, sem markdown, com todos os campos: "
        "score, resumo, justification, datas_prazos, itens_poc, checklist_documentos, "
        "envolve_producao_conteudo, checklist."
    )
    try:
        response = client.models.generate_content(
            model=settings.vertex_model,
            contents=base_prompt + json_tail,
            config=fallback_config,
        )
        return _parse_analysis_response(_parse_json_text(response.text))
    except Exception as exc:
        logger.warning("Gemini fallback JSON-text falhou: %s (ultimo: %s)", exc, last_err)
        raise last_err or exc


def _detalhe_amostra_poc(itens_poc: list[ItemPOC]) -> str:
    if not itens_poc:
        return "nao aplicavel"
    parts = []
    for item in itens_poc:
        parts.append(
            f"{item.descricao} ({item.ano_escolar}, qtd: {item.quantidade}) — {item.observacao}"
        )
    return "; ".join(parts)


def score_bid_with_profile(
    bid: ScrapedBid,
    profile_docs: dict[str, str],
    pdf_text: str | None = None,
) -> AnalyzedBid:
    start = time.perf_counter()
    profile_text = "\n\n".join(f"## {name}\n{content}" for name, content in profile_docs.items())
    result = _vertex_gemini_analyze(profile_text, pdf_text, bid=bid)
    analysis_time = time.perf_counter() - start
    return AnalyzedBid(
        **bid.model_dump(),
        analysis_time_seconds=analysis_time,
        score=round(result.score, 2),
        justification=result.justification,
        resumo=result.resumo or None,
        datas_prazos=result.datas_prazos,
        itens_poc=result.itens_poc,
        checklist_documentos=result.checklist_documentos,
        envolve_producao_conteudo=result.envolve_producao_conteudo,
    )


def analyze_edital(
    edital_id: str,
    pdf_text: str,
    bid_metadata: dict,
    company_profile: str,
    rag_context: str | None = None,
) -> AnalysisResult:
    rag_context_used = rag_context is not None
    if not rag_context_used:
        rag_context = """[CONTEXTO MOCK - substituir pelo Vertex AI Search no ID-42]
A empresa oferece plataforma SaaS de gestao escolar com modulos de:
matricula, frequencia, notas, comunicacao escola-familia, relatorios MEC.
Experiencia comprovada em prefeituras e secretarias de educacao.
Certificacoes: ISO 27001, LGPD compliance."""

    try:
        result = _vertex_gemini_analyze(
            company_profile,
            pdf_text or None,
            bid_metadata=bid_metadata,
            rag_context=rag_context,
        )
        analysis_result = AnalysisResult(
            edital_id=edital_id,
            score=result.score,
            prioridade=_prioridade_from_score(result.score),
            resumo=result.resumo,
            checklist=result.checklist,
            justificativa=result.justification,
            rag_context_used=rag_context_used,
            datas_prazos=result.datas_prazos,
            exige_amostra_ou_poc=bool(result.itens_poc),
            detalhe_amostra_poc=_detalhe_amostra_poc(result.itens_poc),
        )
        _save_analysis_bq(analysis_result)
        return analysis_result
    except Exception as exc:
        logger.error(
            "Falha total na analise automatica do edital %s: %s",
            edital_id,
            exc,
        )
    fallback_result = AnalysisResult(
        edital_id=edital_id,
        score=0.0,
        prioridade="baixa",
        resumo="A analise automatica falhou em processar este edital.",
        checklist=[],
        justificativa="Falha na analise automatica. O modelo de IA nao conseguiu gerar uma resposta valida.",
        rag_context_used=rag_context_used,
        datas_prazos=[],
        exige_amostra_ou_poc=False,
        detalhe_amostra_poc="nao aplicavel",
    )
    _save_analysis_bq(fallback_result)
    return fallback_result
