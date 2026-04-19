#!/usr/bin/env bash
# setup-secrets.sh — create GCP Secret Manager secrets for irggdp
# Run ONCE before first deploy. Fill in values below before running.
# Usage: bash setup-secrets.sh
set -euo pipefail

PROJECT_ID="irggdp"

create_secret() {
  local name="$1"
  local value="$2"
  if gcloud secrets describe "$name" --project "$PROJECT_ID" &>/dev/null; then
    echo "$value" | gcloud secrets versions add "$name" --data-file=- --project "$PROJECT_ID"
    echo "Updated secret: $name"
  else
    echo "$value" | gcloud secrets create "$name" --data-file=- --replication-policy automatic --project "$PROJECT_ID"
    echo "Created secret: $name"
  fi
}

# ── REQUIRED: Fill these in before running ────────────────────────────────────

DJANGO_SECRET=$(python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())" 2>/dev/null || \
  python3 -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits+'!@#$%^&*') for _ in range(50)))")

# Cloud SQL connection details (get from GCP Console → Cloud SQL)
DB_NAME_VAL="irg_gdp"
DB_USER_VAL="irg_gdp"
DB_PASSWORD_VAL="REPLACE_WITH_CLOUD_SQL_PASSWORD"
DB_HOST_VAL="/cloudsql/${PROJECT_ID}:${REGION:-asia-south1}:irggdp-db"

# Firebase service account JSON — download from Firebase Console → Project Settings → Service Accounts
FIREBASE_SA_JSON_PATH="./firebase-service-account.json"

# ─────────────────────────────────────────────────────────────────────────────

create_secret "django-secret-key"          "$DJANGO_SECRET"
create_secret "db-name"                    "$DB_NAME_VAL"
create_secret "db-user"                    "$DB_USER_VAL"
create_secret "db-password"               "$DB_PASSWORD_VAL"
create_secret "db-host"                   "$DB_HOST_VAL"

if [ -f "$FIREBASE_SA_JSON_PATH" ]; then
  create_secret "firebase-credentials-json" "$(cat "$FIREBASE_SA_JSON_PATH")"
else
  echo "WARNING: $FIREBASE_SA_JSON_PATH not found. Create the secret manually:"
  echo "  gcloud secrets create firebase-credentials-json --data-file=./firebase-service-account.json --project $PROJECT_ID"
fi

echo ""
echo "Secrets created. Grant Cloud Run SA access:"
SA="$(gcloud run services describe irggdp-api --region asia-south1 --project $PROJECT_ID --format='value(spec.template.spec.serviceAccountName)' 2>/dev/null || echo 'SERVICE_ACCOUNT@developer.gserviceaccount.com')"
echo "  gcloud projects add-iam-policy-binding $PROJECT_ID --member='serviceAccount:$SA' --role='roles/secretmanager.secretAccessor'"
