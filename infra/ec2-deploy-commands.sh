#!/bin/bash
# EC2 deployment commands — run these on EC2 after git pull
# SSH: ssh -i /Users/prathmeshwalimbe/Downloads/irg-key.pem ec2-user@43.205.237.197

set -e

PROJECT=/home/ec2-user/irg_gdp
BACKEND=$PROJECT/backend
VENV=$PROJECT/venv

cd $PROJECT

# ── 1. Pull latest code ────────────────────────────────────────────────────────
git pull origin main

# ── 2. Install any new Python deps ────────────────────────────────────────────
$VENV/bin/pip install -r $BACKEND/requirements.txt -q

# ── 3. Django migrate + collectstatic ─────────────────────────────────────────
cd $BACKEND
$VENV/bin/python manage.py migrate --noinput
$VENV/bin/python manage.py collectstatic --noinput

# ── 4. Install systemd service (one-time setup) ───────────────────────────────
# Only needed once. Skip if service already exists.
if [ ! -f /etc/systemd/system/gunicorn.service ]; then
  sudo cp $PROJECT/infra/gunicorn.service /etc/systemd/system/gunicorn.service
  sudo systemctl daemon-reload
  sudo systemctl enable gunicorn
  # Ensure gunicorn log directory exists
  sudo mkdir -p /var/log/gunicorn
  sudo chown ec2-user:ec2-user /var/log/gunicorn
fi

# ── 5. Restart gunicorn via systemd ───────────────────────────────────────────
sudo systemctl restart gunicorn
sudo systemctl status gunicorn --no-pager

# ── 6. Install nginx config (one-time setup) ──────────────────────────────────
if [ ! -f /etc/nginx/conf.d/irg-gdp.conf ]; then
  sudo cp $PROJECT/infra/nginx-irg-gdp.conf /etc/nginx/conf.d/irg-gdp.conf
  sudo nginx -t && sudo systemctl reload nginx
fi

echo "✓ Deployment complete"
