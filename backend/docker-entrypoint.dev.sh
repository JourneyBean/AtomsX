#!/bin/sh
set -e

echo "Running Django migrations..."
uv run python manage.py migrate --noinput

echo "Starting Django development server..."
exec uv run python manage.py runserver 0.0.0.0:8000