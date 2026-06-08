#!/usr/bin/env python3
"""
Teste de integração Vertex AI — BidRadar.

Fase 1 — descoberta rápida (google-genai SDK, sem retry):
  Testa modelos: gemini-3.1-pro → gemini-3-pro → gemini-2.5-pro
  Para cada, testa regiões: us-central1 → global

Fase 2 — análise completa com score_bid_with_profile (LangChain).

Ao final, atualiza .env com modelo+região que funcionou.

Uso:
    uv run python scripts/test_gemini.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv, set_key

load_dotenv(ROOT / ".env")

PROJECT = os.environ.get("BIDRADAR_VERTEX_PROJECT_ID", "")
SA_PATH = ROOT / os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")

MODELS = ["gemini-3.1-pro", "gemini-3-pro", "gemini-2.5-pro"]
LOCATIONS = ["us-central1", "global"]

HEURISTIC_PHRASES = {
    "Alta aderencia: objeto alinhado com servicos e experiencia descritos no perfil.",
    "Aderencia moderada: existem pontos de compatibilidade, mas revisar escopo e restricoes.",
    "Baixa aderencia: pouco alinhamento com as areas de atuacao e/ou possiveis restricoes.",
}

print("=" * 60)
print("BidRadar — Teste de integração Vertex AI")
print(f"Projeto : {PROJECT}")
print(f"SA file : {SA_PATH} ({'encontrado' if SA_PATH.exists() else 'AUSENTE — ADC'})")
print("=" * 60)

# Configura credenciais antes de qualquer import GCP
if SA_PATH.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(SA_PATH.resolve())

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"


def _build_genai_credentials():
    """Retorna Credentials do SA ou None (ADC)."""
    if SA_PATH.exists():
        from google.oauth2 import service_account as _sa
        return _sa.Credentials.from_service_account_file(
            str(SA_PATH.resolve()),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
    return None


def probe_model(model: str, location: str) -> bool:
    """Teste mínimo (sem retry) via google-genai SDK. Retorna True se OK."""
    from google import genai as gai
    from google.genai import types as gtypes

    creds = _build_genai_credentials()
    client_kwargs = {"vertexai": True, "project": PROJECT, "location": location}
    if creds:
        client_kwargs["credentials"] = creds

    client = gai.Client(**client_kwargs)
    client.models.generate_content(
        model=model,
        contents="Responda apenas: OK",
        config=gtypes.GenerateContentConfig(max_output_tokens=10),
    )
    return True


# ── Fase 1: descoberta ──────────────────────────────────────────────────────
working_model: str | None = None
working_location: str | None = None

for model in MODELS:
    for location in LOCATIONS:
        os.environ["GOOGLE_CLOUD_LOCATION"] = location
        print(f"\n→ Testando  modelo={model}  location={location} ...")
        try:
            probe_model(model, location)
            print(f"  ✓ Resposta recebida!")
            working_model = model
            working_location = location
            break
        except Exception as exc:
            err = str(exc)
            if "404" in err or "NOT_FOUND" in err.upper() or "not found" in err.lower():
                print(f"  ✗ 404 — modelo não disponível nesta região")
            elif "403" in err or "PERMISSION" in err.upper() or "permission" in err.lower():
                print(f"  ✗ 403 — sem permissão (checar papel Vertex AI User na SA)")
                print(f"    {err[:200]}")
            else:
                print(f"  ✗ {err[:200]}")
    if working_model:
        break

if not working_model:
    print("\n❌  Nenhuma combinação modelo+região funcionou.")
    print("    Cheque: APIs habilitadas, papel 'Vertex AI User' na SA, cotas Vertex AI.")
    sys.exit(1)

print(f"\n{'='*60}")
print(f"Fase 1 OK — modelo={working_model}  location={working_location}")
print(f"{'='*60}")

# ── Fase 2: análise completa via score_bid_with_profile ─────────────────────
os.environ["BIDRADAR_LLM_PROVIDER"] = "vertex_gemini"
os.environ["BIDRADAR_VERTEX_MODEL"] = working_model
os.environ["BIDRADAR_VERTEX_LOCATION"] = working_location
os.environ["GOOGLE_CLOUD_LOCATION"] = working_location

from agent.config import settings  # noqa: E402 (depois dos env vars)
settings.llm_provider = "vertex_gemini"
settings.vertex_model = working_model
settings.vertex_location = working_location

from agent.company_profile import read_profile_files  # noqa: E402
from agent.schemas import ScrapedBid  # noqa: E402
from agent.analyzer.matcher import score_bid_with_profile  # noqa: E402

profile = read_profile_files()
print(f"Perfil carregado: {list(profile.keys())}")

bid = ScrapedBid(
    title="Implantação de Google Workspace e migração de infraestrutura para GCP "
          "com capacitação de equipe técnica",
    agency="Secretaria Municipal de Tecnologia de São Paulo",
    estimated_value=750000.0,
    deadline="2026-08-01T17:00:00",
    url="https://pncp.gov.br/app/editais/test/2026/999",
    source_site="PNCP",
)

print("\nAnalisando edital com Gemini Vertex AI...")
result = score_bid_with_profile(bid, profile)

if result.justification in HEURISTIC_PHRASES:
    print(f"\n⚠  Justificativa é frase heurística — LLM não respondeu como esperado.")
    print(f"   Score: {result.score}  Justificativa: {result.justification}")
    sys.exit(1)

print(f"\n🎯  Score        : {result.score}/100")
print(f"    Modelo       : {working_model} / {working_location}")
print(f"    Tempo        : {result.analysis_time_seconds:.1f}s")
print(f"    Justificativa:\n    {result.justification}")

# Atualiza .env
env_file = str(ROOT / ".env")
set_key(env_file, "BIDRADAR_VERTEX_MODEL", working_model)
set_key(env_file, "BIDRADAR_VERTEX_LOCATION", working_location)
print(f"\n.env atualizado:")
print(f"  BIDRADAR_VERTEX_MODEL={working_model}")
print(f"  BIDRADAR_VERTEX_LOCATION={working_location}")
