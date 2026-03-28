## ADDED Requirements

### Requirement: System uses Docker-in-Docker for container management

The system SHALL use Docker-in-Docker (dind) for all Docker-dependent operations, including Workspace container creation, deletion, and management.

#### Scenario: dind service is configured and running
- **WHEN** system initializes
- **THEN** dind Docker daemon service SHALL be running and healthy
- **AND** system SHALL NOT mount or use host Docker socket

#### Scenario: Docker client connects to dind daemon
- **WHEN** backend or celery-worker initializes Docker client
- **THEN** client SHALL connect to dind Docker daemon via configured socket path
- **AND** client SHALL NOT connect to host Docker socket

### Requirement: dind configuration is configurable via environment variables

The system SHALL allow configuration of dind connection via environment variables.

#### Scenario: Configure dind socket path
- **WHEN** `DIND_SOCKET_PATH` environment variable is set
- **THEN** system SHALL use the specified socket path for Docker client connection
- **AND** default value SHALL be `/var/run/dind/docker.sock`

#### Scenario: Configure DOCKER_HOST
- **WHEN** `DOCKER_HOST` environment variable is set
- **THEN** system SHALL use the specified Docker host for Docker client connection
- **AND** `DOCKER_HOST` SHALL point to dind daemon, not host Docker daemon

#### Scenario: Enable or disable dind mode
- **WHEN** `DIND_ENABLED` environment variable is set to `false`
- **THEN** system SHALL NOT use dind mode
- **AND** system SHALL reject container operations (configuration error)
- **WHEN** `DIND_ENABLED` environment variable is set to `true` (default)
- **THEN** system SHALL use dind mode for all container operations

### Requirement: dind service health is verified before container operations

The system SHALL verify dind daemon health before accepting container operations.

#### Scenario: dind health check passes
- **WHEN** backend or celery-worker starts
- **THEN** system SHALL wait for dind service to pass health check
- **AND** system SHALL only proceed with container operations after health check passes

#### Scenario: dind health check fails
- **WHEN** dind health check fails
- **THEN** system SHALL log error and retry health check
- **AND** system SHALL NOT accept Workspace creation requests until dind is healthy

### Requirement: dind data is persisted

The system SHALL persist dind Docker data (images, containers, volumes) in a dedicated volume.

#### Scenario: dind data persistence
- **WHEN** dind container restarts
- **THEN** previously created images, containers, and volumes SHALL still exist
- **AND** Workspace containers SHALL continue running after dind restart

#### Scenario: dind data volume configuration
- **WHEN** system initializes dind service
- **THEN** dind SHALL mount a dedicated data volume at `/var/lib/docker`
- **AND** volume name SHALL be `dind_data`

### Requirement: dind is isolated from host Docker

The system SHALL ensure complete isolation between dind Docker daemon and host Docker daemon.

#### Scenario: Workspace containers in dind only
- **WHEN** Workspace container is created
- **THEN** container SHALL be created in dind Docker daemon
- **AND** container SHALL NOT appear in host Docker daemon's container list

#### Scenario: Host Docker socket not accessible
- **WHEN** backend or celery-worker runs
- **THEN** host Docker socket (`/var/run/docker.sock`) SHALL NOT be mounted
- **AND** system SHALL have no access to host Docker daemon

### Requirement: dind TLS configuration

The system SHALL allow optional TLS configuration for dind connection in production environments.

#### Scenario: TLS disabled (MVP default)
- **WHEN** `DOCKER_TLS_CERTDIR` is empty or not set
- **THEN** dind SHALL run without TLS
- **AND** Docker client SHALL connect via plain Unix socket

#### Scenario: TLS enabled (production)
- **WHEN** `DOCKER_TLS_CERTDIR` is set to a valid path
- **THEN** dind SHALL generate TLS certificates
- **AND** Docker client SHALL connect via TLS-secured connection