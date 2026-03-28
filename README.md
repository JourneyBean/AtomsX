# AtomsX - Visual Coding Platform

A visual coding platform where users interact with an AI Agent to build applications, with real-time preview capabilities.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         External Traffic                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      OpenResty Gateway                           │
│  - Preview: *.preview.local → auth verify → workspace container │
│  - API: /api/* → Django                                         │
│  - Frontend: /* → Vue App                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌───────────────────────┐       ┌───────────────────────┐
│   Django Control Plane│       │      Vue Frontend     │
│   - OIDC Auth         │       │   - Login Page        │
│   - Workspace API     │       │   - Workspace List    │
│   - Session API       │       │   - Chat Panel (SSE)  │
│   - SSE Endpoint      │       │   - Preview Frame     │
└───────────────────────┘       └───────────────────────┘
              │
              ▼
┌───────────────────────┐
│    PostgreSQL         │
│    - User             │
│    - Workspace        │
│    - Session          │
└───────────────────────┘
              │
              ▼
┌───────────────────────┐
│       Redis           │
│    - Session Cache    │
│    - Celery Queue     │
└───────────────────────┘
              │
              ▼
┌───────────────────────┐
│   Celery Worker       │
│   - Claude Agent SDK  │
│   - File Operations   │
└───────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Docker-in-Docker (dind) Service                     │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Workspace Container Pool                      │  │
│  │  Each workspace runs in an isolated Docker container:     │  │
│  │  - Agent Runtime                                          │  │
│  │  - Preview Server (Vite)                                  │  │
│  │  - Source Files                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Security: dind isolates Workspace containers from host Docker  │
└─────────────────────────────────────────────────────────────────┘
```

### Docker-in-Docker (dind) Architecture

The platform uses Docker-in-Docker for secure container management:

- **Isolation**: All Workspace containers run inside a dedicated dind Docker daemon, completely isolated from the host's Docker environment
- **Security**: Even if the control plane (Django/Celery) is compromised, attackers cannot access the host Docker daemon or other host containers
- **Compliance**: Follows the architecture principle that Workspace should not hold host-level privileges

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for local frontend development)
- Python 3.12+ (for local backend development)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/atomsx.git
   cd atomsx
   ```

2. Create environment file:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. Start development services:
   ```bash
   make dev
   # Or manually: docker compose -f docker-compose.yml -f docker-compose.dev.yml up
   ```

4. Run database migrations:
   ```bash
   make migrate
   # Or: docker compose exec backend uv run python manage.py migrate
   ```

5. Create a superuser (for admin access):
   ```bash
   make superuser
   ```

6. Access the application:
   - **Via Gateway (recommended)**: http://localhost (port 80)
   - **Direct Frontend (dev only)**: http://localhost:5173
   - **Direct Backend (dev only)**: http://localhost:8000/api/
   - **Admin (dev only)**: http://localhost:8000/admin/

Note: The workspace-base image will be pulled automatically (node:20-slim) if not pre-built. For custom workspace images, build inside dind or use a registry.

### Environment Modes

The platform supports two Docker Compose configurations:

| Mode | Command | Ports Exposed | Use Case |
|------|---------|---------------|----------|
| **Development** | `make dev` | 80, 443, 8000, 5173, 5432, 6379 | Local development with debug access |
| **Production** | `make prod` | 80, 443 only | Production deployment (minimal exposure) |

**Development mode** exposes additional ports for debugging:
- Backend API (8000) - direct API testing
- Frontend Vite (5173) - HMR and direct frontend access
- PostgreSQL (5432) - database tools
- Redis (6379) - Redis CLI access

**Production mode** only exposes Gateway ports (80/443):
- All internal services accessed via Gateway
- Database and Redis not accessible from host
- Follows security principle of minimal port exposure

### Docker Socket Configuration

The platform uses different Docker access strategies for dev and prod:

| Mode | Docker Access | Why |
|------|---------------|-----|
| **Development** | Host Docker socket (`/var/run/docker.sock`) | Simpler, faster, no isolation needed |
| **Production** | Docker-in-Docker (dind) | Security isolation for multi-tenant workspaces |

**Development**: Backend and Celery mount the host's Docker socket directly. This allows Workspace containers to be managed without the complexity of dind. Suitable for single-developer environments.

**Production**: Uses Docker-in-Docker for isolation. Workspace containers run in a separate Docker daemon, isolated from the host. This is essential for multi-tenant security.

### Network Model

All services communicate using Docker service names (not localhost):

| Service | Service Name | Accessible From |
|---------|--------------|-----------------|
| PostgreSQL | `postgres` | backend, celery-worker, authentik |
| Redis | `redis` | backend, celery-worker, authentik |
| Backend API | `backend` | gateway, frontend (via proxy) |
| Frontend | `frontend` | gateway |
| Gateway | `gateway` | External traffic |

**Important**: When running in Docker, use service names (e.g., `postgres`, `redis`) instead of `localhost` or `127.0.0.1`. The `localhost` address inside a container refers to the container itself, not the host machine.

### Configuration

All configuration is centralized in `.env` (copy from `.env.example`). Key sections:

**Infrastructure (shared by all services):**
| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_HOST` | PostgreSQL hostname | `postgres` (Docker service name) |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_DB` | Database name | `atomsx` |
| `POSTGRES_USER` | Database user | `atomsx` |
| `POSTGRES_PASSWORD` | Database password | `atomsx_password` |
| `REDIS_HOST` | Redis hostname | `redis` (Docker service name) |
| `REDIS_PORT` | Redis port | `6379` |

**Application:**
| Variable | Description | Default |
|----------|-------------|---------|
| `DJANGO_SECRET_KEY` | Django secret key | Required (change in production!) |
| `DJANGO_DEBUG` | Debug mode | `True` (dev) / `False` (prod) |
| `DJANGO_ALLOWED_HOSTS` | Allowed hosts | `localhost,127.0.0.1,backend` |
| `CORS_ALLOWED_ORIGINS` | CORS origins | `http://localhost:5173,...` |

**OIDC (Authentik):**
| Variable | Description | Default |
|----------|-------------|---------|
| `OIDC_PROVIDER_URL` | OIDC provider URL | `http://authentik:9000/application/o/atomsx/` |
| `OIDC_CLIENT_ID` | OIDC client ID | `atomsx` |
| `OIDC_CLIENT_SECRET` | OIDC client secret | Required |
| `OIDC_REDIRECT_URI` | OIDC callback URL | `http://localhost/api/auth/callback` |

**Workspace:**
| Variable | Description | Default |
|----------|-------------|---------|
| `WORKSPACE_NETWORK_NAME` | Docker network for workspaces | `atomsx-workspaces` |
| `WORKSPACE_BASE_IMAGE` | Docker image for workspaces | `atomsx-workspace:latest` |

**Docker-in-Docker (production only):**
| Variable | Description | Default |
|----------|-------------|---------|
| `DIND_ENABLED` | Enable dind mode | `true` (prod) / `false` (dev) |
| `DOCKER_HOST` | Docker client connection URL | `unix:///var/run/dind/docker.sock` |

## Development

### Available Make Commands

```bash
make dev          # Start development environment
make dev-d        # Start development environment (detached)
make prod         # Start production environment
make down         # Stop all services
make build-prod   # Build production images
make logs         # View all logs
make logs-backend # View backend logs
make migrate      # Run database migrations
make superuser    # Create superuser
make clean        # Remove volumes (destructive)
```

### Backend (Django)

```bash
# Run migrations
make migrate
# Or: docker compose exec backend uv run python manage.py migrate

# Create migrations
docker compose exec backend uv run python manage.py makemigrations

# Run tests
docker compose exec backend uv run pytest

# Shell
docker compose exec backend uv run python manage.py shell
```

### Frontend (Vue 3)

```bash
# Install dependencies
cd frontend
npm install

# Development server
npm run dev

# Build for production
npm run build
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | GET | Initiate OIDC login |
| `/api/auth/callback` | GET | OIDC callback |
| `/api/auth/logout` | POST | Logout |
| `/api/auth/me` | GET | Current user info |
| `/api/workspaces/` | GET, POST | List/create workspaces |
| `/api/workspaces/:id` | GET, DELETE | Get/delete workspace |
| `/api/sessions/` | POST | Start session |
| `/api/sessions/:id` | GET | Get session history |
| `/api/sessions/:id/stream` | GET | SSE stream for responses |
| `/api/sessions/:id/messages` | POST | Send message |
| `/api/sessions/:id/interrupt` | POST | Interrupt response |

## Security Architecture

### Docker-in-Docker Isolation

The platform uses Docker-in-Docker (dind) to ensure complete isolation between:

1. **Host Docker**: The host machine's Docker daemon and containers
2. **dind Docker**: The isolated Docker daemon for Workspace containers

**Benefits**:
- Workspace containers cannot escape to host Docker
- Control plane compromise only affects dind environment, not host
- Follows principle of least privilege
- Clear security boundary for auditing

**What runs in dind**:
- All Workspace containers (user sandboxes)
- Workspace Docker networks
- Workspace Docker volumes

**What stays on host**:
- Control plane containers (Django, Celery, PostgreSQL, Redis)
- Gateway (OpenResty)
- Authentik (OIDC Provider)

### Migration from Host Docker

If you have an existing deployment using host Docker socket:

1. **Stop all services**: `docker-compose down`
2. **Backup data**: Workspace data is stored in Docker volumes
3. **Update configuration**: Pull latest changes with dind support
4. **Start services**: `docker-compose up -d`
5. **Recreate Workspaces**: Existing Workspace containers need to be recreated in dind

Note: Workspace containers created with host Docker will not appear in dind. Users will need to recreate their Workspaces.

## MVP Scope

This MVP includes:

- ✅ OIDC authentication (single provider)
- ✅ Workspace creation and management
- ✅ Agent conversation with streaming responses
- ✅ Real-time preview in isolated containers
- ✅ Multi-tenant isolation
- ✅ Docker-in-Docker for secure container management

Not included in MVP:

- ❌ Publishing and deployment
- ❌ Public access routes
- ❌ Multiple OIDC providers
- ❌ Workspace pause/resume/snapshot

## License

MIT License