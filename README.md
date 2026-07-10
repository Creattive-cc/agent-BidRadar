# 📡 BidRadar

> Agente autônomo de IA para descobrir licitações públicas, avaliar aderência ao perfil da empresa e apresentar as oportunidades em um dashboard web.

![Status](https://img.shields.io/badge/status-MVP-blue)
![Python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![GCP](https://img.shields.io/badge/Cloud_Run-4285F4?logo=googlecloud&logoColor=white)
![UV](https://img.shields.io/badge/uv-managed-DE5FE9)

---

## 📋 Sobre

Buscar editais públicos manualmente é caro, lento e impreciso. O **BidRadar** automatiza esse trabalho:

1. **Coleta** editais em portais públicos (PNCP, ComprasNet, BLL, ConLicitação) em ciclos agendados ou sob demanda via Pub/Sub.
2. **Analisa** cada edital com **Gemini** (Vertex AI) cruzando com o perfil da empresa.
3. **Pontua** a aderência (0–100), prioridade e gera justificativa textual.
4. **Apresenta** as oportunidades em um dashboard React.

O perfil da empresa é mantido em arquivos Markdown versionáveis em `company_profile/` — quem entende do negócio edita texto, o agente lê.

---

## 🧱 Stack

| Camada                | Tecnologia                                              |
| --------------------- | ------------------------------------------------------- |
| Backend / API         | FastAPI + Uvicorn                                       |
| Orquestração do agente | Python (`agent/runner.py`)                            |
| LLM                   | Vertex AI — Gemini 2.5 Pro (configurável)               |
| Scrapers              | Playwright + requests                                   |
| Persistência local    | SQLite (`data/licitacoes.db`) via SQLAlchemy            |
| Persistência cloud    | BigQuery, Cloud Storage, Firestore, Secret Manager      |
| Mensageria            | Cloud Pub/Sub (push subscription)                       |
| Frontend              | React 18 + Vite + Tailwind CSS                          |
| Container / Deploy    | Docker → Artifact Registry → Cloud Run (via Cloud Build) |
| Gerenciador Python    | [UV](https://github.com/astral-sh/uv) (Astral)          |

---

## 📁 Estrutura

```
agent-BidRadar/
├── agent/
│   ├── analyzer/          # gemini_analyzer.py — análise via Vertex AI (Gemini)
│   ├── scraper/           # pncp, comprasnet, bll, conlicitacao
│   ├── company_profile.py # leitura do perfil em .md
│   ├── config.py          # Settings (pydantic + env)
│   ├── downloader.py      # download de PDFs pendentes
│   ├── models.py          # SQLAlchemy models
│   ├── runner.py          # run_once() + run_forever()
│   └── ...
├── api/
│   └── main.py            # endpoints FastAPI
├── frontend/              # SPA React + Vite + Tailwind
├── company_profile/       # perfil da empresa em Markdown
├── data/                  # banco SQLite
├── logs/
├── Dockerfile             # build multi-stage com UV
├── cloudbuild.yaml        # pipeline Cloud Run
├── .env.example
├── pyproject.toml
└── uv.lock
```

---

## ⚙️ Pré-requisitos

- **Python 3.11+** (a imagem Docker usa 3.12)
- **UV**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Node.js 20+** e **npm** (para o frontend)
- **Projeto GCP** com APIs habilitadas: Vertex AI, BigQuery, Pub/Sub, Cloud Storage, Secret Manager
- **Service account** com permissões mínimas: `Vertex AI User`, `BigQuery Data Editor`, `Pub/Sub Publisher`, `Storage Object Admin`, `Secret Manager Secret Accessor`. Arquivo `service_account.json` na raiz do projeto.

---

## 🚀 Como rodar localmente

### 1) Backend + agente

```bash
git clone https://github.com/Creattive-cc/agent-BidRadar.git
cd agent-BidRadar

# cria virtualenv e instala dependências travadas no uv.lock
uv venv
source .venv/bin/activate
uv sync

# instala browsers do Playwright (necessário para scrapers)
uv run playwright install --with-deps chromium

# configura variáveis de ambiente
cp .env.example .env
# edite .env — pelo menos BIDRADAR_VERTEX_PROJECT_ID e ative algum scraper

# sobe a API
uv run uvicorn api.main:app --reload --port 8000
```

API: `http://localhost:8000` · Docs interativas: `http://localhost:8000/docs`

### 2) Frontend

Em outro terminal:

```bash
cd frontend
npm install
npm run dev
```

Vite sobe em `http://localhost:5173`.

### 3) Disparar o agente manualmente

```bash
curl -X POST http://localhost:8000/agent/run-once
```

### 4) Rodar o loop autônomo (sem API)

```bash
uv run python -m agent.runner
```

---

## 🔐 Configuração (`.env`)

### Ciclo do agente

| Variável                 | Default                | Descrição                              |
| ------------------------ | ---------------------- | -------------------------------------- |
| `BIDRADAR_INTERVAL_HOURS` | `6`                   | Intervalo entre ciclos do `run_forever` |
| `BIDRADAR_DB_PATH`       | `data/licitacoes.db`   | Caminho do SQLite                      |

### Scrapers (habilite os que for usar)

| Variável                          | Default | Observação                                        |
| --------------------------------- | :-----: | ------------------------------------------------- |
| `BIDRADAR_ENABLE_COMPRASNET`      | `false` | Wrapper sobre PNCP                                |
| `BIDRADAR_ENABLE_BLL`             | `false` | —                                                 |
| `BIDRADAR_ENABLE_CONLICITACAO`    | `false` | Requer credenciais no Secret Manager              |
| `BIDRADAR_PNCP_MODALIDADES`       | `1..12` | Códigos da Lei 14.133, separados por vírgula      |

### GCP — armazenamento e mensageria

| Variável                  | Default                          |
| ------------------------- | -------------------------------- |
| `BIDRADAR_GCP_PROJECT_ID` | `creattive-licitacoes-dev`       |
| `BIDRADAR_BQ_DATASET`     | `licitacoes`                     |
| `BIDRADAR_BQ_TABLE`       | `editais`                        |
| `BIDRADAR_PUBSUB_TOPIC`   | `coleta-editais`                 |

### Vertex AI (Gemini)

| Variável                       | Default                    | Descrição                              |
| ------------------------------ | -------------------------- | -------------------------------------- |
| `BIDRADAR_VERTEX_PROJECT_ID`   | —                          | Projeto que hospeda o Vertex            |
| `BIDRADAR_VERTEX_LOCATION`     | `us-central1`              |                                        |
| `BIDRADAR_VERTEX_MODEL`        | `gemini-2.5-pro`           | Ex.: `gemini-1.5-flash`, `gemini-2.5-pro` |
| `GOOGLE_GENAI_USE_VERTEXAI`    | `true`                     | Usar Vertex AI em vez da API pública    |
| `GOOGLE_CLOUD_PROJECT`         | —                          | Igual ao Vertex Project ID              |
| `GOOGLE_CLOUD_LOCATION`        | `us-central1`              |                                        |
| `GOOGLE_APPLICATION_CREDENTIALS` | `service_account.json`   | Path para o JSON do service account     |

A análise de aderência fica centralizada em `agent/analyzer/gemini_analyzer.py` (`score_bid_with_profile` para o ciclo do agente; `analyze_edital` para o fluxo Pub/Sub → BigQuery).

---

## 🔄 Fluxo do agente

```
                    ┌──────────────────────┐
                    │ company_profile/*.md │  ← fonte única da verdade
                    └──────────┬───────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
  ┌──────────┐           ┌──────────┐           ┌──────────────┐
  │ Scraper  │           │ Scraper  │     ...   │ Scraper      │
  │  PNCP    │           │  BLL     │           │ ConLicitação │
  └────┬─────┘           └────┬─────┘           └──────┬───────┘
       │                      │                        │
       └──────────────────────┼────────────────────────┘
                              ▼
                    ┌──────────────────┐
                    │   BigQuery       │
                    │ (editais brutos) │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Downloader       │  → Cloud Storage (PDFs)
                    │ download_pending │
                    └────────┬─────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
                ▼                         ▼
       ┌──────────────────┐      ┌──────────────────┐
       │ Pub/Sub trigger  │      │ Análise IA       │
       │ /pubsub/analisar │ ───▶ │ Gemini (Vertex)  │
       └──────────────────┘      └────────┬─────────┘
                                          │ score 0-100
                                          │ prioridade
                                          │ justificativa
                                          ▼
                                 ┌──────────────────┐
                                 │ SQLite local     │
                                 │ (cache do dash)  │
                                 └────────┬─────────┘
                                          │
                                          ▼
                                 ┌──────────────────┐
                                 │ Dashboard React  │
                                 └──────────────────┘
```

Se a chamada ao Vertex falhar, o edital recebe score 0 com justificativa de falha (sem travar o ciclo). Logs estruturados em `logs/agent.log`.

---

## 🌐 Endpoints

| Método | Rota                            | Descrição                                                  |
| ------ | ------------------------------- | ---------------------------------------------------------- |
| `GET`  | `/health`                       | Healthcheck                                                |
| `GET`  | `/licitacoes`                   | Lista editais analisados (ordenados por `created_at desc`)  |
| `GET`  | `/licitacoes/{id}`              | Detalhe de um edital                                       |
| `POST` | `/agent/run-once`               | Dispara um ciclo completo do agente                        |
| `GET`  | `/pubsub/health`                | Healthcheck do subscriber Pub/Sub                          |
| `POST` | `/pubsub/analisar`              | Receptor push do Pub/Sub (análise sob demanda por edital)  |
| `GET`  | `/company-profile/files`        | Lista arquivos `.md` do perfil                             |
| `GET`  | `/company-profile/{filename}`   | Lê um arquivo do perfil                                    |
| `PUT`  | `/company-profile/{filename}`   | Atualiza um arquivo do perfil                              |

Documentação interativa (OpenAPI): `http://localhost:8000/docs`.

---

## 🐳 Build & Deploy

### Build local da imagem

```bash
docker build -t bidradar-api:dev .
docker run --rm -p 8080:8080 \
  -e BIDRADAR_VERTEX_PROJECT_ID=seu-projeto \
  -v $(pwd)/service_account.json:/app/service_account.json:ro \
  bidradar-api:dev
```

### Deploy em Cloud Run (via Cloud Build)

O arquivo `cloudbuild.yaml` já está pronto. Cada execução faz:

1. Build da imagem Docker
2. Push para Artifact Registry: `us-central1-docker.pkg.dev/$PROJECT_ID/bidradar/api`
3. Deploy em Cloud Run no serviço `bidradar-api` (`us-central1`, 512Mi, 1 vCPU, 0–3 instâncias)

Execução manual:

```bash
gcloud builds submit --config=cloudbuild.yaml
```

O serviço sobe com `--no-allow-unauthenticated`. Para chamar de fora, gere um token:

```bash
TOKEN=$(gcloud auth print-identity-token)
curl -H "Authorization: Bearer $TOKEN" https://bidradar-api-XXXX.run.app/health
```

---

## 🛠️ Troubleshooting

**Vertex AI falha**
→ Verifique `service_account.json`, role `Vertex AI User`, `BIDRADAR_VERTEX_PROJECT_ID` e `GOOGLE_GENAI_USE_VERTEXAI=true`. Editais com falha de análise ficam com score 0.

**Scraper retorna lista vazia**
→ Confirme que o `BIDRADAR_ENABLE_*` correspondente está em `true`. ConLicitação exige credenciais no Secret Manager. Para PNCP, verifique se `BIDRADAR_PNCP_MODALIDADES` tem códigos válidos.

**`uv sync` falha**
→ `uv python install 3.11` e `uv venv --python 3.11`.

**Playwright reclama de browser ausente**
→ `uv run playwright install --with-deps chromium`.

**Pub/Sub push retorna 400**
→ Mensagem precisa estar em `base64` com JSON contendo `edital_id` e `numero`. Erros de negócio retornam 200 propositalmente para evitar reentrega.

---

## 🗺️ Roadmap

- [x] **Sprint 1** — Fundação & Infra GCP (Cloud Run, BigQuery, Pub/Sub, Secret Manager)
- [ ] **Sprint 2** — Crawlers PNCP e ConLicitação completos
- [ ] **Sprint 3** — Análise IA com RAG sobre `company_profile`
- [ ] **Sprint 4** — Interface Web MVP (Dashboard, Oportunidades, Filtros, Logs)
- [ ] **Sprint 5** — Notificações por e-mail, controle operacional (pausar/retomar), gestão de usuários (Firebase Auth), monitoring

---

## 📄 Licença

Projeto interno Creattive. Uso e distribuição restritos.
