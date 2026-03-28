# AtomsX Workspace Base Image
# Includes: Node.js, Python, Agent Runtime, Preview Server

FROM node:20-slim

# Proxy support build arguments
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

# Install system dependencies
RUN HTTP_PROXY=${HTTP_PROXY} HTTPS_PROXY=${HTTPS_PROXY} NO_PROXY=${NO_PROXY} \
    http_proxy=${http_proxy} https_proxy=${https_proxy} no_proxy=${no_proxy} \
    apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create workspace directory
WORKDIR /workspace

# Create virtual environment for Agent runtime
RUN python3 -m venv /opt/agent-env

# Install Python packages for Agent
RUN HTTP_PROXY=${HTTP_PROXY} HTTPS_PROXY=${HTTPS_PROXY} NO_PROXY=${NO_PROXY} \
    http_proxy=${http_proxy} https_proxy=${https_proxy} no_proxy=${no_proxy} \
    /opt/agent-env/bin/pip install --no-cache-dir \
    anthropic \
    python-dotenv

# Copy default Vue project template
COPY template/ /workspace/

# Install Node dependencies for the template with proxy support
RUN if [ -n "$HTTP_PROXY" ]; then \
        npm config set proxy $HTTP_PROXY; \
    fi && \
    if [ -n "$HTTPS_PROXY" ]; then \
        npm config set https-proxy $HTTPS_PROXY; \
    fi && \
    npm install && \
    npm config delete proxy 2>/dev/null || true && \
    npm config delete https-proxy 2>/dev/null || true

# Copy startup script
COPY scripts/start.sh /start.sh
RUN chmod +x /start.sh

# Environment variables
ENV NODE_ENV=development
ENV WORKSPACE_PORT=3000

# Expose preview server port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/ || exit 1

# Start preview server by default
CMD ["/start.sh"]