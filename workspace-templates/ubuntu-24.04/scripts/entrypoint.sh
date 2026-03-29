#!/bin/bash
# Entrypoint script for workspace container
# Starts workspace-client with health monitoring

set -e

echo "Starting Workspace Client..."

# Load nvm to make node available
export NVM_NODEJS_ORG_MIRROR=https://mirrors.ustc.edu.cn/node/
[ -s "$HOME/.nvm/nvm.sh" ] && \. "$HOME/.nvm/nvm.sh"

# Configuration from environment
WORKSPACE_ID="${WORKSPACE_ID:-}"
ATOMSX_AUTH_TOKEN="${ATOMSX_AUTH_TOKEN:-}"
ATOMSX_BACKEND_WS_URL="${ATOMSX_BACKEND_WS_URL:-ws://backend:8000}"
ATOMSX_BACKEND_HTTP_URL="${ATOMSX_BACKEND_HTTP_URL:-http://backend:8000}"
ATOMSX_INTERNAL_API_TOKEN="${ATOMSX_INTERNAL_API_TOKEN:-dev-internal-token}"

# Verify required environment variables
if [ -z "$WORKSPACE_ID" ]; then
    echo "ERROR: WORKSPACE_ID is required"
    exit 1
fi

if [ -z "$ATOMSX_AUTH_TOKEN" ]; then
    echo "ERROR: ATOMSX_AUTH_TOKEN is required"
    exit 1
fi

# Ensure workspace and history directories exist and are writable
# These are mounted from host, but may need permission fixes
for dir in /home/user/workspace /home/user/history; do
    if [ ! -d "$dir" ]; then
        echo "Creating directory: $dir"
        mkdir -p "$dir" 2>/dev/null || {
            sudo mkdir -p "$dir"
            sudo chown user:user "$dir"
        }
    fi

    if [ ! -w "$dir" ]; then
        echo "Warning: Cannot write to $dir, fixing permissions..."
        sudo chown user:user "$dir" 2>/dev/null || true
    fi
done

# Export environment for workspace-client
export ATOMSX_AUTH_TOKEN
export ATOMSX_BACKEND_WS_URL
export ATOMSX_BACKEND_HTTP_URL
export ATOMSX_INTERNAL_API_TOKEN
export WORKSPACE_ID

# Start workspace-client using uv
cd /opt/workspace-client

# Run with uv in the virtual environment
exec uv run python -m workspace_client.main