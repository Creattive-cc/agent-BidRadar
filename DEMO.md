# 🎬 BidRadar — Demo para apresentação (Streamlit + Cloud Run)

Versão funcional **enxuta** para mostrar o agente rodando ponta-a-ponta:
**coleta (PNCP) → análise de aderência → dashboard**. Reusa o código real
de `agent/`. Não substitui a Interface Web oficial (Jira **ID-30**, React) —
é um *demo runner* publicável em Cloud Run com URL própria.

## Arquivos desta demo

- `streamlit_app.py` — app da demo (reusa `agent/`)
- `requirements-demo.txt` — deps mínimas (build rápido)
- `Dockerfile.demo` — imagem leve para Cloud Run
- `cloudbuild-demo.yaml` — build + deploy automatizados
- `deploy-demo.sh` — atalho de 1 comando
- `.streamlit/config.toml` — tema e porta

## Rodar localmente (uv)

```bash
# na raiz do repo agent-BidRadar
uv venv
. .venv/bin/activate.fish        # fish; em bash use: source .venv/bin/activate
uv pip install -r requirements-demo.txt
streamlit run streamlit_app.py
```

Abre em `http://localhost:8501`. Na barra lateral:
1. **Fonte**: comece com *Dados de exemplo (offline)* — sempre funciona.
2. Clique em **Rodar agente**. Para dados reais, troque para *PNCP ao vivo*.

> A demo desabilita os scrapers de navegador (BLL/ConLicitação) e usa só o
> **PNCP** (API pública). Por isso não precisa de Playwright/Chromium nem GCP.

## Publicar no Cloud Run

Pré-requisitos: `gcloud` autenticado (`gcloud auth login`) e um projeto GCP.

```bash
chmod +x deploy-demo.sh
./deploy-demo.sh SEU_PROJECT_ID            # região padrão us-central1
# ou: ./deploy-demo.sh SEU_PROJECT_ID southamerica-east1
```

Ao final, o script imprime a **URL pública** (`--allow-unauthenticated`) para o
Diego abrir direto no navegador, sem login.

Equivalente manual:

```bash
gcloud builds submit --config=cloudbuild-demo.yaml \
  --substitutions=_REGION=us-central1
```

## Modo de análise

- **Heurística** (padrão): palavras-chave do perfil × objeto do edital. Sem
  credenciais, instantâneo — ideal para a apresentação.
- **Gemini / Vertex AI**: selecione na barra lateral. Requer `service_account.json`
  e as libs do projeto principal (`langchain-google-genai`). Se indisponível,
  o agente **cai automaticamente** na heurística (nada quebra na frente do chefe).

## Editar o perfil da empresa

Aba **🏢 Perfil da empresa** lê/edita os `.md` de `company_profile/`. Quem entende
do negócio ajusta o texto; o agente reanalisa na próxima execução. É a “fonte
única da verdade” do match.

## Onde isso encaixa no projeto (Jira ID)

- **ID-28** Coleta de Editais → etapa de coleta (PNCP) da demo
- **ID-29** Análise IA → score + justificativa
- **ID-30** Interface Web → esta demo antecipa o dashboard (oficial será React)
- **ID-27** Infra GCP / Cloud Run → deploy desta demo
