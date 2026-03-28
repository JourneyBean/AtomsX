## MODIFIED Requirements

### Requirement: Workspace containers are isolated

The system SHALL ensure each Workspace container runs in an isolated environment with no access to other containers or host system.

#### Scenario: Container network isolation
- **WHEN** Workspace container is created
- **THEN** container is assigned to its own Docker network or isolated network namespace **within the dind Docker daemon**
- **AND** container cannot directly reach other Workspace containers
- **AND** container cannot directly reach **dind Docker socket**
- **AND** container **has no access to host Docker socket or host system**

#### Scenario: Container filesystem isolation
- **WHEN** Workspace container is created
- **THEN** container has its own volume for source files **managed by dind Docker daemon**
- **AND** container cannot access other Workspace volumes
- **AND** container filesystem is independent of **dind daemon filesystem and host filesystem** (except mounted workspace volume)

### Requirement: Workspace container creation completes

#### Scenario: Workspace container creation completes
- **WHEN** container creation task completes successfully
- **THEN** system creates Docker container with isolated network and volume **in the dind Docker daemon**
- **AND** system stores container_id in Workspace record
- **AND** system updates Workspace status to "running"
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_CREATED"

#### Scenario: Workspace container creation fails
- **WHEN** container creation task fails (e.g., **dind Docker daemon unavailable**, resource limit)
- **THEN** system updates Workspace status to "error"
- **AND** system records error message in Workspace record
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_ERROR", error_message

### Requirement: Workspace container deletion completes

#### Scenario: Workspace container deletion completes
- **WHEN** container deletion task completes
- **THEN** system stops and removes Docker container **from the dind Docker daemon**
- **AND** system removes container volume **from dind Docker daemon** (files deleted)
- **AND** system marks Workspace record as deleted (soft delete or hard delete based on policy)
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_DELETED"

## ADDED Requirements

### Requirement: Docker operations use dind exclusively

The system SHALL perform all Docker operations exclusively through the dind Docker daemon.

#### Scenario: Container creation in dind
- **WHEN** Workspace container creation task runs
- **THEN** task SHALL connect to dind Docker daemon via configured socket
- **AND** container SHALL be created in dind environment only
- **AND** task SHALL NOT attempt to use host Docker socket

#### Scenario: Container deletion in dind
- **WHEN** Workspace container deletion task runs
- **THEN** task SHALL connect to dind Docker daemon via configured socket
- **AND** container SHALL be deleted from dind environment only

#### Scenario: Network and volume creation in dind
- **WHEN** system creates Docker network or volume for Workspace
- **THEN** network/volume SHALL be created in dind Docker daemon only
- **AND** network/volume SHALL NOT exist in host Docker daemon

### Requirement: Workspace preview port accessibility

The system SHALL ensure Workspace preview ports are accessible from the gateway despite running in dind.

#### Scenario: Preview port mapping
- **WHEN** Workspace container is created with preview port
- **THEN** container's preview port SHALL be mapped to a host-accessible port
- **AND** gateway SHALL be able to proxy to the preview port

#### Scenario: Port mapping chain
- **WHEN** dind container runs with port publishing
- **THEN** dind SHALL publish Workspace container ports to dind container's ports
- **AND** docker-compose SHALL map dind container ports to host ports
- **AND** gateway SHALL access preview via host port mapping chain