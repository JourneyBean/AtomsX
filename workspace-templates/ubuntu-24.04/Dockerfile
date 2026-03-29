# Workspace Image for AtomsX
# Based on Ubuntu 24.04 with Python 3.12, Node.js 24 (via nvm), and workspace-client

FROM ubuntu:24.04

# Proxy support build arguments
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Configure apt to use USTC mirror (faster in China)
RUN sed -i 's|http://archive.ubuntu.com|http://mirrors.ustc.edu.cn|g' /etc/apt/sources.list.d/ubuntu.sources \
    && sed -i 's|http://security.ubuntu.com|http://mirrors.ustc.edu.cn|g' /etc/apt/sources.list.d/ubuntu.sources

# Install system dependencies
RUN HTTP_PROXY=${HTTP_PROXY} HTTPS_PROXY=${HTTPS_PROXY} NO_PROXY=${NO_PROXY} \
    http_proxy=${http_proxy} https_proxy=${https_proxy} no_proxy=${no_proxy} \
    apt-get update && apt-get install -y \
    # Python
    python3.12 \
    python3.12-venv \
    python3-pip \
    # Build tools and utilities
    curl \
    wget \
    git \
    sudo \
    ca-certificates \
    gnupg \
    build-essential \
    # Process management
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create user with uid=1000, gid=1000
# Ubuntu 24.04 has 'ubuntu' user with UID/GID 1000 - delete and recreate
RUN userdel -r ubuntu 2>/dev/null || true \
    && groupadd -g 1000 user \
    && useradd -u 1000 -g 1000 -m -s /bin/bash user \
    && echo "user ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Ensure user home directory has correct permissions
RUN chown -R user:user /home/user

# Configure uv to use TUNA mirror (written to user config for runtime use)
RUN mkdir -p /home/user/.config/uv \
    && printf '[[index]]\nurl = "https://pypi.tuna.tsinghua.edu.cn/simple"\ndefault = true\n' > /home/user/.config/uv/uv.toml \
    && chown -R user:user /home/user/.config

# Set up workspace directories (will be mounted separately at runtime)
RUN mkdir -p /home/user/workspace \
    && mkdir -p /home/user/history \
    && mkdir -p /home/user/logs \
    && mkdir -p /home/user/.var/run \
    && chown -R user:user /home/user

# Install nvm and Node.js 24 for the user
# Note: NVM_NODEJS_ORG_MIRROR should NOT end with /
ENV NVM_DIR=/home/user/.nvm
ENV NVM_NODEJS_ORG_MIRROR=https://npmmirror.com/mirrors/node/

USER user
RUN export HTTP_PROXY=${HTTP_PROXY} HTTPS_PROXY=${HTTPS_PROXY} NO_PROXY=${NO_PROXY} \
    http_proxy=${http_proxy} https_proxy=${https_proxy} no_proxy=${no_proxy} && \
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash \
    && . "$NVM_DIR/nvm.sh" \
    && unset http_proxy https_proxy no_proxy HTTP_PROXY HTTPS_PROXY NO_PROXY \
    && nvm install 24 \
    && nvm use 24 \
    && nvm alias default 24 \
    && npm config set registry https://registry.npmmirror.com

# Add nvm to user's bashrc for interactive shells
RUN echo 'export NVM_DIR="$HOME/.nvm"' >> ~/.bashrc \
    && echo 'export NVM_NODEJS_ORG_MIRROR=https://mirrors.ustc.edu.cn/node' >> ~/.bashrc \
    && echo '[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"' >> ~/.bashrc

# Copy workspace-client source code
USER root
COPY README.md pyproject.toml /opt/workspace-client/
COPY src/ /opt/workspace-client/src/
COPY scripts/ /opt/workspace-client/scripts/

# Install workspace-client dependencies with uv (use TUNA mirror for build)
ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
WORKDIR /opt/workspace-client
RUN uv sync

# Make scripts executable
RUN chmod +x /opt/workspace-client/scripts/start_preview.sh

# Copy supervisord configuration
RUN mkdir -p /var/log/supervisor
COPY scripts/supervisord.conf /etc/supervisor/supervisord.conf
COPY scripts/programs.conf /etc/supervisor/conf.d/programs.conf

# Set up working directory
WORKDIR /home/user/workspace

# Switch to non-root user
USER user

# Expose preview server port
EXPOSE 3000

# Health check for supervisord and its child processes
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD pgrep -f "supervisord" > /dev/null && pgrep -f "workspace_client.main" > /dev/null || exit 1

# Entrypoint starts supervisord which manages workspace-client and preview-server
ENTRYPOINT ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]