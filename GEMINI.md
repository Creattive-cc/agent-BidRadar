# GEMINI.md — Contexto do Projeto BidRadar

Este arquivo fornece contexto para o Gemini Code Assist entender o projeto antes de
sugerir alterações. Leia-o integralmente antes de qualquer modificação de código.

---

## O que é o BidRadar

Agente autônomo para prospecção e análise de licitações públicas. O objetivo é
automatizar o processo que a equipe de licitação do Grupo Bringel (empresas Creattive e
INX) realiza manualmente hoje:

1. Acessar portais (PNCP, ConLicitação) e filtrar editais por palavras-chave
2. Descartar editais fora dos critérios (valor abaixo do mínimo, exclusivos para ME/EPP)
3. Baixar os PDFs dos editais aprovados
4. Analisar o edital e calcular % de aderência da plataforma da empresa aos requisitos
5. Notificar a equipe sobre oportunidades com alta aderência

A empresa **não é ME/EPP**, portanto editais com `tipoBeneficioId = 1`
(participação exclusiva para ME/EPP) devem ser descartados automaticamente.

---

## Stack Técnica

- **Linguagem:** Python 3.12 com UV (Astral) para gerenciamento de dependências
- **API:** FastAPI + Uvicorn
- **Banco local:** SQLAlchemy + SQLite (desenvolvimento)
- **GCP:** BigQuery (armazenamento de editais), GCS (PDFs), Pub/Sub (pipeline),
  Firestore (config em runtime), Cloud Run (deploy), Vertex AI + Gemini (análise IA)
- **Auth:** Firebase Auth (login e-mail/senha, perfis admin e analista)

---

## Estrutura de Arquivos

```
agent/
  config.py           — Settings via Pydantic + env vars. Usar sempre settings.*
  runner.py           — Orquestra scrapers → análise → download. Ponto de entrada do ciclo.
  downloader.py       — Download de PDFs e upload para GCS. Suporte especial para PNCP.
  scraper/
    pncp.py           — Scraper principal. Coleta do PNCP via API REST pública.
    comprasnet.py     — Scraper ComprasNet
    bll.py            — Scraper BLL
    conlicitacao.py   — Scraper ConLicitação (pausado: aguardando credenciais)
  analyzer/
    gemini_analyzer.py  — Análise de aderência edital × perfil (Vertex AI / Gemini)
                          score_bid_with_profile() → AnalyzedBid (runner, API)
                          analyze_edital() → AnalysisResult (Pub/Sub → BigQuery)
  company_profile.py  — Leitura dos arquivos .md do perfil da empresa (context RAG)
  models.py           — Modelos SQLAlchemy
  logging_utils.py    — get_logger("bidradar.modulo") — usar sempre este padrão
api/
  main.py             — FastAPI: endpoints REST + subscriber Pub/Sub
```

---

## APIs do PNCP

O PNCP tem **três bases de URL distintas** com propósitos diferentes:

| Base URL | Uso |
|---|---|
| `https://pncp.gov.br/api/consulta/v1/` | API pública de consulta (sem auth) |
| `https://pncp.gov.br/api/pncp/v1/` | API interna do portal (sem auth, descoberta via interceptação) |
| `https://pncp.gov.br/pncp-api/v1/` | Download de arquivos binários (sem auth) |

### Endpoints utilizados

```
# Listar contratações por data de publicação
GET /api/consulta/v1/contratacoes/publicacao
  ?dataInicial=AAAAMMDD&dataFinal=AAAAMMDD&codigoModalidadeContratacao=6&pagina=1

# Dados completos de uma contratação
GET /api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}

# Listar arquivos de um edital
GET /api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos
  ?pagina=1&tamanhoPagina=50
  → Retorna: lista direta (não objeto com "data") — ATENÇÃO: não usar data.get("data", [])

# Baixar arquivo binário (PDF)
GET /pncp-api/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos/{sequencialDocumento}
  → Content-Type: application/octet-stream
```

### Parsing do numeroControlePNCP

```python
# Formato: "05472936000139-1-000082/2026"
#           CNPJ            tipo  seq   ano
#                            ↑ ignorar na URL

def _pncp_portal_url(numero_controle: str) -> str:
    parts = numero_controle.split("-")
    cnpj = parts[0]
    sequencial, ano = parts[2].split("/")
    return f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{int(sequencial)}"

# URL portal:  https://pncp.gov.br/app/editais/05472936000139/2026/82
# URL API:     https://pncp.gov.br/api/consulta/v1/orgaos/05472936000139/compras/2026/82
```

### Endpoints que NÃO existem na API pública de Consultas

`/documentos`, `/arquivos`, `/itens` como sub-path da API de consulta resultam em
timeout — esses endpoints pertencem à API de Integração autenticada. Usar sempre
`/api/pncp/v1/` para listar arquivos.

---

## Filtros Automáticos Pré-IA

Configurados via Firestore em `config/filters`. Aplicados em `_apply_filters()` no
`agent/scraper/pncp.py`:

| Campo Firestore | Tipo | Comportamento |
|---|---|---|
| `valor_minimo` | float | Descarta editais com `valorTotalEstimado` abaixo do valor |
| `excluir_me_epp` | bool | Descarta editais com `tipoBeneficioId = 1` (exclusivo ME/EPP) |
| `termos_exclusao` | list[str] | Descarta editais com termo no objeto (case-insensitive) |

**Importante:** `tipoBeneficioId = 1` = exclusivo ME/EPP → descartar.
Códigos 2, 3, 4, 5 ou ausente → manter.

---

## Pipeline Pub/Sub

```
Scraper PNCP
    → INSERT BigQuery (tabela editais)
    → PUBLISH Pub/Sub (topic: coleta-editais)
        → Cloud Run POST /pubsub/analisar
            → download_pending_pdfs()
            → analyze_edital() em gemini_analyzer.py
                (score, prioridade, checklist, datas/prazos, POC, etc.)
            → INSERT BigQuery (tabela analises)
```

O ciclo local (`runner.py`) usa `score_bid_with_profile()` no mesmo módulo e persiste
em SQLite (`AnalyzedBid` com `datas_prazos`, `itens_poc`, `checklist_documentos`,
`envolve_producao_conteudo`).

Mensagem publicada:
```json
{"edital_id": "uuid", "numero": "05472936000139-1-000082/2026"}
```

**Regra crítica do subscriber:** sempre retornar HTTP 200, mesmo em erros de negócio.
O Pub/Sub reentrega se receber status != 200, causando loop infinito.

---

## Configurações (config.py)

Todas as configurações são lidas via variáveis de ambiente com fallback:

```python
settings.gcp_project_id      # GCP project (BigQuery, Pub/Sub, Firestore)
settings.bigquery_dataset     # "licitacoes"
settings.bigquery_table       # "editais"
settings.pubsub_topic         # "coleta-editais"
settings.pncp_modalidades     # "1,2,3,4,5,6,7,8,9,10,11,12"
settings.interval_hours       # frequência do ciclo (padrão: 6h)
```

---

## Convenções de Código

```python
# Logger — sempre usar get_logger com namespace
from agent.logging_utils import get_logger
logger = get_logger("bidradar.modulo")

# Clientes GCP — lazy init com globals, nunca instanciar direto
_bq_client: Any = None
def _get_bq():
    global _bq_client
    if _bq_client is None:
        from google.cloud import bigquery
        _bq_client = bigquery.Client()
    return _bq_client

# Erros de credencial local (fora do GCP) são silenciosos em DEBUG
# Outros erros de infra: logger.warning, nunca deixar travar o fluxo

# Type hints obrigatórios em todas as funções
# Funções privadas de módulo: prefixo _underscore
# Requests ao PNCP: sempre incluir User-Agent: Mozilla/5.0
```

---

## Decisões Técnicas Importantes

- **Sem Playwright em produção** — descobrimos que a API interna do PNCP
  (`/api/pncp/v1/`) funciona sem autenticação e sem captcha via `requests` simples.
  Playwright foi instalado apenas para descoberta dos endpoints e não deve ser
  adicionado ao fluxo principal.

- **ConLicitação pausado** — requer credenciais de login que ainda não temos.
  Não implementar nada para ConLicitação até as credenciais estarem disponíveis.

- **API Pub/Sub retorna lista direta** — a API `/arquivos` do PNCP retorna
  `[{...}, {...}]` e não `{"data": [...]}`. Nunca usar `.get("data", [])` nela.
  Usar: `data if isinstance(data, list) else data.get("data", [])`

- **Firestore para config em runtime** — filtros, toggles e configurações que o
  usuário pode alterar pela interface ficam no Firestore (`config/filters`),
  não em variáveis de ambiente.

---

## Épicos e Roadmap (referência Jira)

| Epic | Prazo | Responsável | Status |
|---|---|---|---|
| ID-28 Coleta de Editais (Crawler) | 23/05/2026 | Felipe Malveira | Em andamento |
| ID-29 Análise IA (Vertex AI + Gemini) | 06/06/2026 | wagner.saldanha | A fazer |
| ID-30 Interface Web (MVP) | 27/06/2026 | josebe.barbosa | A fazer |
| ID-31 Notificações & Operação | 04/07/2026 | Felipe Malveira | A fazer |
