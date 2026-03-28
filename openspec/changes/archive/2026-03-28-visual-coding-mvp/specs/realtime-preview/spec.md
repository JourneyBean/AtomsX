## ADDED Requirements

### Requirement: Logged-in user can access Preview for their Workspace

The system SHALL allow logged-in users to access the Preview URL for Workspaces they own, viewing the real-time running application.

#### Scenario: Access own Workspace Preview
- **WHEN** logged-in user navigates to Preview URL for Workspace they own (e.g., `<workspace-id>.preview.local`)
- **THEN** OpenResty gateway intercepts the request
- **AND** gateway forwards authentication verification to Django control plane
- **AND** Django verifies user session and Workspace ownership
- **AND** gateway proxies request to Workspace container's Preview Server
- **AND** user sees the running application in Preview frame

#### Scenario: Preview authentication success
- **WHEN** user accesses Preview URL with valid session
- **THEN** system returns the Preview content from Workspace container
- **AND** system does not require additional login prompt

#### Scenario: Preview authentication failure - no session
- **WHEN** user accesses Preview URL without valid session (not logged in or session expired)
- **THEN** system returns HTTP 401 Unauthorized
- **AND** system does not serve any Preview content
- **AND** system optionally redirects to login page

#### Scenario: Preview access forbidden - not owner
- **WHEN** logged-in user accesses Preview URL for Workspace owned by another user
- **THEN** system returns HTTP 403 Forbidden
- **AND** system does not serve any Preview content

### Requirement: Preview reflects Workspace file changes in real-time

The system SHALL reflect file modifications in Workspace to the Preview display with minimal latency.

#### Scenario: File change triggers Preview update
- **WHEN** Agent modifies source file in Workspace container
- **THEN** Workspace Preview Server detects file change (via file watcher or Agent signal)
- **AND** Preview Server triggers hot module replacement (HMR) or reload
- **AND** Preview frame in frontend updates to show new content
- **AND** update latency is less than 2 seconds for typical changes

#### Scenario: Preview Server restart after significant change
- **WHEN** file change requires Preview Server restart (e.g., dependency update, config change)
- **THEN** system restarts Preview Server in Workspace container
- **AND** system notifies frontend of temporary Preview unavailable state
- **AND** Preview resumes within 10 seconds

### Requirement: Preview URL is unique per Workspace

The system SHALL provide a unique Preview URL for each Workspace.

#### Scenario: Unique Preview URL
- **WHEN** Workspace is created and status is "running"
- **THEN** system assigns Preview URL: `<workspace-id>.preview.<domain>`
- **AND** Preview URL is stored in Workspace metadata
- **AND** URL is unique and not shared with other Workspaces

#### Scenario: Preview URL resolves to correct Workspace
- **WHEN** user accesses `<workspace-id>.preview.local`
- **THEN** gateway routes request to the specific Workspace container
- **AND** no other Workspace container receives the request

### Requirement: Preview is unavailable when Workspace is not running

The system SHALL return appropriate error when Preview URL is accessed for non-running Workspace.

#### Scenario: Preview for stopped Workspace
- **WHEN** user accesses Preview URL for Workspace with status "stopped" or "error"
- **THEN** system returns HTTP 503 Service Unavailable
- **AND** system returns message "Workspace is not running"

#### Scenario: Preview for non-existent Workspace
- **WHEN** user accesses Preview URL for Workspace ID that does not exist
- **THEN** system returns HTTP 404 Not Found

### Requirement: Preview Server runs in Workspace container

The system SHALL run the Preview Server process inside the Workspace container, not in control plane or separate service.

#### Scenario: Preview Server in container
- **WHEN** Workspace container is created
- **THEN** container includes Preview Server process (e.g., Vite Dev Server)
- **AND** Preview Server listens on designated port (e.g., 3000)
- **AND** container port is mapped to host for gateway access

#### Scenario: Preview Server lifecycle tied to Workspace
- **WHEN** Workspace container is stopped or deleted
- **THEN** Preview Server stops
- **AND** Preview URL becomes unavailable

### Requirement: Preview access events are audited

The system SHALL record audit logs for Preview access events.

#### Scenario: Preview access audit
- **WHEN** user successfully accesses Preview URL
- **THEN** system creates audit record with: timestamp, user_id, workspace_id, ip_address, event_type="PREVIEW_ACCESS"

#### Scenario: Preview access denied audit
- **WHEN** Preview access is denied (authentication failure or forbidden)
- **THEN** system creates audit record with: timestamp, requesting_ip, workspace_id (if valid), event_type="PREVIEW_ACCESS_DENIED", reason