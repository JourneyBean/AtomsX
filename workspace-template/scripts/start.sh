#!/bin/bash
# Workspace Startup Script
# Starts the Preview Server and keeps the container running

set -e

echo "Starting Workspace..."

# Change to workspace directory
cd /workspace

# Start Vite dev server for Vue project
echo "Starting Preview Server on port 3000..."
npm run dev -- --host 0.0.0.0 --port 3000 &

# Keep container running
wait