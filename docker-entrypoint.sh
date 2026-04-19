#!/bin/sh
set -e
python manage.py migrate --noinput
exec gunicorn wsgi:application \
  --bind "0.0.0.0:${PORT:-8080}" \
  --workers 2 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
