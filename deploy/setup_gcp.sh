#!/usr/bin/env bash
set -euo pipefail

# LedgerLens Google Cloud Platform Bootstrap Script
# Idempotently provisions base GCP APIs, Artifact Registry, GCS, BigQuery,
# Pub/Sub, Secret Manager, and Cloud Run runtime IAM permissions.
# AlloyDB is opt-in (--with-alloydb or WITH_ALLOYDB=true) because it incurs
# continuous hourly compute and storage charges even when idle.

usage() {
  cat <<'EOF'
Usage: PROJECT_ID=<gcp-project-id> ./deploy/setup_gcp.sh [--with-alloydb]

Options:
  --with-alloydb    Also provision AlloyDB cluster and primary instance
                    (incurs continuous hourly billing; off by default).
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
  GEMINI_API_KEY    Optional value to add as a new version of GEMINI_API_KEY.
  RUNTIME_SA        Optional Cloud Run runtime service account email.
  WITH_ALLOYDB      Set to "true" to provision AlloyDB (default: false).
  ALLOYDB_CLUSTER   AlloyDB cluster ID (default: ledgerlens-alloydb).
  ALLOYDB_INSTANCE  AlloyDB primary instance ID (default: ledgerlens-primary).
  ALLOYDB_NETWORK   VPC network for AlloyDB (default: default).
  ALLOYDB_CPU_COUNT AlloyDB instance vCPU count (default: 2).
  ALLOYDB_PASSWORD  Required when creating a new AlloyDB cluster.
EOF
}

WITH_ALLOYDB="${WITH_ALLOYDB:-false}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-alloydb)
      WITH_ALLOYDB="true"
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
ALLOYDB_NETWORK="${ALLOYDB_NETWORK:-default}"
ALLOYDB_CPU_COUNT="${ALLOYDB_CPU_COUNT:-2}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BQ_SCHEMA_FILE="${ROOT_DIR}/infra/bigquery/schema.sql"

echo "==> Enabling required GCP APIs for project ${PROJECT_ID}..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  bigquery.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  pubsub.googleapis.com \
  aiplatform.googleapis.com \
  --project="${PROJECT_ID}"

echo "==> Ensuring Artifact Registry repository '${AR_REPO}' in ${REGION}..."
if gcloud artifacts repositories describe "${AR_REPO}" \
  --project="${PROJECT_ID}" \
  --location="${REGION}" >/dev/null 2>&1; then
  echo "    Artifact Registry repository '${AR_REPO}' already exists."
else
  gcloud artifacts repositories create "${AR_REPO}" \
    --project="${PROJECT_ID}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="LedgerLens container images"
fi

echo "==> Ensuring GCS bucket 'gs://${GCS_BUCKET}' in ${REGION}..."
if gcloud storage buckets describe "gs://${GCS_BUCKET}" \
  --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "    GCS bucket 'gs://${GCS_BUCKET}' already exists."
else
  gcloud storage buckets create "gs://${GCS_BUCKET}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --uniform-bucket-level-access
fi

echo "==> Ensuring BigQuery dataset '${PROJECT_ID}:${BQ_DATASET}' in ${REGION}..."
if bq --project_id="${PROJECT_ID}" show --dataset "${PROJECT_ID}:${BQ_DATASET}" >/dev/null 2>&1; then
  echo "    BigQuery dataset '${BQ_DATASET}' already exists."
else
  bq --project_id="${PROJECT_ID}" mk --dataset --location="${REGION}" "${PROJECT_ID}:${BQ_DATASET}"
fi

if [[ -f "${BQ_SCHEMA_FILE}" ]]; then
  echo "==> Applying BigQuery schema from ${BQ_SCHEMA_FILE}..."
  bq query \
    --project_id="${PROJECT_ID}" \
    --use_legacy_sql=false \
    --dataset_id="${BQ_DATASET}" < "${BQ_SCHEMA_FILE}"
else
  echo "WARNING: ${BQ_SCHEMA_FILE} not found; skipping BigQuery schema apply." >&2
fi

echo "==> Ensuring Pub/Sub topic '${PUBSUB_TOPIC}'..."
if gcloud pubsub topics describe "${PUBSUB_TOPIC}" \
  --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "    Pub/Sub topic '${PUBSUB_TOPIC}' already exists."
else
  gcloud pubsub topics create "${PUBSUB_TOPIC}" --project="${PROJECT_ID}"
fi

echo "==> Ensuring Secret Manager secret '${SECRET_NAME}'..."
if gcloud secrets describe "${SECRET_NAME}" \
  --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "    Secret '${SECRET_NAME}' already exists."
else
  gcloud secrets create "${SECRET_NAME}" \
    --project="${PROJECT_ID}" \
    --replication-policy="automatic"
fi

if [[ -n "${GEMINI_API_KEY:-}" ]]; then
  echo "    Adding new version to secret '${SECRET_NAME}' from GEMINI_API_KEY env var..."
  printf '%s' "${GEMINI_API_KEY}" | gcloud secrets versions add "${SECRET_NAME}" \
    --project="${PROJECT_ID}" \
    --data-file=-
else
  EXISTING_VERSION="$(gcloud secrets versions list "${SECRET_NAME}" \
    --project="${PROJECT_ID}" \
    --limit=1 \
    --format='value(name)' 2>/dev/null || true)"
  if [[ -z "${EXISTING_VERSION}" ]]; then
    echo "NOTE: Secret '${SECRET_NAME}' has no versions yet. Add your Gemini API key before deploying Cloud Run:"
    echo "  printf '%s' 'YOUR_GEMINI_API_KEY' | gcloud secrets versions add ${SECRET_NAME} --project=${PROJECT_ID} --data-file=-"
  fi
fi

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
RUNTIME_SA="${RUNTIME_SA:-${PROJECT_NUMBER}-compute@developer.gserviceaccount.com}"

echo "==> Granting IAM roles to Cloud Run runtime SA '${RUNTIME_SA}'..."
RUNTIME_ROLES=(
  "roles/bigquery.dataEditor"
  "roles/bigquery.jobUser"
  "roles/storage.objectAdmin"
  "roles/secretmanager.secretAccessor"
  "roles/pubsub.publisher"
  "roles/aiplatform.user"
  "roles/alloydb.client"
)

for role in "${RUNTIME_ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="${role}" \
    --condition=None \
    --quiet >/dev/null
  echo "    Bound ${role}"
done

if [[ "${WITH_ALLOYDB}" == "true" ]]; then
  cat <<EOF

========================================================================
COST NOTICE: PROVISIONING ALLOYDB FOR POSTGRESQL
========================================================================
Unlike serverless Cloud Run, BigQuery, GCS, and Pub/Sub, AlloyDB incurs
continuous hourly compute (${ALLOYDB_CPU_COUNT} vCPU) and storage billing even when idle.
Cluster:  ${ALLOYDB_CLUSTER} (region: ${REGION}, network: ${ALLOYDB_NETWORK})
Instance: ${ALLOYDB_INSTANCE} (PRIMARY)
To stop AlloyDB billing later, run:
  PROJECT_ID=${PROJECT_ID} REGION=${REGION} ./deploy/teardown_gcp.sh --delete-alloydb
========================================================================

EOF

  echo "==> Enabling AlloyDB and networking APIs..."
  gcloud services enable \
    alloydb.googleapis.com \
    compute.googleapis.com \
    servicenetworking.googleapis.com \
    --project="${PROJECT_ID}"

  PSA_RANGE_NAME="${PSA_RANGE_NAME:-ledgerlens-alloydb-psa}"
  echo "==> Ensuring Private Services Access range '${PSA_RANGE_NAME}' on network '${ALLOYDB_NETWORK}'..."
  if ! gcloud compute addresses describe "${PSA_RANGE_NAME}" --global \
    --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud compute addresses create "${PSA_RANGE_NAME}" \
      --global \
      --purpose=VPC_PEERING \
      --prefix-length=16 \
      --network="${ALLOYDB_NETWORK}" \
      --project="${PROJECT_ID}"
  fi
  gcloud services vpc-peerings connect \
    --service=servicenetworking.googleapis.com \
    --ranges="${PSA_RANGE_NAME}" \
    --network="${ALLOYDB_NETWORK}" \
    --project="${PROJECT_ID}" || echo "    VPC peering already connected (or update required)."

  echo "==> Ensuring AlloyDB cluster '${ALLOYDB_CLUSTER}' in ${REGION}..."
  if gcloud alloydb clusters describe "${ALLOYDB_CLUSTER}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" >/dev/null 2>&1; then
    echo "    AlloyDB cluster '${ALLOYDB_CLUSTER}' already exists."
  else
    ALLOYDB_PASSWORD="${ALLOYDB_PASSWORD:?Set ALLOYDB_PASSWORD when creating a new AlloyDB cluster}"
    gcloud alloydb clusters create "${ALLOYDB_CLUSTER}" \
      --project="${PROJECT_ID}" \
      --region="${REGION}" \
      --network="${ALLOYDB_NETWORK}" \
      --password="${ALLOYDB_PASSWORD}"
  fi

  echo "==> Ensuring AlloyDB primary instance '${ALLOYDB_INSTANCE}'..."
  if gcloud alloydb instances describe "${ALLOYDB_INSTANCE}" \
    --project="${PROJECT_ID}" \
    --cluster="${ALLOYDB_CLUSTER}" \
    --region="${REGION}" >/dev/null 2>&1; then
    echo "    AlloyDB instance '${ALLOYDB_INSTANCE}' already exists."
  else
    gcloud alloydb instances create "${ALLOYDB_INSTANCE}" \
      --project="${PROJECT_ID}" \
      --cluster="${ALLOYDB_CLUSTER}" \
      --region="${REGION}" \
      --instance-type=PRIMARY \
      --cpu-count="${ALLOYDB_CPU_COUNT}"
  fi
else
  echo "==> Skipping AlloyDB provisioning (WITH_ALLOYDB=${WITH_ALLOYDB}). Pass --with-alloydb to enable."
fi

echo "==> GCP setup complete for '${SERVICE_NAME}' in ${PROJECT_ID} (${REGION})."
echo "    Next: PROJECT_ID=${PROJECT_ID} REGION=${REGION} ./deploy/cloudrun.sh"
