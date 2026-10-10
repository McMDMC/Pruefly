#!/usr/bin/env bash
# One-shot deploy to Cloud Run (EU). Usage: PROJECT=my-gcp-project ./deploy/deploy.sh
set -euo pipefail
: "${PROJECT:?set PROJECT=<gcp project id>}"
REGION="${REGION:-europe-west3}"
SERVICE="${SERVICE:-pruefly}"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com \
  artifactregistry.googleapis.com aiplatform.googleapis.com --project "$PROJECT"

# Secrets (created once; you will be asked to paste the values).
ensure_secret() {
  local name="$1" prompt="$2"
  if ! gcloud secrets describe "$name" --project "$PROJECT" >/dev/null 2>&1; then
    read -r -s -p "$prompt: " val; echo
    printf '%s' "$val" | gcloud secrets create "$name" --data-file=- --replication-policy=automatic --project "$PROJECT"
  fi
}
ensure_secret pruefly-access-code "Zugangscode (für Joanna)"
ensure_secret pruefly-anthropic-key "ANTHROPIC_API_KEY"

SA="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
for s in pruefly-access-code pruefly-anthropic-key; do
  gcloud secrets add-iam-policy-binding "$s" --member "serviceAccount:$SA" \
    --role roles/secretmanager.secretAccessor --project "$PROJECT" >/dev/null
done
gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$SA" \
  --role roles/aiplatform.user >/dev/null   # Gemini fallback via Vertex

gcloud run deploy "$SERVICE" --source . --project "$PROJECT" --region "$REGION" \
  --allow-unauthenticated --max-instances 3 --memory 1Gi --cpu 1 --timeout 120 \
  --set-env-vars "PRUEFLY_ENV=prod,PRUEFLY_GEMINI_PROJECT=$PROJECT,PRUEFLY_GEMINI_LOCATION=${GEMINI_LOCATION:-europe-west1},PRUEFLY_GEMINI_MODEL=${GEMINI_MODEL:-gemini-3.5-flash}" \
  --set-secrets "PRUEFLY_ACCESS_CODE=pruefly-access-code:latest,ANTHROPIC_API_KEY=pruefly-anthropic-key:latest"

gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format='value(status.url)'
