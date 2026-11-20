#!/usr/bin/env bash
set -euo pipefail

# LedgerLens Google Cloud Run Deployment Script (Buildathon Slides 4 & 5)
# Production path: Cloud Run + Secret Manager (GEMINI_API_KEY) + Cloud SQL + Cloud Storage

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-asia-south1}"
GCP_LOCATION="${GCP_LOCATION:-global}"
SERVICE_NAME="${SERVICE_NAME:-ledgerlens-auditor}"
AR_REPO="${AR_REPO:-ledgerlens}"
DB_BACKEND="${DB_BACKEND:-sqlite}"
ALLOYDB_INSTANCE_URI="${ALLOYDB_INSTANCE_URI:-}"
BQ_DATASET="${BQ_DATASET:-ledgerlens_analytics}"
GCS_UPLOAD_BUCKET="${GCS_UPLOAD_BUCKET:-${GCS_BUCKET:-${PROJECT_ID}-ledgerlens-uploads}}"
USE_VERTEX_AI="${USE_VERTEX_AI:-true}"
PUBSUB_RECOVERY_TOPIC="${PUBSUB_RECOVERY_TOPIC:-ledgerlens-recovery-events}"
CLOUD_SQL_INSTANCE="${CLOUD_SQL_INSTANCE:-}" # e.g. my-project:asia-south1:ledgerlens-sql
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/ledgerlens:latest"

echo "==> Building and pushing container image: ${IMAGE_URI}"
gcloud builds submit --project "${PROJECT_ID}" --tag "${IMAGE_URI}" .

DEPLOY_ARGS=(
  run deploy "${SERVICE_NAME}"
  --project "${PROJECT_ID}"
  --image "${IMAGE_URI}"
  --region "${REGION}"
  --platform managed
  --allow-unauthenticated
  --memory 1Gi
  --cpu 1
  --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},GCP_LOCATION=${GCP_LOCATION},DB_BACKEND=${DB_BACKEND},ALLOYDB_INSTANCE_URI=${ALLOYDB_INSTANCE_URI},BQ_DATASET=${BQ_DATASET},GCS_UPLOAD_BUCKET=${GCS_UPLOAD_BUCKET},USE_VERTEX_AI=${USE_VERTEX_AI},PUBSUB_RECOVERY_TOPIC=${PUBSUB_RECOVERY_TOPIC},GEMINI_PRIMARY_MODEL=gemini-4-carbon,GEMINI_FLASH_MODEL=gemini-2.5-flash"
  --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest"
)

if [[ -n "${CLOUD_SQL_INSTANCE}" ]]; then
  DEPLOY_ARGS+=(--add-cloudsql-instances "${CLOUD_SQL_INSTANCE}")
fi

echo "==> Deploying to Cloud Run (${REGION})..."
gcloud "${DEPLOY_ARGS[@]}"
