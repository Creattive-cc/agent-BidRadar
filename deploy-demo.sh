#!/usr/bin/env bash
# Deploy da DEMO BidRadar (Streamlit) no Cloud Run via Cloud Build.
# Usa Dockerfile.demo (imagem leve) e publica uma URL pública para a apresentação.
#
# Uso:  ./deploy-demo.sh SEU_PROJECT_ID [REGIAO]
set -euo pipefail

PROJECT_ID="${1:?Informe o PROJECT_ID. Ex: ./deploy-demo.sh creattive-licitacoes-dev}"
REGION="${2:-us-central1}"
SERVICE="bidradar-demo"

echo "→ Projeto: $PROJECT_ID | Região: $REGION | Serviço: $SERVICE"

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

gcloud builds submit \
    --config=cloudbuild-demo.yaml \
    --substitutions=_REGION="$REGION",_SERVICE="$SERVICE"

echo
echo "✅ URL pública da demo:"
gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)'
