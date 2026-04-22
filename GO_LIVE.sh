# IRG_GDP — Go-Live Runbook
# irggdp.com | EC2: 43.205.237.197 | Firebase project: irggdp
# Run each section in order. Steps marked [ONE-TIME] only run on first deploy.

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — DNS (do this first, takes up to 30 min to propagate)
# ─────────────────────────────────────────────────────────────────────────────
# In your domain registrar / Route 53:
#   A     irggdp.com      → 43.205.237.197
#   A     www.irggdp.com  → 43.205.237.197
# Verify: dig irggdp.com +short   (should return 43.205.237.197)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — EC2: fill in secrets in backend/.env
# ─────────────────────────────────────────────────────────────────────────────
# SSH into EC2:
ssh -i /Users/prathmeshwalimbe/Downloads/irg-key.pem ec2-user@43.205.237.197

# Edit the env file and fill every blank value:
nano /home/ec2-user/irg_gdp/backend/.env
# Required values to fill:
#   DJANGO_SECRET_KEY   — run: python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
#   DB_PASSWORD         — choose a strong password (min 20 chars)
#   RAZORPAY_KEY_ID     — from Razorpay dashboard → Settings → API Keys
#   RAZORPAY_KEY_SECRET — same
#   EMAIL_HOST_USER     — Gmail address for sending notifications
#   EMAIL_HOST_PASSWORD — Gmail App Password (not your login password)
#   IRG_CHAIN_MIDDLEWARE_SECRET — run: openssl rand -hex 32
#   IRG_CHAIN_AUDIT_TOKEN       — run: openssl rand -hex 32

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — EC2: push latest code [ONE-TIME: clone the repo]
# ─────────────────────────────────────────────────────────────────────────────
# [ONE-TIME] Clone repo on EC2:
cd /home/ec2-user
git clone https://github.com/YOUR_ORG/irg_gdp.git
# OR if already cloned:
cd /home/ec2-user/irg_gdp && git pull origin main

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — EC2: first-time system setup (installs nginx, postgres, certbot, SSL)
# ─────────────────────────────────────────────────────────────────────────────
# [ONE-TIME] Run from EC2 after DNS has propagated:
bash /home/ec2-user/irg_gdp/infra/ec2-deploy-commands.sh --setup

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — EC2: deploy the app
# ─────────────────────────────────────────────────────────────────────────────
bash /home/ec2-user/irg_gdp/infra/ec2-deploy-commands.sh

# Verify Django is up:
curl -s https://irggdp.com/healthz   # → {"status": "ok"}
curl -s https://irggdp.com/api/v1/auth/users/me/   # → 401 (expected — not logged in)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — EC2: create Django superuser
# ─────────────────────────────────────────────────────────────────────────────
cd /home/ec2-user/irg_gdp/backend
/home/ec2-user/irg_gdp/venv/bin/python manage.py createsuperuser
# Visit https://irggdp.com/admin/ to verify

# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — EC2: open firewall ports (AWS Security Group)
# ─────────────────────────────────────────────────────────────────────────────
# In AWS Console → EC2 → Security Groups → inbound rules, ensure:
#   Port 22   (SSH)   — your IP only
#   Port 80   (HTTP)  — 0.0.0.0/0  (for certbot renewal + redirect)
#   Port 443  (HTTPS) — 0.0.0.0/0
# Do NOT expose 8000 (gunicorn), 8545 (Besu), 3100 (middleware) publicly.

# ─────────────────────────────────────────────────────────────────────────────
# STEP 8 — Firebase: add irggdp.com as authorised domain
# ─────────────────────────────────────────────────────────────────────────────
# Firebase Console → Authentication → Settings → Authorised domains
# Add: irggdp.com  and  www.irggdp.com

# ─────────────────────────────────────────────────────────────────────────────
# STEP 9 — Firebase: deploy hosting + functions + rules (from your Mac)
# ─────────────────────────────────────────────────────────────────────────────
cd /Users/prathmeshwalimbe/Downloads/irg_gdp
firebase deploy --project irggdp

# Verify frontend is live:
# https://irggdp.com  → IRG_GDP landing page
# https://irggdp.com/wallet  → wallet.html

# ─────────────────────────────────────────────────────────────────────────────
# STEP 10 — Smoke tests
# ─────────────────────────────────────────────────────────────────────────────
# 1. Open https://irggdp.com — landing page loads, no console errors
# 2. Click Sign On — register a test household user
# 3. Sign in — dashboard loads
# 4. Click 💼 My Wallet — wallet page loads, shows "Created — awaiting activation"
# 5. Complete wallet activation (set password, write seed, add 2 nominees)
# 6. Check https://irggdp.com/admin/ — Django admin accessible
# 7. Check SSL: https://www.ssllabs.com/ssltest/analyze.html?d=irggdp.com

# ─────────────────────────────────────────────────────────────────────────────
# EVERY FUTURE DEPLOY (after code changes)
# ─────────────────────────────────────────────────────────────────────────────
# From your Mac:
cd /Users/prathmeshwalimbe/Downloads/irg_gdp
git add -A && git commit -m "your message" && git push origin main

# Then on EC2:
ssh -i /Users/prathmeshwalimbe/Downloads/irg-key.pem ec2-user@43.205.237.197 \
  "bash /home/ec2-user/irg_gdp/infra/ec2-deploy-commands.sh"

# Or for Cloud Run (if using that path instead of EC2):
bash /Users/prathmeshwalimbe/Downloads/irg_gdp/deploy.sh
