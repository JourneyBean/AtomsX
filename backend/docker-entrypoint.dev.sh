#!/bin/sh
set -e

echo "Running Django migrations..."
uv run python manage.py migrate --noinput

echo "Starting Django ASGI server (daphne)..."
# Use daphne for WebSocket support (Django Channels)
exec uv run daphne -b 0.0.0.0 -p 8000 config.asgi:application