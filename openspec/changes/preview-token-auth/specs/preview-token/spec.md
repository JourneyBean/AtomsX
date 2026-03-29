## ADDED Requirements

### Requirement: User can generate preview token for their workspace

The system SHALL allow authenticated users to generate a preview access token for workspaces they own.

#### Scenario: Generate preview token for owned workspace
- **WHEN** authenticated user requests token for workspace they own via `/api/workspaces/{id}/preview-token/`
- **THEN** system generates a unique opaque token
- **AND** system stores token in Redis with: key=`preview_token:{token}`, value={user_id, workspace_id}, TTL=600 seconds
- **AND** system returns JSON with `{token, expires_at, workspace_id}`
- **AND** system creates audit log with event_type="PREVIEW_TOKEN_GENERATED"

#### Scenario: Generate token for non-owned workspace
- **WHEN** authenticated user requests token for workspace owned by another user
- **THEN** system returns HTTP 403 Forbidden
- **AND** system does not generate token

#### Scenario: Generate token without authentication
- **WHEN** unauthenticated user requests preview token
- **THEN** system returns HTTP 401 Unauthorized

### Requirement: Preview token is validated by gateway

The system SHALL validate preview tokens presented via URL query parameter before granting preview access.

#### Scenario: Valid token grants preview access
- **WHEN** gateway receives preview URL with valid `?token=<token>` parameter
- **THEN** gateway calls backend `/api/auth/verify/?token=<token>&workspace_id=<id>`
- **AND** backend validates token exists in Redis
- **AND** backend verifies workspace_id matches token scope
- **AND** gateway receives `{authorized: true, container_host: "..."}`
- **AND** gateway proxies request to workspace container

#### Scenario: Expired or invalid token denies access
- **WHEN** gateway receives preview URL with expired or non-existent token
- **THEN** backend returns HTTP 401 Unauthorized
- **AND** gateway returns "Authentication required" message

#### Scenario: Token scope mismatch denies access
- **WHEN** gateway receives preview URL with token scoped to different workspace
- **THEN** backend returns HTTP 403 Forbidden
- **AND** gateway returns "Access denied" message

### Requirement: Preview token has limited lifetime

The system SHALL enforce a maximum lifetime of 10 minutes for preview tokens.

#### Scenario: Token expires after TTL
- **WHEN** token has been stored in Redis for more than TTL seconds
- **THEN** Redis automatically removes token
- **AND** subsequent validation fails with 401

### Requirement: Token generation events are audited

The system SHALL record audit logs for token generation events.

#### Scenario: Token generation audit
- **WHEN** user generates preview token
- **THEN** system creates audit record with: timestamp, user_id, workspace_id, event_type="PREVIEW_TOKEN_GENERATED"

#### Scenario: Token validation audit
- **WHEN** token is validated for preview access
- **THEN** system creates audit record with: timestamp, user_id (from token), workspace_id, ip_address, event_type="PREVIEW_ACCESS"