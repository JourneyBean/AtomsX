## ADDED Requirements

### Requirement: Service-to-service communication via Docker service name

The system SHALL use Docker service names for all inter-service communication within the platform control plane. No service SHALL reference localhost or 127.0.0.1 when connecting to another service in the same Docker Compose deployment.

#### Scenario: Backend connects to database
- **WHEN** backend service starts and connects to PostgreSQL
- **THEN** backend SHALL use `postgres` as the host name (not localhost or 127.0.0.1)

#### Scenario: Backend connects to Redis
- **WHEN** backend service connects to Redis for Celery or caching
- **THEN** backend SHALL use `redis` as the host name

#### Scenario: Frontend proxies API requests
- **WHEN** frontend development server proxies requests to `/api/*`
- **THEN** frontend SHALL proxy to `http://backend:8000` (not localhost:8000)

#### Scenario: Gateway routes to backend
- **WHEN** gateway receives request for `/api/*`
- **THEN** gateway SHALL route to `backend:8000` upstream (defined in nginx.conf)

#### Scenario: Gateway routes to frontend
- **WHEN** gateway receives request for non-API routes
- **THEN** gateway SHALL route to `frontend:5173` upstream

### Requirement: Port exposure restricted to Gateway only

The system SHALL expose only the Gateway service ports (80 and 443) to the host machine in production environment. Database, Redis, Backend API, and Authentik ports SHALL NOT be mapped to host ports in production.

#### Scenario: Production deployment port check
- **WHEN** production docker-compose is deployed
- **THEN** only port 80 and 443 SHALL be mapped to host
- **AND** PostgreSQL port 5432 SHALL NOT be mapped to host
- **AND** Redis port 6379 SHALL NOT be mapped to host
- **AND** Backend port 8000 SHALL NOT be mapped to host
- **AND** Authentik ports 9000/9443 SHALL NOT be mapped to host

#### Scenario: Development environment port flexibility
- **WHEN** development docker-compose is deployed
- **THEN** Gateway ports 80/443 SHALL be mapped to host
- **AND** optional debug ports MAY be mapped to host (backend:8000, frontend:5173)

### Requirement: No hardcoded localhost in configuration files

The system SHALL NOT contain hardcoded localhost or 127.0.0.1 references for service-to-service communication in any configuration file that runs inside containers.

#### Scenario: Vite proxy configuration
- **WHEN** vite.config.ts is loaded in frontend container
- **THEN** proxy target SHALL NOT be `http://localhost:8000`
- **AND** proxy target SHALL use Docker service name `backend`

#### Scenario: Django ALLOWED_HOSTS configuration
- **WHEN** Django settings are loaded
- **THEN** ALLOWED_HOSTS SHALL include Docker service name `backend`
- **AND** localhost MAY be included only for local development outside Docker

#### Scenario: OIDC redirect URI
- **WHEN** OIDC callback is configured
- **THEN** redirect URI SHALL use the Gateway-accessible path
- **AND** SHALL NOT use `localhost:8000` inside container context

#### Scenario: Gateway server_name configuration
- **WHEN** nginx.conf is loaded
- **THEN** server_name SHALL NOT be hardcoded to `localhost` only
- **AND** SHALL use `_` (catch-all) or actual domain name

### Requirement: Service startup dependency with health checks

The system SHALL ensure services wait for their dependencies to be healthy before starting. All services that depend on database or Redis SHALL use `depends_on` with `condition: service_healthy`.

#### Scenario: Backend waits for database
- **WHEN** backend service is starting
- **THEN** backend SHALL NOT start until postgres health check passes

#### Scenario: Backend waits for Redis
- **WHEN** backend service is starting
- **THEN** backend SHALL NOT start until redis health check passes

#### Scenario: Celery worker waits for dependencies
- **WHEN** celery-worker is starting
- **THEN** celery-worker SHALL NOT start until postgres AND redis are healthy

#### Scenario: Gateway waits for backend
- **WHEN** gateway service is starting
- **THEN** gateway SHALL NOT start until backend is ready (port 8000 accepting connections)

#### Scenario: Authentik waits for database and Redis
- **WHEN** authentik-server is starting
- **THEN** authentik-server SHALL NOT start until postgres AND redis are healthy

### Requirement: Health check definitions for infrastructure services

The system SHALL define health checks for PostgreSQL, Redis, and Backend services to enable proper dependency orchestration.

#### Scenario: PostgreSQL health check
- **WHEN** postgres service is running
- **THEN** health check SHALL use `pg_isready` command
- **AND** interval SHALL be 5 seconds or less
- **AND** retries SHALL be at least 5

#### Scenario: Redis health check
- **WHEN** redis service is running
- **THEN** health check SHALL use `redis-cli ping` command
- **AND** SHALL return `PONG` for healthy status

#### Scenario: Backend health check (optional for production)
- **WHEN** backend service is running in production
- **THEN** health check MAY use HTTP endpoint `/api/health` or admin endpoint
- **AND** SHALL return HTTP 200 for healthy status