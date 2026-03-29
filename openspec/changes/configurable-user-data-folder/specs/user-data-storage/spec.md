# User Data Storage Capability

## Purpose

Define how user data is stored, organized, and accessed on the host system for persistent storage across Workspace container lifecycles.

## ADDED Requirements

### Requirement: Data storage root path is configurable

The system SHALL provide a configurable root path for storing user data, with environment-specific defaults.

#### Scenario: Development environment default path
- **WHEN** system is running in DEBUG mode (development environment)
- **THEN** data storage root path defaults to `./dev-cache/data`

#### Scenario: Default path configuration
- **WHEN** system starts
- **THEN** data storage root path defaults to `/var/opt/atomsx/workspaces`

#### Scenario: Custom path via environment variable
- **WHEN** environment variable `ATOMSX_WORKSPACE_DATA_ROOT` is set
- **THEN** system uses the environment variable value as data storage root path

### Requirement: User data directory follows UUID sharding structure

The system SHALL organize user data directories using a two-level UUID sharding structure.

#### Scenario: Directory structure for new Workspace
- **WHEN** a new Workspace is created with UUID `abc12345-def6-7890-...`
- **THEN** data directory path is `{root}/a/b/abc12345-def6-7890-.../`
- **AND** first-level directory uses first character of UUID (a)
- **AND** second-level directory uses second character of UUID (b)
- **AND** full UUID is used as the final directory name

#### Scenario: Sharding prevents directory overflow
- **WHEN** thousands of Workspaces exist
- **THEN** first-level directories contain at most 16 subdirectories (UUID first char: 0-9, a-f)
- **AND** second-level directories contain at most 16 subdirectories per parent (UUID second char: 0-9, a-f)

### Requirement: User data directory contains workspace and history subdirectories

The system SHALL create standardized subdirectories within each user data directory.

#### Scenario: Subdirectory creation during Workspace initialization
- **WHEN** a new Workspace data directory is created
- **THEN** system creates `workspace/` subdirectory for storing user code repository
- **AND** system creates `history/` subdirectory for storing conversation history

#### Scenario: Subdirectory permissions
- **WHEN** subdirectories are created
- **THEN** subdirectories have permissions `0755`
- **AND** subdirectories are owned by the system user running the Celery task

### Requirement: User data directory is mounted as container home directory

The system SHALL mount the user data directory as the home directory inside the Workspace container.

#### Scenario: Mount configuration during container creation
- **WHEN** Workspace container is being created
- **THEN** system mounts `{root}/{uuid[0]}/{uuid[1]}/{uuid}/` as `/home/user` in the container
- **AND** `workspace/` subdirectory is accessible at `/home/user/workspace`
- **AND** `history/` subdirectory is accessible at `/home/user/history`

#### Scenario: Mount uses bind mount type
- **WHEN** Workspace container is being created
- **THEN** system uses Docker bind mount for user data directory
- **AND** bind mount ensures direct access to host filesystem path

### Requirement: Data directory creation failure is handled gracefully

The system SHALL handle data directory creation failures with clear error reporting.

#### Scenario: Directory creation fails due to permissions
- **WHEN** system attempts to create data directory but lacks write permission on root path
- **THEN** Workspace creation fails with status "error"
- **AND** error message includes "Failed to create data directory: permission denied"
- **AND** audit record is created with event_type="WORKSPACE_ERROR"

#### Scenario: Directory creation fails due to disk space
- **WHEN** system attempts to create data directory but disk is full
- **THEN** Workspace creation fails with status "error"
- **AND** error message includes "Failed to create data directory: disk full"
- **AND** audit record is created with event_type="WORKSPACE_ERROR"

### Requirement: Data directories persist after container deletion

The system SHALL preserve user data directories when Workspace containers are deleted.

#### Scenario: Data directory preserved after container deletion
- **WHEN** Workspace container is deleted
- **THEN** user data directory `{root}/{uuid[0]}/{uuid[1]}/{uuid}/` remains on host filesystem
- **AND** `workspace/` and `history/` subdirectories remain intact

#### Scenario: Data directory can be reused for new container
- **WHEN** a new Workspace container is created with same UUID as previously deleted Workspace
- **THEN** existing data directory is reused
- **AND** previous workspace content and history remain accessible