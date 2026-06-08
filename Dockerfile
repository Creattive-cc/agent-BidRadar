# ── Stage 1: React build ──────────────────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts

COPY frontend/ ./
# VITE_API_BASE é vazio em produção: FastAPI e SPA no mesmo origin
RUN npm run build

# ── Stage 2: Python deps ──────────────────────────────────────────────────────
FROM python:3.12-slim AS python-builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# ── Stage 3: Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

COPY --from=python-builder /app/.venv /app/.venv
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

COPY agent/ ./agent/
COPY api/ ./api/
COPY company_profile/ ./company_profile/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
