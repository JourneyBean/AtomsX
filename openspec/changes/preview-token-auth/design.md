## Context

Current realtime preview uses session-based authentication. The iframe embedding at preview subdomain (`{workspace-id}.preview.local`) cannot share cookies with the main app (`localhost:18080`) due to cross-origin restrictions and `SameSite=Lax` cookie policy. This blocks preview access when embedded in iframe.

## Goals / Non-Goals

**Goals:**
- Enable iframe preview access without session cookie dependency
- Maintain security: tokens scoped to workspace, time-limited, tied to user session
- Keep implementation simple for MVP (opaque token, not JWT)

**Non-Goals:**
- Not replacing session auth for API endpoints (preview only)
- Not implementing complex token schemes (refresh, revocation lists)
- Not supporting token reuse across sessions

## Decisions

### Token Storage: Redis Cache (not Database)

**Choice**: Store tokens in Redis with TTL, not PostgreSQL.

**Rationale**:
- Tokens are ephemeral, short-lived (5-10 min)
- No persistence needed beyond TTL
- Redis already used for caching and Celery
- Simpler cleanup (auto-expire)

**Alternatives considered**:
- Database table: Adds complexity, requires cleanup job
- JWT: No server-side validation, harder to revoke

### Token Format: Opaque UUID

**Choice**: Use random UUID token, not JWT.

**Rationale**:
- Simpler implementation
- Server-side validation allows revocation
- No cryptographic complexity for MVP
- Token itself carries no data (just lookup key)

### Token Scope: Single Workspace

**Choice**: Each token is scoped to one workspace ID.

**Rationale**:
- Prevents token reuse across workspaces
- Clear audit trail (token → user → workspace)
- Matches user intent (preview specific workspace)

### Token Lifetime: 10 Minutes

**Choice**: Token expires after 10 minutes.

**Rationale**:
- Long enough for development session
- Short enough to limit exposure if leaked
- User can regenerate if needed

### Gateway Validation: Direct Backend Call

**Choice**: Gateway calls backend `/api/auth/verify/` with token parameter.

**Rationale**:
- Reuses existing auth_check.lua pattern
- Backend validates token against Redis
- Centralized validation logic

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Token leaked via URL sharing | Short TTL limits exposure; token scoped to single workspace; audit logging |
| URL with token visible in browser history | Tokens are one-time use optional; recommend regenerating |
| Redis unavailable | Gateway returns 503; fallback to session auth when available |
| Token in URL query param visible to JS in iframe | Same-origin policy applies; iframe JS cannot access parent URL |