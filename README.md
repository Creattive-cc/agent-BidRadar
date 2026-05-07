# BidRadar

BidRadar e um agente autonomo de IA para buscar licitacoes publicas, analisar aderencia com o perfil da empresa e apresentar os resultados em um dashboard web simples.

## Stack

- Backend: FastAPI
- Agente: Python + LangChain/LangGraph (com fallback heuristico)
- Frontend: React + Tailwind
- Banco: SQLite local
- Gerenciador de pacotes: UV

## Estrutura

```
bidradar/
├── agent/
├── api/
├── frontend/
├── company_profile/
├── data/
├── logs/
├── pyproject.toml
└── README.md
```

## Como rodar

### 1) Backend + agente

```bash
cd bidradar
uv venv
source .venv/bin/activate
uv sync
cp .env.example .env
uv run uvicorn api.main:app --reload --port 8000
```

### 2) Frontend

```bash
cd bidradar/frontend
npm install
npm run dev
```

## Fluxo do agente

1. Le `company_profile/*.md` a cada ciclo (fonte unica da verdade)
2. Varre os scrapers ativos (ComprasNet e BLL)
3. Analisa aderencia (score 0-100 + justificativa)
4. Persiste em SQLite
5. Registra logs em `logs/agent.log`

## Configuracao Gemini Vertex AI

1. Garanta que o arquivo `service_account.json` esteja na raiz do projeto.
2. Copie `.env.example` para `.env`.
3. Preencha `BIDRADAR_VERTEX_PROJECT_ID`.
4. Mantenha `BIDRADAR_LLM_PROVIDER=vertex_gemini`.

Se a chamada ao Vertex falhar, o sistema usa fallback heuristico automaticamente.

## Endpoints principais

- `GET /health`
- `GET /licitacoes`
- `GET /licitacoes/{id}`
- `POST /agent/run-once`
- `GET /company-profile/files`
- `GET /company-profile/{filename}`
- `PUT /company-profile/{filename}`
# Sprint 1 - Infra GCP concluída
