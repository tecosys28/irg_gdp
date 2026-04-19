#!/usr/bin/env bash
# deploy.sh — full production deploy to irggdp.com
# Usage: bash deploy.sh
# Prerequisites: gcloud CLI authenticated, firebase CLI installed, Docker running.
set -euo pipefail

PROJECT_ID="irggdp"
REGION="asia-south1"
SERVICE="irggdp-api"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE}"

echo "=== 1. Build & push Docker image ==="
gcloud builds submit --tag "$IMAGE" --project "$PROJECT_ID" .

echo "=== 2. Deploy to Cloud Run ==="
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --platform managed \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars "DJANGO_DEBUG=False" \
  --set-env-vars "FIREBASE_PROJECT_ID=${PROJECT_ID}" \
  --set-env-vars "DJANGO_ALLOWED_HOSTS=irggdp.com,www.irggdp.com,${SERVICE}-$(gcloud config get-value account 2>/dev/null | tr -d '@.' | head -c8)-${REGION}.a.run.app" \
  --update-secrets "DJANGO_SECRET_KEY=django-secret-key:latest" \
  --update-secrets "DB_NAME=db-name:latest" \
  --update-secrets "DB_USER=db-user:latest" \
  --update-secrets "DB_PASSWORD=db-password:latest" \
  --update-secrets "DB_HOST=db-host:latest" \
  --update-secrets "FIREBASE_CREDENTIALS_JSON=firebase-credentials-json:latest"

echo "=== 3. Deploy Firebase (hosting + functions + rules) ==="
firebase deploy --project "$PROJECT_ID"

echo ""
echo "=== Done! ==="
echo "Site: https://irggdp.com"
echo "API:  https://irggdp.com/api/v1/"
echo "Admin: https://irggdp.com/admin/"
