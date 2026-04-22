#!/bin/bash
# EC2 deployment script — irggdp.com
# SSH: ssh -i /Users/prathmeshwalimbe/Downloads/irg-key.pem ec2-user@43.205.237.197
#
# First run:  bash ec2-deploy-commands.sh --setup
# Every deploy after: bash ec2-deploy-commands.sh
set -euo pipefail

DOMAIN=irggdp.com
PROJECT=/home/ec2-user/irg_gdp
BACKEND=$PROJECT/backend
VENV=$PROJECT/venv
EMAIL=admin@irggdp.com   # used for Let's Encrypt notifications

SETUP=false
[[ "${1:-}" == "--setup" ]] && SETUP=true

# ─────────────────────────────────────────────────────────────────────────────
# FIRST-TIME SETUP
# ─────────────────────────────────────────────────────────────────────────────
if $SETUP; then
  echo "=== [SETUP] Installing system packages ==="
  sudo yum update -y
  sudo yum install -y git nginx python3.11 python3.11-pip python3.11-devel \
      postgresql15 postgresql15-server postgresql15-devel \
      gcc openssl-devel bzip2-devel libffi-devel zlib-devel \
      libjpeg-devel certbot python3-certbot-nginx

  echo "=== [SETUP] Initialising PostgreSQL ==="
  sudo postgresql-setup --initdb || true
  sudo systemctl enable postgresql --now

  echo "=== [SETUP] Creating DB and user ==="
  # Read password from .env
  DB_PASS=$(grep '^DB_PASSWORD=' "$BACKEND/.env" | cut -d= -f2-)
  if [[ -z "$DB_PASS" ]]; then
    echo "ERROR: DB_PASSWORD is empty in $BACKEND/.env — set it first."
    exit 1
  fi
  sudo -u postgres psql -c "CREATE USER irg_gdp WITH PASSWORD '$DB_PASS';" 2>/dev/null || true
  sudo -u postgres psql -c "CREATE DATABASE irg_gdp_db OWNER irg_gdp;" 2>/dev/null || true
  sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE irg_gdp_db TO irg_gdp;" 2>/dev/null || true

  echo "=== [SETUP] Creating Python virtualenv ==="
  python3.11 -m venv "$VENV"

  echo "=== [SETUP] Installing nginx config (HTTP only — before cert) ==="
  # Temporary HTTP-only config so certbot can do its ACME challenge
  sudo tee /etc/nginx/conf.d/irg-gdp.conf > /dev/null <<'NGINX_TMP'
server {
    listen 80;
    server_name irggdp.com www.irggdp.com;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 301 https://irggdp.com$request_uri; }
}
NGINX_TMP
  sudo nginx -t && sudo systemctl enable nginx --now && sudo systemctl reload nginx

  echo "=== [SETUP] Obtaining Let's Encrypt certificate ==="
  sudo certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" \
      --non-interactive --agree-tos -m "$EMAIL" --redirect

  echo "=== [SETUP] Installing production nginx config ==="
  sudo cp "$PROJECT/infra/nginx-irg-gdp.conf" /etc/nginx/conf.d/irggdp.conf
  sudo nginx -t && sudo systemctl reload nginx

  echo "=== [SETUP] Installing gunicorn systemd service ==="
  sudo cp "$PROJECT/infra/gunicorn.service" /etc/systemd/system/gunicorn.service
  sudo systemctl daemon-reload
  sudo systemctl enable gunicorn

  echo "=== [SETUP] Setting up certbot auto-renewal ==="
  echo "0 3 * * * root certbot renew --quiet --post-hook 'systemctl reload nginx'" \
      | sudo tee /etc/cron.d/certbot-renew > /dev/null

  echo "=== [SETUP] Done. Now run without --setup to deploy the app. ==="
  exit 0
fi

# ─────────────────────────────────────────────────────────────────────────────
# EVERY DEPLOY
# ─────────────────────────────────────────────────────────────────────────────
echo "=== [DEPLOY] Pulling latest code ==="
cd "$PROJECT"
git pull origin main

echo "=== [DEPLOY] Installing Python dependencies ==="
"$VENV/bin/pip" install -r "$BACKEND/requirements.txt" -q

echo "=== [DEPLOY] Running migrations ==="
cd "$BACKEND"
"$VENV/bin/python" manage.py migrate --noinput

echo "=== [DEPLOY] Collecting static files ==="
"$VENV/bin/python" manage.py collectstatic --noinput --clear

echo "=== [DEPLOY] Reloading nginx config ==="
sudo cp "$PROJECT/infra/nginx-irg-gdp.conf" /etc/nginx/conf.d/irggdp.conf
sudo nginx -t && sudo systemctl reload nginx

echo "=== [DEPLOY] Restarting gunicorn ==="
sudo systemctl restart gunicorn
sudo systemctl status gunicorn --no-pager -l

echo ""
echo "✓ Deploy complete — https://$DOMAIN"
