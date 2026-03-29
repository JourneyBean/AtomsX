# Workspace Management Capability - Delta Spec

## Purpose

This delta spec modifies the existing workspace-management capability to support Workspace Client architecture.

## MODIFIED Requirements

### Requirement: User can create a new Workspace

The system SHALL allow logged-in users to create a new isolated Workspace container.

#### Scenario: Successful Workspace creation
- **WHEN** logged-in user submits Workspace creation request with name
- **THEN** system validates the name is non-empty and within length limit (max 100 characters)
- **AND** system creates Workspace record in database with: id (UUID), owner (user), name, status="creating", created_at
- **AND** system generates WorkspaceToken with unique token
- **AND** system triggers asynchronous container creation task
- **AND** system returns HTTP 201 Created with Workspace metadata

#### Scenario: Workspace container creation completes
- **WHEN** container creation task completes successfully
- **THEN** system creates Docker container with:
  - isolated network and volume
  - ATOMSX_AUTH_TOKEN environment variable (from WorkspaceToken)
  - ATOMSX_BACKEND_WS_URL environment variable
  - WORKSPACE_ID environment variable
- **AND** system stores container_id in Workspace record
- **AND** system updates Workspace status to "running"
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_CREATED"

#### Scenario: Workspace container creation fails
- **WHEN** container creation task fails (e.g., Docker unavailable, resource limit)
- **THEN** system updates Workspace status to "error"
- **AND** system records error message in Workspace record
- **AND** system deletes WorkspaceToken
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_ERROR", error_message

#### Scenario: Duplicate Workspace name for same user
- **WHEN** user attempts to create Workspace with name that already exists for that user
- **THEN** system returns HTTP 409 Conflict with error message "Workspace name already exists"

### Requirement: User can delete a Workspace

The system SHALL allow logged-in users to delete a Workspace they own, including its container, token, and associated data.

#### Scenario: Successful Workspace deletion
- **WHEN** logged-in user requests deletion of Workspace they own
- **THEN** system updates Workspace status to "deleting"
- **AND** system triggers asynchronous container deletion task
- **AND** system returns HTTP 202 Accepted

#### Scenario: Workspace container deletion completes
- **WHEN** container deletion task completes
- **THEN** system stops and removes Docker container
- **AND** system removes container volume (files deleted)
- **AND** system deletes WorkspaceToken associated with Workspace
- **AND** system marks Workspace record as deleted (soft delete or hard delete based on policy)
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_DELETED"

#### Scenario: Delete Workspace with active Session
- **WHEN** user attempts to delete Workspace that has an active Session
- **THEN** system terminates the active Session first
- **AND** then proceeds with Workspace deletion

#### Scenario: Delete other user's Workspace forbidden
- **WHEN** logged-in user requests deletion of Workspace owned by another user
- **THEN** system returns HTTP 403 Forbidden

## ADDED Requirements

### Requirement: Workspace container includes Workspace Client

The system SHALL ensure each Workspace container includes the Workspace Client program.

#### Scenario: Workspace Client installed in container
- **WHEN** Workspace container is created
- **THEN** container has `/home/user/workspace-client/` directory with:
  - pyproject.toml
  - .venv/ (virtual environment)
  - src/workspace_client/ (Python source code)
- **AND** Workspace Client is configured to run as container entrypoint

#### Scenario: Workspace Client runs as non-root
- **WHEN** Workspace container starts
- **THEN** Workspace Client process runs with uid=1000, gid=1000
- **AND** all files in /home/user/ are owned by uid=1000

### Requirement: Workspace container environment variables

The system SHALL inject required environment variables into Workspace containers.

#### Scenario: Required environment variables
- **WHEN** Workspace container is created
- **THEN** container has environment variables:
  - WORKSPACE_ID (UUID string)
  - ATOMSX_AUTH_TOKEN (from WorkspaceToken)
  - ATOMSX_BACKEND_WS_URL (from settings)
  - ATOMSX_BACKEND_HTTP_URL (from settings)

### Requirement: Workspace Token lifecycle

The system SHALL manage WorkspaceToken lifecycle in sync with Workspace container.

#### Scenario: Token created with Workspace
- **WHEN** Workspace creation task starts
- **THEN** system creates WorkspaceToken record before container creation

#### Scenario: Token deleted with Workspace
- **WHEN** Workspace deletion task completes
- **THEN** system deletes WorkspaceToken record

#### Scenario: Token deleted on container stop
- **WHEN** Celery task detects container has stopped unexpectedly
- **THEN** system deletes WorkspaceToken record
- **AND** system logs token cleanup

### Requirement: Workspace Client ready check

The system SHALL verify Workspace Client is ready before accepting sessions.

#### Scenario: Health check passes
- **WHEN** Workspace container is running
- **THEN** container health check verifies Workspace Client process is running
- **AND** health check verifies WebSocket connection can be established

#### Scenario: Workspace not ready for sessions
- **WHEN** Workspace status is "running" but Workspace Client is not connected
- **THEN** attempts to create Session return HTTP 503 Service Unavailable