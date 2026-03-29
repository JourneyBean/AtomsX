## MODIFIED Requirements

### Requirement: Logged-in user can access Preview for their Workspace

The system SHALL allow logged-in users to access the Preview URL for Workspaces they own, viewing the real-time running application. Authentication can be verified via session cookie OR preview token query parameter.

#### Scenario: Access own Workspace Preview with session
- **WHEN** logged-in user navigates to Preview URL for Workspace they own with valid session cookie
- **THEN** OpenResty gateway intercepts the request
- **AND** gateway forwards authentication verification to Django control plane
- **AND** Django verifies user session and Workspace ownership
- **AND** gateway proxies request to Workspace container's Preview Server
- **AND** user sees the running application in Preview frame

#### Scenario: Access own Workspace Preview with token
- **WHEN** user navigates to Preview URL with valid `?token=<preview_token>` query parameter
- **THEN** OpenResty gateway intercepts the request
- **AND** gateway forwards token and workspace_id to Django `/api/auth/verify/`
- **AND** Django validates token in Redis and verifies workspace ownership
- **AND** gateway proxies request to Workspace container's Preview Server
- **AND** user sees the running application in Preview frame

#### Scenario: Preview authentication success
- **WHEN** user accesses Preview URL with valid session OR valid token
- **THEN** system returns the Preview content from Workspace container
- **AND** system does not require additional login prompt

#### Scenario: Preview authentication failure - no session or token
- **WHEN** user accesses Preview URL without valid session AND without valid token
- **THEN** system returns HTTP 401 Unauthorized
- **AND** system does not serve any Preview content
- **AND** system optionally redirects to login page

#### Scenario: Preview access forbidden - not owner
- **WHEN** user accesses Preview URL for Workspace owned by another user (via session or token)
- **THEN** system returns HTTP 403 Forbidden
- **AND** system does not serve any Preview content