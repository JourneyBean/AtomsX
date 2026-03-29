# Workspace Container Architecture

## Overview

Each workspace runs in an isolated Docker container with:
- **Workspace Client**: Python client that connects to Backend via WebSocket
- **Claude Agent SDK**: AI agent runtime for code generation
- **Preview Server**: Vite Dev Server for Vue.js applications
- **Source Files**: Bind-mounted user data directory

## Architecture Components

### Backend Services

```
┌─────────────────────────────────────────────────────────────────┐
│                         Backend (Django)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ REST API    │  │ WebSocket   │  │ Celery      │             │
│  │ (Views)     │  │ (Channels)  │  │ (Tasks)     │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│         │                │                │                      │
│         └────────────────┼────────────────┘                      │
│                          │                                       │
│                    ┌─────▼─────┐                                 │
│                    │   Redis   │                                 │
│                    │ (Pub/Sub) │                                 │
│                    └───────────┘                                 │
└──────────────────────────────────────────────────────────────────┘
```

### Workspace Container

```
┌──────────────────────────────────────────────────────────────────┐
│                     Workspace Container                           │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Workspace Client (Python)                    │   │
│  │  - WebSocket connection to Backend                        │   │
│  │  - Token-based authentication                             │   │
│  │  - Multi-session management                               │   │
│  │  - Claude Agent SDK integration                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                          │                                       │
│         ┌────────────────┼────────────────┐                      │
│         ▼                ▼                ▼                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ /home/user/ │  │ /home/user/ │  │ Preview     │              │
│  │ workspace/  │  │ history/    │  │ Server      │              │
│  │ (code)      │  │ (sessions)  │  │ (port 3000) │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## Communication Flow

### Task Execution Flow

```
Browser                Backend              Workspace Client
   │                      │                        │
   │──POST /messages──▶  │                        │
   │                      │──WebSocket "task"──▶  │
   │                      │                        │──Claude SDK──▶
   │                      │                        │
   │                      │◀─WebSocket "stream"──  │
   │◀─SSE stream────────  │                        │
   │                      │                        │
   │                      │◀─WebSocket "complete"─ │
   │◀─SSE "done"────────  │                        │
```

### Session Resume Flow

```
Browser                Backend              Workspace Client
   │                      │                        │
   │──POST /resume───▶   │                        │
   │   {history_id}       │                        │
   │                      │──WebSocket "resume"──▶ │
   │                      │                        │──Load history──▶
   │                      │                        │──Claude SDK──▶
   │                      │◀─WebSocket "stream"──  │
   │◀─SSE stream────────  │                        │
```

## Workspace Client

### Features

1. **WebSocket Connection**: Maintains persistent connection to Backend
2. **Token Authentication**: Authenticates using workspace-specific token
3. **Multi-session Support**: Handles multiple concurrent Claude sessions
4. **Session Resume**: Resumes previous sessions from history
5. **User Interrupt**: Supports interrupting ongoing tasks
6. **Ask User**: Handles interactive questions from Claude

### Message Protocol

| Direction | Type | Description |
|-----------|------|-------------|
| Backend → Client | `task` | Start a new task |
| Backend → Client | `resume` | Resume from history |
| Backend → Client | `interrupt` | Interrupt current task |
| Backend → Client | `user_input` | Response to ask_user |
| Client → Backend | `stream` | Streaming content |
| Client → Backend | `ask_user` | Request user input |
| Client → Backend | `complete` | Task completed |
| Client → Backend | `interrupted` | Task interrupted |
| Client → Backend | `error` | Error occurred |

### History Storage

Sessions are stored in `/home/user/history/`:

```
/home/user/history/
├── index.json                    # Session index
└── sessions/
    ├── {history_session_id}/
    │   ├── session.json          # Session metadata
    │   └── messages.jsonl        # Conversation history
    └── ...
```

The `index.json` contains:
```json
{
  "{history_session_id}": {
    "created_at": "2024-01-15T10:30:00Z",
    "last_activity": "2024-01-15T11:00:00Z"
  }
}
```

## Container Lifecycle

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Creating  │────▶│   Running   │────▶│   Stopping  │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    Error    │     │   Deleting  │     │   Deleted   │
└─────────────┘     └─────────────┘     └─────────────┘
```

### Token Lifecycle

1. **Creation**: WorkspaceToken generated when container is created
2. **Injection**: Token injected as `ATOMSX_AUTH_TOKEN` environment variable
3. **Usage**: Workspace Client uses token for WebSocket authentication
4. **Cleanup**: Token deleted when container stops or is deleted

## Security Model

### Container Isolation

1. **Network Isolation**: All workspace containers connected to isolated Docker network (`atomsx-workspaces`)

2. **No Docker Socket Access**: Containers cannot access host's Docker socket

3. **Dropped Capabilities**: Containers run with minimal Linux capabilities:
   ```yaml
   cap_drop: ['ALL']
   cap_add: ['CHOWN', 'SETUID', 'SETGID']
   ```

4. **Resource Limits**:
   - Memory: 512MB
   - CPU: 50% quota
   - No swap

5. **No Privilege Escalation**: `no-new-privileges` security option

### Authentication

1. **User Authentication**: OIDC via Authentik (or other provider)
2. **Workspace Ownership**: Each workspace linked to user
3. **Token Authentication**: Workspace-specific tokens for WebSocket
4. **Internal API**: Service-to-service auth via `ATOMSX_INTERNAL_API_TOKEN`

### File Operation Boundaries

Agent file operations are restricted to:
- **Allowed paths**: `/home/user/workspace/`
- **Forbidden paths**: `/home/user/workspace/.git/`, `/home/user/workspace/.env`
- **Max file size**: 100KB

## Port Mapping

Each workspace container exposes port 3000 for the Preview Server.
The host port is dynamically assigned and tracked in `workspace.container_host`.

## Preview Access Flow

1. User navigates to `http://{workspace-id}.preview.local`
2. OpenResty gateway intercepts the request
3. Lua script verifies authentication via Django API
4. Django checks workspace ownership
5. Gateway proxies to the container's preview server

## Environment Variables

### Backend Configuration

| Variable | Description |
|----------|-------------|
| `WORKSPACE_CLIENT_WS_URL` | WebSocket URL for Workspace Client |
| `WORKSPACE_CLIENT_HTTP_URL` | HTTP URL for internal API |
| `ATOMSX_INTERNAL_API_TOKEN` | Token for service-to-service auth |

### Container Environment

| Variable | Description |
|----------|-------------|
| `WORKSPACE_ID` | UUID of the workspace |
| `ATOMSX_AUTH_TOKEN` | WebSocket authentication token |
| `ATOMSX_BACKEND_WS_URL` | Backend WebSocket URL |
| `ATOMSX_BACKEND_HTTP_URL` | Backend HTTP URL |
| `ATOMSX_INTERNAL_API_TOKEN` | Token for fetching agent config |

## Known Limitations (MVP)

1. **Single-machine deployment**: Cannot scale to multiple hosts
2. **No container checkpointing**: Cannot pause/resume workspaces
3. **Fixed resource limits**: All workspaces have the same limits
4. **No GPU support**: Containers cannot access GPU

## Image Prebuilding

### Overview

Workspace images can be prebuilt to reduce container startup time. This is especially useful in production environments where fast workspace creation is critical.

### Prebuild Command

```bash
# Prebuild the default workspace image
python manage.py prebuild_workspace_images

# Options:
#   --image <name>    Custom image name (default: WORKSPACE_BASE_IMAGE setting)
#   --force           Force rebuild even if image exists
#   --verbose         Show detailed output
```

### Deployment Workflow

1. **Initial Deployment**:
   ```bash
   # After deploying code, prebuild the workspace image
   python manage.py prebuild_workspace_images
   ```

2. **Verify Image**:
   ```bash
   # Check image exists in Docker registry
   docker images | grep atomsx-workspace
   ```

3. **Update Image**:
   ```bash
   # Force rebuild with latest dependencies
   python manage.py prebuild_workspace_images --force
   ```

### Timeout Configuration

Workspace creation timeout is configurable via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKSPACE_CREATION_SOFT_TIMEOUT` | 300s | Soft timeout - allows cleanup |
| `WORKSPACE_CREATION_HARD_TIMEOUT` | 360s | Hard timeout - force termination |

### Image Strategy

When creating a workspace:
1. Check if prebuilt image exists (`WORKSPACE_BASE_IMAGE`)
2. If exists → use directly (fast path)
3. If not → pull fallback image `node:20-slim` (slow path)
4. Audit log includes `image_source` field to track which path was used

## Future Evolution

### Kubernetes Migration

1. Replace Docker SDK with Kubernetes Python client
2. Convert containers to Pods with:
   - Init container for workspace setup
   - Main container for preview server
   - Sidecar for agent runtime
3. Use NetworkPolicies for isolation
4. Use ResourceQuotas for multi-tenant limits

### Builder/Deployer Integration

For publishing capabilities:
1. Create separate Builder service for image builds
2. Create Deployer service for K8s deployments
3. Store deployment manifests in database
4. Implement rollback via image tags