-- Authentication and routing module for Preview access
-- Handles: auth verification, workspace ownership, container resolution
-- Supports: session cookie OR preview token query parameter

local http = require "resty.http"
local cjson = require "cjson"
local cache = ngx.shared.workspace_cache

local M = {}

-- Configuration
local AUTH_VERIFY_URL = "http://backend:8000/api/auth/verify/"
local CACHE_TTL = 60  -- Cache auth results for 60 seconds

--- Check authentication and workspace access
-- @param workspace_id The UUID of the workspace being accessed
function M.check(workspace_id)
    if not workspace_id then
        ngx.status = 400
        ngx.say("Bad Request: Missing workspace ID")
        ngx.exit(400)
        return
    end

    -- Extract token from query parameter or cookie
    local token = ngx.var.arg_token

    -- If no token in query, check cookie
    if not token then
        local cookie_header = ngx.var.http_cookie or ""
        -- Parse preview_token cookie
        token = ngx.re.match(cookie_header, "preview_token=([^;]+)")
        if token then
            token = token[1]
        end
    end

    -- Build cache key: prefer token, fall back to session
    local cache_key
    if token then
        cache_key = "token:" .. token .. ":" .. workspace_id
    else
        local session_id = ngx.var.cookie_sessionid or ngx.var.http_authorization or "anonymous"
        cache_key = "session:" .. session_id .. ":" .. workspace_id
    end

    -- Check cache
    local cached = cache:get(cache_key)
    if cached then
        local result = cjson.decode(cached)
        if result.authorized then
            ngx.var.container_host = result.container_host
            ngx.log(ngx.INFO, "Using cached auth for workspace ", workspace_id)
            return
        else
            M._deny_access(result.reason or "unauthorized")
            return
        end
    end

    -- Build backend URL with token parameter if present
    local verify_url = AUTH_VERIFY_URL .. "?workspace_id=" .. workspace_id
    if token then
        verify_url = verify_url .. "&token=" .. token
    end

    -- Verify with backend
    local httpc = http.new()
    local res, err = httpc:request_uri(verify_url, {
        method = "GET",
        headers = {
            ["Cookie"] = ngx.var.http_cookie or "",
            ["X-Workspace-Id"] = workspace_id,
        },
        keepalive_timeout = 60,
        keepalive_pool = 10,
    })

    if not res then
        ngx.log(ngx.ERR, "Auth verification failed: ", err)
        ngx.status = 503
        ngx.say("Authentication service unavailable")
        ngx.exit(503)
        return
    end

    if res.status == 200 then
        local body = cjson.decode(res.body)

        -- Cache the result
        local cache_value = cjson.encode({
            authorized = true,
            container_host = body.container_host or "localhost:3000",
        })
        cache:set(cache_key, cache_value, CACHE_TTL)

        -- Set the container host for proxy_pass
        ngx.var.container_host = body.container_host or M._get_container_host(workspace_id)

        ngx.log(ngx.INFO, "Preview access granted for user ", body.user_id or "unknown",
                " to workspace ", workspace_id)

    elseif res.status == 401 then
        M._deny_access("unauthorized")

    elseif res.status == 403 then
        M._deny_access("forbidden")

    elseif res.status == 404 then
        M._deny_access("not_found", 404)

    else
        ngx.log(ngx.ERR, "Auth verification returned status ", res.status)
        M._deny_access("error", 503)
    end
end

--- Get the container host for a workspace
-- For MVP, we use Docker DNS to resolve container names
-- Container naming: workspace-{uuid}
function M._get_container_host(workspace_id)
    -- Docker container naming convention
    -- The container name is workspace-{uuid}
    -- Docker's internal DNS resolves this to the container IP
    return "workspace-" .. workspace_id .. ":3000"
end

--- Deny access with appropriate status
function M._deny_access(reason, status)
    status = status or 401

    local messages = {
        unauthorized = "Authentication required. Please log in to access this workspace.",
        forbidden = "Access denied. You do not have permission to access this workspace.",
        not_found = "Workspace not found.",
        error = "Service temporarily unavailable.",
    }

    -- Cache the denial (shorter TTL for errors)
    cache:set(ngx.var.cookie_sessionid or "anonymous", cjson.encode({
        authorized = false,
        reason = reason,
    }), 10)

    ngx.status = status
    ngx.say(messages[reason] or "Access denied")
    ngx.exit(status)
end

return M