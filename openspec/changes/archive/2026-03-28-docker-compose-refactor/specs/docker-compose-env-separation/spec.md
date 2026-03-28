## ADDED Requirements

### Requirement: Separate docker-compose files for dev and prod

The system SHALL provide separate Docker Compose configuration files for development and production environments, using Docker Compose multi-file override mechanism.

#### Scenario: Development environment startup
- **WHEN** developer starts the platform in development mode
- **THEN** the system SHALL use `docker compose -f docker-compose.yml -f docker-compose.dev.yml up`

#### Scenario: Production environment startup
- **WHEN** operator deploys the platform in production mode
- **THEN** the system SHALL use `docker compose -f docker-compose.yml -f docker-compose.prod.yml up`

#### Scenario: Base configuration inheritance
- **WHEN** either dev or prod compose files are loaded
- **THEN** both SHALL inherit base configuration from `docker-compose.yml`
- **AND** base file SHALL define shared services, networks, and volumes

### Requirement: Development compose file characteristics

The system SHALL provide `docker-compose.dev.yml` with development-specific configurations that facilitate debugging and hot reload.

#### Scenario: Development port exposure
- **WHEN** development compose is active
- **THEN** Gateway ports 80/443 SHALL be exposed to host
- **AND** Backend port 8000 MAY be exposed for direct API debugging
- **AND** Frontend port 5173 MAY be exposed for direct frontend debugging

#### Scenario: Development volume mounts
- **WHEN** development compose is active
- **THEN** backend source code SHALL be mounted as volume for hot reload
- **AND** frontend source code SHALL be mounted as volume for hot reload

#### Scenario: Development command override
- **WHEN** development compose is active
- **THEN** backend SHALL use `runserver` with auto-reload
- **AND** frontend SHALL use Vite dev server with HMR
- **AND** celery SHALL run with `--loglevel=debug`

#### Scenario: Development environment variables
- **WHEN** development compose is active
- **THEN** DJANGO_DEBUG SHALL be set to `True`
- **AND** logging level SHALL be `DEBUG` or `INFO`

### Requirement: Production compose file characteristics

The system SHALL provide `docker-compose.prod.yml` with production-specific configurations that minimize security exposure and optimize resource usage.

#### Scenario: Production port exposure
- **WHEN** production compose is active
- **THEN** only Gateway ports 80/443 SHALL be exposed to host
- **AND** no database, Redis, or internal service ports SHALL be exposed

#### Scenario: Production Dockerfile usage
- **WHEN** production compose is active
- **THEN** backend SHALL build using `Dockerfile.prod`
- **AND** frontend SHALL build using `Dockerfile.prod`
- **AND** Dockerfile.prod SHALL use multi-stage build for minimal image size

#### Scenario: Production resource limits
- **WHEN** production compose is active
- **THEN** each service MAY have CPU and memory limits defined
- **AND** restart policy SHALL be `always` or `on-failure`

#### Scenario: Production environment variables
- **WHEN** production compose is active
- **THEN** DJANGO_DEBUG SHALL be set to `False`
- **AND** DJANGO_SECRET_KEY SHALL be provided via environment or secrets
- **AND** logging level SHALL be `WARNING` or `ERROR`

#### Scenario: Production volume strategy
- **WHEN** production compose is active
- **THEN** source code volumes SHALL NOT be mounted (use built-in image code)
- **AND** only data volumes (postgres_data, redis_data) SHALL be persisted

### Requirement: Separate Dockerfiles for production

The system SHALL provide production-specific Dockerfiles (`Dockerfile.prod`) for backend and frontend services that optimize for minimal image size and production readiness.

#### Scenario: Backend production Dockerfile
- **WHEN** `backend/Dockerfile.prod` is used
- **THEN** it SHALL use multi-stage build
- **AND** final stage SHALL NOT contain development dependencies (pytest, etc.)
- **AND** SHALL use production WSGI server (not runserver)

#### Scenario: Frontend production Dockerfile
- **WHEN** `frontend/Dockerfile.prod` is used
- **THEN** it SHALL build static assets with `npm run build`
- **AND** SHALL use nginx or similar to serve static files
- **AND** SHALL NOT contain Vite dev server

#### Scenario: Production image size optimization
- **WHEN** production Dockerfiles are built
- **THEN** backend image SHALL be smaller than development image
- **AND** frontend image SHALL contain only static assets and nginx

### Requirement: Startup convenience commands

The system SHALL provide convenient commands (Makefile or npm scripts) to simplify starting development and production environments without memorizing compose file combinations.

#### Scenario: Makefile dev command
- **WHEN** developer runs `make dev`
- **THEN** system SHALL execute `docker compose -f docker-compose.yml -f docker-compose.dev.yml up`

#### Scenario: Makefile prod command
- **WHEN** operator runs `make prod`
- **THEN** system SHALL execute `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`

#### Scenario: Makefile stop command
- **WHEN** user runs `make down`
- **THEN** system SHALL stop all services and clean up

### Requirement: Documentation for environment switching

The system SHALL document the new startup commands and environment differences in README.md or developer guide.

#### Scenario: README development instructions
- **WHEN** developer reads README.md
- **THEN** they SHALL find clear instructions for starting development environment
- **AND** SHALL understand which ports are available for debugging

#### Scenario: README production instructions
- **WHEN** operator reads README.md
- **THEN** they SHALL find clear instructions for production deployment
- **AND** SHALL understand security differences (minimal port exposure)