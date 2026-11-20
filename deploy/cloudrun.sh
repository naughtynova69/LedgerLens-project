#!/usr/bin/env bash
set -euo pipefail

# LedgerLens Google Cloud Run Deployment Script (Buildathon Slides 4 & 5)
# Production path: Cloud Run + Secret Manager (GEMINI_API_KEY) + Cloud SQL + Cloud Storage

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-asia-south1}"
SERVICE_NAME="${SERVICE_NAME:-ledgerlens-auditor}"
AR_REPO="${AR_REPO:-ledgerlens}"
GCS_BUCKET="${GCS_BUCKET:-${PROJECT_ID}-ledgerlens-uploads}"
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
  --set-env-vars "GEMINI_PRIMARY_MODEL=gemini-4-carbon,GEMINI_FLASH_MODEL=gemini-2.5-flash,GCS_UPLOAD_BUCKET=${GCS_BUCKET}"
  --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest"
)

if [[ -n "${CLOUD_SQL_INSTANCE}" ]]; then
  DEPLOY_ARGS+=(--add-cloudsql-instances "${CLOUD_SQL_INSTANCE}")
fi

echo "==> Deploying to Cloud Run (${REGION})..."
gcloud "${DEPLOY_ARGS[@]}"
