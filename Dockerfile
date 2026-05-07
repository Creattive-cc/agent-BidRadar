# ---- Build stage ----
FROM python:3.12-slim AS builder

# Instalar UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copiar arquivos de dependências
COPY pyproject.toml uv.lock ./

# Instalar dependências sem o projeto em si
RUN uv sync --frozen --no-install-project --no-dev

# ---- Runtime stage ----
FROM python:3.12-slim

WORKDIR /app

# Copiar o virtualenv do builder
COPY --from=builder /app/.venv /app/.venv

# Copiar o código
COPY agent/ ./agent/
COPY api/ ./api/

# Variáveis de ambiente
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

EXPOSE 8080

# Rodar a API FastAPI com uvicorn
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
