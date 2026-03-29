## Why

The iframe-based preview cannot share session cookies due to cross-origin restrictions (preview subdomain vs main app domain). The current `SESSION_COOKIE_SAMESITE = 'Lax'` configuration blocks iframe requests from carrying cookies. This blocks the realtime preview feature from working in the intended iframe layout.

## What Changes

- Add preview token generation endpoint in Django backend
- Modify gateway auth check to accept token via URL query parameter
- Frontend iframe URL will include `?token=<preview_token>` for preview access
- Tokens are workspace-scoped, time-limited, and single-use (optional)

## Capabilities

### New Capabilities
- `preview-token`: Token-based authentication mechanism for preview access, enabling iframe embedding without session cookie dependency

### Modified Capabilities
- `realtime-preview`: Authentication mechanism changes from session-based to token-based. The requirement "gateway forwards authentication verification to Django control plane" now supports token parameter as alternative to session cookie.

## Impact

- **Backend**: New API endpoint `/api/workspaces/{id}/preview-token/` for token generation
- **Gateway**: `auth_check.lua` modified to extract and validate token from query parameter
- **Frontend**: Preview iframe URL construction includes token parameter
- **Security**: Preview tokens are short-lived (5-10 minutes), scoped to specific workspace, tied to user session

## Non-goals

- Not replacing session authentication for API access (preview only)
- Not implementing JWT or complex token schemes (simple opaque token sufficient for MVP)
- Not supporting token refresh mechanism (regenerate new token when needed)