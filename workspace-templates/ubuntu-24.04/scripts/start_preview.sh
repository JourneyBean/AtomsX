#!/bin/bash
# Preview Server Startup Script
# Handles: start_app.sh detection, execution, and fallback to placeholder

set -e

# Load nvm to make node available
export NVM_NODEJS_ORG_MIRROR=https://mirrors.ustc.edu.cn/node/
[ -s "$HOME/.nvm/nvm.sh" ] && \. "$HOME/.nvm/nvm.sh"

WORKSPACE_DIR="/home/user/workspace"
START_SCRIPT="$WORKSPACE_DIR/start_app.sh"
PLACEHOLDER_SCRIPT="/opt/workspace-client/scripts/placeholder_server.py"

# Ensure log directory exists
mkdir -p /home/user/logs

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Start placeholder server with message
start_placeholder() {
    local reason="$1"
    local detail="$2"
    log "Starting placeholder server: $reason"
    export PLACEHOLDER_MESSAGE="$reason"
    export PLACEHOLDER_DETAIL="$detail"
    exec python3 "$PLACEHOLDER_SCRIPT"
}

# Main logic
log "Preview server starting..."

# Check if start_app.sh exists
if [ ! -f "$START_SCRIPT" ]; then
    start_placeholder "no_start_script" "Please create start_app.sh in workspace directory"
    exit 0
fi

# Check if executable
if [ ! -x "$START_SCRIPT" ]; then
    log "start_app.sh not executable, attempting to fix..."
    chmod +x "$START_SCRIPT" 2>/dev/null || {
        start_placeholder "permission_denied" "Cannot make start_app.sh executable"
        exit 0
    }
fi

# Execute start_app.sh
log "Executing start_app.sh..."
cd "$WORKSPACE_DIR"

# Capture error output
ERROR_OUTPUT=$(mktemp)
if bash "$START_SCRIPT" 2>"$ERROR_OUTPUT"; then
    # Script succeeded, keep running
    wait
else
    EXIT_CODE=$?
    ERROR_MSG=$(cat "$ERROR_OUTPUT" 2>/dev/null || echo "Unknown error")
    rm -f "$ERROR_OUTPUT"

    log "start_app.sh failed with exit code $EXIT_CODE: $ERROR_MSG"
    start_placeholder "start_failed" "start_app.sh failed (exit $EXIT_CODE): $ERROR_MSG"
fi