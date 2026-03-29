# Workspace Management Capability - Delta Spec

## Purpose

This delta spec captures modifications to the workspace-management capability due to the introduction of configurable user data storage.

## MODIFIED Requirements

### Requirement: User can create a new Workspace

The system SHALL allow logged-in users to create a new isolated Workspace container with persistent user data storage.

#### Scenario: Successful Workspace creation
- **WHEN** logged-in user submits Workspace creation request with name
- **THEN** system validates the name is non-empty and within length limit (max 100 characters)
- **AND** system creates Workspace record in database with: id (UUID), owner (user), name, status="creating", created_at
- **AND** system computes user data directory path: `{WORKSPACE_DATA_ROOT}/{uuid[0]}/{uuid[1]}/{uuid}/`
- **AND** system triggers asynchronous container creation task with data directory path

#### Scenario: Workspace container creation completes
- **WHEN** container creation task completes successfully
- **THEN** system creates user data directory with subdirectories `workspace/` and `history/`
- **AND** system creates Docker container with bind mount: `{data_dir}` → `/home/user`
- **AND** system stores container_id in Workspace record
- **AND** system updates Workspace status to "running"
- **AND** system creates audit record with: timestamp, user_id, workspace_id, container_id, data_dir_path, event_type="WORKSPACE_CREATED"

#### Scenario: Workspace container creation fails
- **WHEN** container creation task fails (e.g., Docker unavailable, resource limit, data directory creation failure)
- **THEN** system updates Workspace status to "error"
- **AND** system records error message in Workspace record
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_ERROR", error_message

### Requirement: User can view Workspace details

The system SHALL allow logged-in users to view details of a specific Workspace they own, including storage information.

#### Scenario: View own Workspace
- **WHEN** logged-in user requests details of Workspace they own
- **THEN** system returns Workspace record with: id, name, status, container_id, created_at, updated_at, data_dir_path

### Requirement: Workspace containers are isolated

The system SHALL ensure each Workspace container runs in an isolated environment with persistent user data storage.

#### Scenario: Container filesystem isolation with persistent data
- **WHEN** Workspace container is created
- **THEN** container has bind mount for user data directory at `/home/user`
- **AND** container cannot access other Workspace data directories
- **AND** user data persists on host filesystem independent of container lifecycle