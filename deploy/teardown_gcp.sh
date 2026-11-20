#!/usr/bin/env bash
set -euo pipefail

# LedgerLens Google Cloud Platform Teardown Script
# Cleanly deletes the Cloud Run service and (optionally) AlloyDB instance/cluster,
# and prints explicit commands for optional BigQuery, GCS, Pub/Sub, Artifact Registry,
# and Secret Manager cleanup so billing stops cleanly without unintended data loss.

usage() {
  cat <<'EOF'
Usage: PROJECT_ID=<gcp-project-id> ./deploy/teardown_gcp.sh [--delete-alloydb]

Options:
  --delete-alloydb  Delete the AlloyDB primary instance and cluster to stop
                    continuous hourly compute/storage charges.
  -h, --help        Show this help message and exit.

Environment variables:
  PROJECT_ID        Required GCP project ID.
  REGION            GCP region (default: asia-south1).
  SERVICE_NAME      Cloud Run service name (default: ledgerlens-auditor).
  AR_REPO           Artifact Registry Docker repo (default: ledgerlens).
  BQ_DATASET        BigQuery dataset name (default: ledgerlens_analytics).
  GCS_BUCKET        GCS upload bucket (default: ${PROJECT_ID}-ledgerlens-uploads).
  PUBSUB_TOPIC      Pub/Sub recovery events topic (default: ledgerlens-recovery-events).
  SECRET_NAME       Secret Manager secret name (default: GEMINI_API_KEY).
  DELETE_ALLOYDB    Set to "true" to delete AlloyDB (default: false).
  ALLOYDB_CLUSTER   AlloyDB cluster ID (default: ledgerlens-alloydb).
  ALLOYDB_INSTANCE  AlloyDB primary instance ID (default: ledgerlens-primary).
EOF
}

DELETE_ALLOYDB="${DELETE_ALLOYDB:-false}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --delete-alloydb)
      DELETE_ALLOYDB="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-asia-south1}"
SERVICE_NAME="${SERVICE_NAME:-ledgerlens-auditor}"
AR_REPO="${AR_REPO:-ledgerlens}"
BQ_DATASET="${BQ_DATASET:-ledgerlens_analytics}"
GCS_BUCKET="${GCS_BUCKET:-${PROJECT_ID}-ledgerlens-uploads}"
PUBSUB_TOPIC="${PUBSUB_TOPIC:-ledgerlens-recovery-events}"
SECRET_NAME="${SECRET_NAME:-GEMINI_API_KEY}"
ALLOYDB_CLUSTER="${ALLOYDB_CLUSTER:-ledgerlens-alloydb}"
ALLOYDB_INSTANCE="${ALLOYDB_INSTANCE:-ledgerlens-primary}"

echo "==> Deleting Cloud Run service '${SERVICE_NAME}' in ${REGION} (if present)..."
if gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" >/dev/null 2>&1; then
  gcloud run services delete "${SERVICE_NAME}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --quiet
  echo "    Deleted Cloud Run service '${SERVICE_NAME}'."
else
  echo "    Cloud Run service '${SERVICE_NAME}' not found; skipping."
fi

if [[ "${DELETE_ALLOYDB}" == "true" ]]; then
  echo "==> Deleting AlloyDB instance '${ALLOYDB_INSTANCE}' (if present)..."
  if gcloud alloydb instances describe "${ALLOYDB_INSTANCE}" \
    --project="${PROJECT_ID}" \
    --cluster="${ALLOYDB_CLUSTER}" \
    --region="${REGION}" >/dev/null 2>&1; then
    gcloud alloydb instances delete "${ALLOYDB_INSTANCE}" \
      --project="${PROJECT_ID}" \
      --cluster="${ALLOYDB_CLUSTER}" \
      --region="${REGION}" \
      --quiet
    echo "    Deleted AlloyDB instance '${ALLOYDB_INSTANCE}'."
  else
    echo "    AlloyDB instance '${ALLOYDB_INSTANCE}' not found; skipping."
  fi

  echo "==> Deleting AlloyDB cluster '${ALLOYDB_CLUSTER}' (if present)..."
  if gcloud alloydb clusters describe "${ALLOYDB_CLUSTER}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" >/dev/null 2>&1; then
    gcloud alloydb clusters delete "${ALLOYDB_CLUSTER}" \
      --project="${PROJECT_ID}" \
      --region="${REGION}" \
      --quiet
    echo "    Deleted AlloyDB cluster '${ALLOYDB_CLUSTER}'."
  else
    echo "    AlloyDB cluster '${ALLOYDB_CLUSTER}' not found; skipping."
  fi
else
  echo "==> AlloyDB teardown skipped (pass --delete-alloydb if you provisioned AlloyDB)."
fi

cat <<EOF

==> Optional cleanup commands to remove retained storage/messaging/artifacts and stop all billing:

  # 1. Delete BigQuery analytics dataset and all tables:
  bq rm -r -f -d "${PROJECT_ID}:${BQ_DATASET}"

  # 2. Delete GCS uploads bucket and stored objects:
  gcloud storage rm -r "gs://${GCS_BUCKET}"

  # 3. Delete Pub/Sub topic:
  gcloud pubsub topics delete "${PUBSUB_TOPIC}" --project="${PROJECT_ID}"

  # 4. Delete Artifact Registry Docker repository:
  gcloud artifacts repositories delete "${AR_REPO}" --location="${REGION}" --project="${PROJECT_ID}" --quiet

  # 5. Delete Secret Manager secret:
  gcloud secrets delete "${SECRET_NAME}" --project="${PROJECT_ID}" --quiet
EOF
