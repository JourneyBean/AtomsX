#!/bin/sh
set -e

# Install dependencies if node_modules is missing or empty
if [ ! -d "/app/node_modules" ] || [ -z "$(ls -A /app/node_modules 2>/dev/null)" ]; then
    echo "Installing npm dependencies..."
    npm install
fi

# Run the provided command, or default to dev server
if [ $# -gt 0 ]; then
    exec "$@"
else
    exec npm run dev -- --host
fi