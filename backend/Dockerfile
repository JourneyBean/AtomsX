FROM python:3.12-slim

# Proxy support build arguments
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

WORKDIR /app

# Install system dependencies (including curl for healthcheck)
RUN HTTP_PROXY=${HTTP_PROXY} HTTPS_PROXY=${HTTPS_PROXY} NO_PROXY=${NO_PROXY} \
    http_proxy=${http_proxy} https_proxy=${https_proxy} no_proxy=${no_proxy} \
    apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock .python-version ./

# Install dependencies using uv
# --frozen ensures exact versions from lock file
# --no-dev excludes development dependencies (pytest, pytest-cov, etc.)
# uv sync automatically creates .venv in project directory
RUN HTTP_PROXY=${HTTP_PROXY} HTTPS_PROXY=${HTTPS_PROXY} NO_PROXY=${NO_PROXY} \
    http_proxy=${http_proxy} https_proxy=${https_proxy} no_proxy=${no_proxy} \
    uv sync --frozen --no-dev

# Copy application code
COPY . .

# Copy and set up entrypoint script
RUN chmod +x /app/docker-entrypoint.dev.sh

# Collect static files (for production)
RUN uv run python manage.py collectstatic --noinput || true

EXPOSE 8000

# Use entrypoint to run migrations before starting server
ENTRYPOINT ["./docker-entrypoint.dev.sh"]