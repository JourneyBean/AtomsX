# Workspace Management Capability

## Purpose

Enable users to create, manage, and delete isolated workspace containers for development.

## Requirements

### Requirement: Workspace creation timeout is configurable

The system SHALL provide configurable timeout settings for workspace container creation tasks.

#### Scenario: Default timeout configuration
- **WHEN** no custom timeout is configured
- **THEN** system uses default soft time limit of 300 seconds (5 minutes)
- **AND** system uses default hard time limit of 360 seconds (6 minutes)

#### Scenario: Custom timeout via environment variables
- **WHEN** environment variable `WORKSPACE_CREATION_SOFT_TIMEOUT` is set to custom value (e.g., 600)
- **THEN** system uses the custom soft time limit value
- **AND** workspace creation task respects the custom timeout

#### Scenario: Custom timeout via Django settings
- **WHEN** Django setting `WORKSPACE_CREATION_TIME_LIMITS` is configured with custom values
- **THEN** system uses the configured soft and hard time limits
- **AND** environment variable takes precedence if both are set

### Requirement: User can create a new Workspace

The system SHALL allow logged-in users to create a new isolated Workspace container with optimized image retrieval and configurable timeout constraints.

#### Scenario: Successful Workspace creation
- **WHEN** logged-in user submits Workspace creation request with name
- **THEN** system validates the name is non-empty and within length limit (max 100 characters)
- **AND** system creates Workspace record in database with: id (UUID), owner (user), name, status="creating", created_at
- **AND** system triggers asynchronous container creation task with configurable soft time limit
- **AND** system returns HTTP 201 Created with Workspace metadata

#### Scenario: Workspace container creation with prebuilt image
- **WHEN** container creation task starts and prebuilt image exists in Docker registry
- **THEN** system uses the prebuilt image directly without pulling
- **AND** system creates Docker container with isolated network and volume
- **AND** system stores container_id in Workspace record
- **AND** system updates Workspace status to "running"
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_CREATED", image_source="prebuilt"

#### Scenario: Workspace container creation without prebuilt image
- **WHEN** container creation task starts and prebuilt image does not exist
- **THEN** system attempts to pull fallback image (node:20-slim)
- **AND** system creates Docker container with fallback image
- **AND** system stores container_id in Workspace record
- **AND** system updates Workspace status to "running"
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_CREATED", image_source="fallback_pull"

#### Scenario: Workspace creation exceeds configurable soft time limit
- **WHEN** container creation task exceeds configured soft time limit
- **THEN** task receives SoftTimeLimitExceeded exception
- **AND** system updates Workspace status to "error"
- **AND** system records error message "Workspace creation timeout exceeded (soft limit: {configured_value}s)"
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_ERROR", error_message="timeout"

#### Scenario: Workspace creation exceeds configurable hard time limit
- **WHEN** container creation task exceeds configured hard time limit
- **THEN** task is forcibly terminated by Celery
- **AND** system detects orphaned Workspace in "creating" status on subsequent checks
- **AND** system updates Workspace status to "error" with message "Task terminated due to timeout (hard limit: {configured_value}s)"

#### Scenario: Workspace container creation fails
- **WHEN** container creation task fails (e.g., Docker unavailable, resource limit)
- **THEN** system updates Workspace status to "error"
- **AND** system records error message in Workspace record
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_ERROR", error_message

#### Scenario: Duplicate Workspace name for same user
- **WHEN** user attempts to create Workspace with name that already exists for that user
- **THEN** system returns HTTP 409 Conflict with error message "Workspace name already exists"

### Requirement: User can list their Workspaces

The system SHALL allow logged-in users to retrieve a list of their own Workspaces.

#### Scenario: List Workspaces
- **WHEN** logged-in user requests Workspace list
- **THEN** system returns all Workspace records where owner = current user
- **AND** each Workspace includes: id, name, status, created_at
- **AND** Workspaces are sorted by created_at descending

#### Scenario: Empty Workspace list
- **WHEN** logged-in user has no Workspaces
- **THEN** system returns empty array

### Requirement: User can view Workspace details

The system SHALL allow logged-in users to view details of a specific Workspace they own.

#### Scenario: View own Workspace
- **WHEN** logged-in user requests details of Workspace they own
- **THEN** system returns Workspace record with: id, name, status, container_id, created_at, updated_at

#### Scenario: View other user's Workspace forbidden
- **WHEN** logged-in user requests details of Workspace owned by another user
- **THEN** system returns HTTP 403 Forbidden
- **AND** system does not reveal any Workspace details

### Requirement: User can delete a Workspace

The system SHALL allow logged-in users to delete a Workspace they own, including its container and associated data.

#### Scenario: Successful Workspace deletion
- **WHEN** logged-in user requests deletion of Workspace they own
- **THEN** system updates Workspace status to "deleting"
- **AND** system triggers asynchronous container deletion task
- **AND** system returns HTTP 202 Accepted

#### Scenario: Workspace container deletion completes
- **WHEN** container deletion task completes
- **THEN** system stops and removes Docker container
- **AND** system removes container volume (files deleted)
- **AND** system marks Workspace record as deleted (soft delete or hard delete based on policy)
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_DELETED"

#### Scenario: Delete Workspace with active Session
- **WHEN** user attempts to delete Workspace that has an active Session
- **THEN** system terminates the active Session first
- **AND** then proceeds with Workspace deletion

#### Scenario: Delete other user's Workspace forbidden
- **WHEN** logged-in user requests deletion of Workspace owned by another user
- **THEN** system returns HTTP 403 Forbidden

### Requirement: Workspace containers are isolated

The system SHALL ensure each Workspace container runs in an isolated environment with no access to other containers or host system.

#### Scenario: Container network isolation
- **WHEN** Workspace container is created
- **THEN** container is assigned to its own Docker network or isolated network namespace
- **AND** container cannot directly reach other Workspace containers
- **AND** container cannot directly reach host Docker socket

#### Scenario: Container filesystem isolation
- **WHEN** Workspace container is created
- **THEN** container has its own volume for source files
- **AND** container cannot access other Workspace volumes
- **AND** container filesystem is independent of host filesystem (except mounted workspace volume)

### Requirement: Workspace lifecycle events are audited

The system SHALL record audit logs for all Workspace lifecycle events.

#### Scenario: Creation audit
- **WHEN** Workspace is created (container running)
- **THEN** system creates audit record with: timestamp, user_id, workspace_id, container_id, event_type="WORKSPACE_CREATED"

#### Scenario: Deletion audit
- **WHEN** Workspace is deleted
- **THEN** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_DELETED"

#### Scenario: Status change audit
- **WHEN** Workspace status changes (e.g., running -> error, creating -> running)
- **THEN** system creates audit record with: timestamp, user_id, workspace_id, previous_status, new_status, event_type="WORKSPACE_STATUS_CHANGE"

### Requirement: Workspace status includes recreating state

The system SHALL support a `recreating` status for Workspace, indicating the workspace container is being rebuilt with the latest image.

#### Scenario: Valid recreating status transitions
- **WHEN** workspace status is `running`, `stopped`, or `error`
- **THEN** system allows transition to `recreating` status
- **AND** system does not allow transition from `creating` or `deleting` to `recreating`

#### Scenario: Recreating status to running
- **WHEN** recreate task completes successfully
- **THEN** system transitions workspace status from `recreating` to `running`

#### Scenario: Recreating status to error
- **WHEN** recreate task fails (timeout, Docker error, image not found)
- **THEN** system transitions workspace status from `recreating` to `error`
- **AND** system records error message in workspace record

### Requirement: User can recreate a Workspace

The system SHALL allow logged-in users to recreate a Workspace they own, replacing its container with a new one using the latest prebuilt image while preserving the data directory.

#### Scenario: Successful Workspace recreate from running state
- **WHEN** logged-in user requests recreate on a workspace with status `running`
- **THEN** system validates workspace ownership
- **AND** system updates workspace status to `recreating`
- **AND** system triggers asynchronous recreate task
- **AND** system returns HTTP 202 Accepted with workspace metadata

#### Scenario: Successful Workspace recreate from stopped state
- **WHEN** logged-in user requests recreate on a workspace with status `stopped`
- **THEN** system validates workspace ownership
- **AND** system updates workspace status to `recreating`
- **AND** system triggers asynchronous recreate task (creates new container since old one does not exist)
- **AND** system returns HTTP 202 Accepted with workspace metadata

#### Scenario: Successful Workspace recreate from error state
- **WHEN** logged-in user requests recreate on a workspace with status `error`
- **THEN** system validates workspace ownership
- **AND** system updates workspace status to `recreating`
- **AND** system triggers asynchronous recreate task
- **AND** system returns HTTP 202 Accepted with workspace metadata

#### Scenario: Recreate task execution
- **WHEN** recreate task starts
- **THEN** system stops old container (if exists) with timeout of 10 seconds
- **AND** system removes old container (if exists)
- **AND** system deletes old WorkspaceToken
- **AND** system creates new WorkspaceToken
- **AND** system creates new container with same `data_dir_path` bind mounts
- **AND** system starts new container
- **AND** system updates workspace `container_id` to new container ID
- **AND** system updates workspace status to `running`
- **AND** system creates audit record with: timestamp, user_id, workspace_id, container_id, event_type="WORKSPACE_RECREATED"

#### Scenario: Recreate preserves data directory
- **WHEN** recreate task creates new container
- **THEN** system uses the same `data_dir_path` from workspace record
- **AND** system mounts `/home/user/workspace` to same host path
- **AND** system mounts `/home/user/history` to same host path
- **AND** workspace files and history data are preserved

#### Scenario: Recreate other user's Workspace forbidden
- **WHEN** logged-in user requests recreate on workspace owned by another user
- **THEN** system returns HTTP 403 Forbidden
- **AND** system does not change workspace status

#### Scenario: Recreate on deleting workspace forbidden
- **WHEN** logged-in user requests recreate on workspace with status `deleting`
- **THEN** system returns HTTP 400 Bad Request with error message "Cannot recreate workspace in deleting state"

#### Scenario: Recreate on recreating workspace conflict
- **WHEN** logged-in user requests recreate on workspace with status `recreating`
- **THEN** system returns HTTP 409 Conflict with error message "Workspace recreate already in progress"

#### Scenario: Recreate with prebuilt image not found
- **WHEN** recreate task starts and prebuilt image does not exist in Docker registry
- **THEN** system updates workspace status to `error`
- **AND** system records error message "Workspace image not found"
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_ERROR", error_message="image_not_found"

#### Scenario: Recreate exceeds soft time limit
- **WHEN** recreate task exceeds configurable soft time limit
- **THEN** task receives SoftTimeLimitExceeded exception
- **AND** system updates workspace status to `error`
- **AND** system records error message "Workspace recreate timeout exceeded"
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_ERROR", error_message="timeout"

#### Scenario: Recreate with Docker error
- **WHEN** recreate task encounters Docker operation error (container creation fails)
- **THEN** system updates workspace status to `error`
- **AND** system records error message from Docker exception
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_ERROR", error_message

### Requirement: Workspace recreate events are audited

The system SHALL record audit logs for Workspace recreate events.

#### Scenario: Recreate success audit
- **WHEN** Workspace recreate completes successfully
- **THEN** system creates audit record with: timestamp, user_id, workspace_id, container_id (new), event_type="WORKSPACE_RECREATED"
- **AND** audit record includes previous_container_id if available

#### Scenario: Recreate error audit
- **WHEN** Workspace recreate fails
- **THEN** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_ERROR", error_message