#!/bin/sh
# Gateway entrypoint script
# Generates nginx.conf from template with environment variable substitution

# Default values for domain configuration
ATOMSX_PREVIEW_DOMAIN="${ATOMSX_PREVIEW_DOMAIN:-preview.local}"
ATOMSX_DEPLOY_DOMAIN="${ATOMSX_DEPLOY_DOMAIN:-apps.local}"

# Use envsubst to replace environment variables in the template
envsubst '${ATOMSX_PREVIEW_DOMAIN} ${ATOMSX_DEPLOY_DOMAIN}' < /usr/local/openresty/nginx/conf/nginx.conf.template > /usr/local/openresty/nginx/conf/nginx.conf

# Start OpenResty
exec openresty -g "daemon off;"