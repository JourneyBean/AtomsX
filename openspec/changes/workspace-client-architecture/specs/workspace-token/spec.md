# Workspace Token Capability

## Purpose

Enable secure authentication of Workspace Client connections through time-limited tokens.

## ADDED Requirements

### Requirement: System generates token on Workspace creation

The system SHALL generate a unique authentication token when a Workspace is created.

#### Scenario: Token generated
- **WHEN** Workspace container creation task starts
- **THEN** system generates a 32-byte URL-safe random token
- **AND** system creates WorkspaceToken record with: workspace_id, token, created_at
- **AND** system injects token into container environment as ATOMSX_AUTH_TOKEN

#### Scenario: Token uniqueness
- **WHEN** token is generated
- **THEN** system verifies token does not already exist in database
- **AND** if collision occurs, system regenerates token

### Requirement: System validates token on WebSocket connection

The system SHALL validate token when Workspace Client attempts WebSocket connection.

#### Scenario: Valid token accepted
- **WHEN** Workspace Client connects with token that exists in WorkspaceToken table
- **AND** token belongs to the workspace_id in the URL
- **THEN** system accepts connection

#### Scenario: Invalid token rejected
- **WHEN** Workspace Client connects with token that does not exist in WorkspaceToken table
- **THEN** system rejects connection with code 4001

#### Scenario: Token-workspace mismatch rejected
- **WHEN** Workspace Client connects with valid token for workspace A
- **BUT** URL contains workspace_id for workspace B
- **THEN** system rejects connection with code 4001

### Requirement: System deletes token on Workspace deletion

The system SHALL delete the token when Workspace is deleted or container is stopped.

#### Scenario: Token deleted on Workspace deletion
- **WHEN** Workspace deletion task completes
- **THEN** system deletes associated WorkspaceToken record
- **AND** system logs token deletion

#### Scenario: Token deleted on container stop detected
- **WHEN** Celery task detects container has stopped
- **THEN** system deletes associated WorkspaceToken record
- **AND** system logs token deletion

### Requirement: Token is not logged or exposed

The system SHALL ensure token values are not exposed in logs or API responses.

#### Scenario: Token not in audit logs
- **WHEN** audit log is created for Workspace event
- **THEN** token value is NOT included in audit record

#### Scenario: Token not in API response
- **WHEN** API returns Workspace details
- **THEN** token value is NOT included in response

#### Scenario: Token not in error messages
- **WHEN** error occurs involving token
- **THEN** error message does not contain token value