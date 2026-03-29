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