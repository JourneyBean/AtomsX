## 1. Backend - Token Generation Endpoint

- [x] 1.1 Create PreviewToken model with fields: token (UUID), workspace_id, user_id, created_at
- [x] 1.2 Add token generation logic in WorkspaceViewSet (POST `/api/workspaces/{id}/preview-token/`)
- [x] 1.3 Store token in Redis with key format `preview_token:{token}` and TTL 600 seconds
- [x] 1.4 Add ownership verification before token generation
- [x] 1.5 Add audit log for PREVIEW_TOKEN_GENERATED event

## 2. Backend - Token Validation

- [x] 2.1 Update AuthVerifyView to accept `token` query parameter
- [x] 2.2 Implement token validation: check Redis, verify workspace_id match
- [x] 2.3 Return authorized response with container_host on valid token
- [x] 2.4 Return 401 on invalid/expired token, 403 on scope mismatch
- [x] 2.5 Add audit log for PREVIEW_ACCESS event on token validation

## 3. Gateway - Token Authentication

- [x] 3.1 Update auth_check.lua to extract `token` from query parameter
- [x] 3.2 Pass token to backend `/api/auth/verify/?token=...&workspace_id=...`
- [x] 3.3 Cache auth result with token as key (not session)

## 4. Frontend - Token Integration

- [x] 4.1 Add API method to generate preview token for workspace
- [x] 4.2 Construct preview iframe URL with `?token=<token>` parameter
- [x] 4.3 Handle token generation failure (show error message)
- [x] 4.4 Add token regeneration button in preview panel

## 5. Testing

- [x] 5.1 Test token generation endpoint (success, forbidden, unauthorized)
- [x] 5.2 Test token validation (valid, expired, scope mismatch)
- [x] 5.3 Test preview URL access with token through gateway
- [ ] 5.4 Test iframe preview with token works without session cookie

## 6. Security & Cleanup

- [ ] 6.1 Verify tokens are not logged in URLs (strip from access logs)
- [ ] 6.2 Add rate limiting to token generation endpoint
- [ ] 6.3 Document token lifetime and regeneration guidance

## Notes

### Implementation Status

**Completed:**
- Backend token generation (`/api/workspaces/{id}/preview-token/`)
- Backend token validation in AuthVerifyView
- Gateway auth_check.lua updated to support token parameter
- Frontend generates token and constructs iframe URL

**Pending Investigation:**
- Nginx `proxy_pass` with variable (`$container_host`) requires resolver directive
- Current 503 response is from workspace placeholder server (correct behavior for start_failed)
- Need to verify nginx can resolve container hostname via Docker DNS

The auth flow is working:
1. Frontend generates token via POST `/api/workspaces/{id}/preview-token/`
2. Gateway receives request with `?token=...`
3. Gateway calls backend `/api/auth/verify/` with token
4. Backend validates token from Redis, returns `container_host`
5. Gateway sets `$container_host` nginx variable
6. Proxy to workspace container returns placeholder response (503 - start_failed)