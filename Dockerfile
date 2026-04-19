# Cloud Run deploy image for irg_gdp Django backend
# The container is fronted by Firebase Hosting (see firebase.json rewrites).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# System deps for psycopg2 and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir firebase-admin>=6.5.0 google-cloud-firestore>=2.16.0

COPY backend /app

# Collect static files (Whitenoise serves them)
RUN python manage.py collectstatic --noinput || true

# Run with gunicorn
CMD gunicorn wsgi:application --bind 0.0.0.0:${PORT} --workers 2 --timeout 60
