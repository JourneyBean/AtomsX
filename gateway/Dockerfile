FROM openresty/openresty:alpine

# Install gettext for envsubst, perl+curl for OPM, and openssl for certificates
RUN apk add --no-cache gettext perl curl openssl

# Install lua-resty-http for HTTP client support in Lua
RUN /usr/local/openresty/bin/opm get ledgetech/lua-resty-http

# Generate snakeoil SSL certificates for development
RUN mkdir -p /etc/nginx/ssl && \
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/snakeoil.key \
    -out /etc/nginx/ssl/snakeoil.crt \
    -subj "/CN=localhost/O=AtomsX Dev/C=US"

# Copy entrypoint script and config template
COPY docker-entrypoint.sh /docker-entrypoint.sh
COPY nginx.conf.template /usr/local/openresty/nginx/conf/nginx.conf.template
COPY lua /usr/local/openresty/lua

# Make entrypoint executable
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]