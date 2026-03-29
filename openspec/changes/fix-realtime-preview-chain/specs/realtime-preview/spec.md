## MODIFIED Requirements

### Requirement: Preview URL resolves to correct Workspace

The system SHALL route Preview URL requests to the correct Workspace container using Docker DNS resolution.

#### Scenario: Preview URL resolves via Docker DNS
- **WHEN** user accesses `<workspace-id>.preview.<domain>`
- **THEN** gateway resolves container hostname `workspace-{workspace-id}` via Docker DNS
- **AND** gateway proxies request to `workspace-{workspace-id}:3000`
- **AND** no other Workspace container receives the request

#### Scenario: Gateway on shared network
- **WHEN** Gateway container starts
- **THEN** Gateway is connected to `atomsx-network` for backend/frontend access
- **AND** Gateway is connected to `atomsx-workspaces` for workspace container access
- **AND** Gateway can resolve workspace container names via Docker DNS

### Requirement: Preview Server runs in Workspace container

The system SHALL run the Preview Server process inside the Workspace container, managed by supervisord.

#### Scenario: Preview Server in container with supervisord
- **WHEN** Workspace container is created
- **THEN** supervisord starts as PID 1
- **AND** supervisord starts preview-server process
- **AND** Preview Server listens on port 3000
- **AND** port 3000 is accessible via container network (no port mapping needed)

#### Scenario: Preview Server lifecycle tied to Workspace
- **WHEN** Workspace container is stopped or deleted
- **THEN** supervisord receives SIGTERM
- **AND** preview-server process stops gracefully
- **AND** Preview URL becomes unavailable

## ADDED Requirements

### Requirement: container_host uses Docker DNS compatible format

The system SHALL store container_host in a format that allows Docker DNS resolution from Gateway.

#### Scenario: container_host stored as container name
- **WHEN** workspace container is created
- **THEN** workspace.container_host is set to `workspace-{uuid}:3000`
- **AND** Gateway can use this value directly in proxy_pass directive
- **AND** Docker DNS resolves `workspace-{uuid}` to container IP

#### Scenario: Auth verify returns correct container_host
- **WHEN** Gateway calls /api/auth/verify with X-Workspace-Id header
- **THEN** backend returns `container_host: "workspace-{uuid}:3000"`
- **AND** Gateway sets $container_host variable to this value
- **AND** proxy_pass uses this variable to route request