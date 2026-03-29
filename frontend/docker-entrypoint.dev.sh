#!/bin/sh
set -e

# npm registry mirror (defaults to npmmirror for better China connectivity)
NPM_REGISTRY="${NPM_REGISTRY:-https://registry.npmmirror.com}"

# Configure npm registry
npm config set registry $NPM_REGISTRY

# Install dependencies if node_modules is missing or empty, with retry logic
if [ ! -d "/app/node_modules" ] || [ -z "$(ls -A /app/node_modules 2>/dev/null)" ]; then
    echo "Installing npm dependencies from $NPM_REGISTRY..."

    for i in 1 2 3; do
        echo "Attempt $i: npm install..."
        if npm install --prefer-offline --no-audit; then
            echo "npm install succeeded on attempt $i"
            break
        fi
        if [ $i -lt 3 ]; then
            sleep=$((i * 5))
            echo "npm install failed, retrying in $sleep seconds..."
            sleep $sleep
        else
            echo "npm install failed after 3 attempts"
            exit 1
        fi
    done
fi

# Run the provided command, or default to dev server
if [ $# -gt 0 ]; then
    exec "$@"
else
    exec npm run dev -- --host
fi