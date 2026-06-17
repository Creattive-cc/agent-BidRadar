#!/usr/bin/env bash
set -e

PROJECT_DIR="/home/felimal/Projetos/Trabalho/Creattive/dev/agent-BidRadar"
LOG_FILE="$PROJECT_DIR/logs/bidradar_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$PROJECT_DIR/logs"

# Garante que o Cloud SQL proxy está rodando
if ! pgrep -f "cloud-sql-proxy.*bidradar-db" > /dev/null; then
  /home/felimal/.local/bin/cloud-sql-proxy creattive-licitacoes-dev:us-central1:bidradar-db --port=5433 &
  sleep 3
fi

cd "$PROJECT_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando BidRadar run_once" | tee -a "$LOG_FILE"

uv run python -m agent.runner >> "$LOG_FILE" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Concluído" | tee -a "$LOG_FILE"
