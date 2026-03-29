FROM openresty/openresty:alpine

# Install gettext for envsubst, and perl+curl for OPM
RUN apk add --no-cache gettext perl curl

# Install lua-resty-http for HTTP client support in Lua
RUN /usr/local/openresty/bin/opm get ledgetech/lua-resty-http

# Copy entrypoint script and config template
COPY docker-entrypoint.sh /docker-entrypoint.sh
COPY nginx.conf.template /usr/local/openresty/nginx/conf/nginx.conf.template
COPY lua /usr/local/openresty/lua

# Make entrypoint executable
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]