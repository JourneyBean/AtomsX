## Context

### Current State

The realtime preview feature has a broken request chain:

```
User Browser
    │
    ▼ http://{workspace-id}.preview.local
OpenResty Gateway (atomsx-network)
    │
    │ ❌ Cannot resolve workspace-{uuid} container name
    │ ❌ Different network (atomsx-workspaces)
    │ ❌ container_host = "dind:32768" (wrong format)
    ▼
Connection Failed
```

### Root Causes

1. **Network Isolation**: Gateway in `atomsx-network`, workspace containers in `atomsx-workspaces` - no cross-network DNS resolution
2. **Incorrect container_host**: Stored as `dind:{port}` but Gateway needs Docker DNS name
3. **No Preview Process**: workspace-client runs but nothing listens on port 3000

### Stakeholders

- **Users**: Need working preview to see their code changes in real-time
- **Claude Agent**: Needs guidance on how to start preview servers
- **Frontend**: Needs placeholder UI when preview unavailable

## Goals / Non-Goals

**Goals:**
- Fix network routing from Gateway to workspace containers
- Standardize container_host format for Docker DNS resolution
- Add process management with supervisord
- Provide automatic preview server startup with graceful fallback
- Guide Claude Agent on preview server usage

**Non-Goals:**
- Dynamic preview server configuration (future)
- Multiple preview servers per workspace
- Preview log streaming to frontend
- Custom port configuration

## Decisions

### Decision 1: Network Configuration - Gateway Joins Workspace Network

**Chosen**: Gateway container joins `atomsx-workspaces` network

**Alternatives Considered**:

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A. Gateway joins workspace network | Add `atomsx-workspaces` to Gateway | Simple, no container changes | Gateway can reach all workspace ports |
| B. Workspace joins main network | Each workspace joins `atomsx-network` | Isolated from other workspaces | More network config per container |
| C. Shared network | All containers in one network | Simplest | No isolation between workspaces |

**Rationale**: Option A is simplest for MVP. Security is maintained because:
- Gateway only proxies to port 3000 (enforced by nginx config)
- Auth verification happens before proxy
- Workspace isolation still exists (containers can't reach each other)

### Decision 2: container_host Format - Docker DNS Name

**Chosen**: `workspace-{uuid}:3000`

**Alternatives Considered**:

| Option | Format | Works With | Limitations |
|--------|--------|------------|-------------|
| A. Container name | `workspace-{uuid}:3000` | Docker DNS | Requires same network |
| B. IP address | `172.18.0.5:3000` | Any network | IP changes on restart |
| C. dind port | `dind:32768` | Port mapping | Gateway can't reach dind |

**Rationale**: Option A is the standard Docker approach. With Decision 1 (shared network), container names resolve correctly.

### Decision 3: Process Management - Supervisord

**Chosen**: Supervisord as PID 1 managing two processes

**Alternatives Considered**:

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A. Supervisord | Classic process manager | Mature, simple config | Extra dependency |
| B. systemd | Linux init system | Full service management | Requires privileged container |
| C. Custom script | Shell script with wait | No dependencies | No auto-restart, no logging |

**Rationale**: Supervisord is:
- Widely used for container process management
- Simple ini-style configuration
- Built-in log rotation and process monitoring
- Auto-restart on failure

### Decision 4: Preview Server Startup - Script with Fallback

**Chosen**: `start_app.sh` with placeholder fallback

**Flow**:
```
Container Start
    │
    ▼
start_preview.sh
    │
    ├── start_app.sh exists?
    │   │
    │   ├── YES → Execute start_app.sh
    │   │           │
    │   │           ├── Success → Preview server running
    │   │           │
    │   │           └── Failure → Placeholder (with error message)
    │   │
    │   └── NO → Placeholder (with guidance message)
    │
    ▼
Placeholder HTTP Server (port 3000)
    │
    └── Returns JSON: {status: "placeholder", message: "...", hint: "..."}
```

**Rationale**:
- Graceful degradation instead of complete failure
- Clear feedback to users and Claude Agent about what's needed
- JSON response allows frontend to show contextual help

## Architecture

### Network Topology (After Fix)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Docker Networks                                 │
│                                                                             │
│   atomsx-network                         atomsx-workspaces                  │
│   ┌─────────────────────────┐           ┌─────────────────────────┐        │
│   │                         │           │                         │        │
│   │   ┌─────────────┐       │           │   ┌─────────────┐      │        │
│   │   │   backend   │       │           │   │ workspace-1 │      │        │
│   │   └─────────────┘       │           │   └─────────────┘      │        │
│   │                         │           │                         │        │
│   │   ┌─────────────┐       │           │   ┌─────────────┐      │        │
│   │   │   frontend  │       │           │   │ workspace-2 │      │        │
│   │   └─────────────┘       │           │   └─────────────┘      │        │
│   │                         │           │                         │        │
│   │   ┌─────────────┐       ├───────────┤   ┌─────────────┐      │        │
│   │   │   gateway   │◄──────┤ BOTH      │   │ workspace-3 │      │        │
│   │   └─────────────┘       ├───────────┤   └─────────────┘      │        │
│   │                         │           │                         │        │
│   └─────────────────────────┘           └─────────────────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Request Flow (After Fix)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────────────────────┐
│ User Browser │────▶│   Gateway    │────▶│        Workspace Container       │
│              │     │ (OpenResty)  │     │                                  │
└──────────────┘     └──────────────┘     │  ┌────────────────────────────┐  │
                            │              │  │      supervisord           │  │
                            │              │  │  ┌──────────────────────┐  │  │
                     1. Extract workspace_id │  │  │ workspace-client    │  │  │
                        from Host header     │  │  │ (WebSocket to       │  │  │
                            │              │  │  │  backend)            │  │  │
                            │              │  │  └──────────────────────┘  │  │
                     2. Auth verification    │  │                            │  │
                        via Lua to backend   │  │  ┌──────────────────────┐  │  │
                            │              │  │  │ preview-server       │  │  │
                            │              │  │  │ (port 3000)          │  │  │
                     3. Set $container_host  │  │  │                      │  │  │
                        = "workspace-{id}:3000│  │  │ - start_app.sh OR   │  │  │
                            │              │  │  │ - placeholder        │  │  │
                     4. proxy_pass           │  │  └──────────────────────┘  │  │
                        http://$container_host│  └────────────────────────────┘  │
                            ▼              └──────────────────────────────────┘
                     5. Return preview
                        content to user
```

### Workspace Container Internal Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           Workspace Container                                 │
│                                                                              │
│   supervisord (PID 1)                                                        │
│   │                                                                          │
│   ├── workspace-client                                                       │
│   │   │                                                                      │
│   │   ├── WebSocket connection to backend                                    │
│   │   ├── Claude Agent SDK process                                          │
│   │   └── Session management                                                 │
│   │                                                                          │
│   └── preview-server                                                         │
│       │                                                                      │
│       └── start_preview.sh                                                   │
│           │                                                                  │
│           ├── /home/user/workspace/start_app.sh exists?                     │
│           │   │                                                              │
│           │   ├── YES → execute start_app.sh                                 │
│           │   │       │                                                      │
│           │   │       ├── Success → Dev server on port 3000                  │
│           │   │       │                                                      │
│           │   │       └── Failure → placeholder_server.py                    │
│           │   │               (with error message)                           │
│           │   │                                                              │
│           │   └── NO → placeholder_server.py                                 │
│           │           (with guidance message)                                │
│           │                                                                  │
│           └── placeholder_server.py (Python HTTP server)                     │
│               Returns JSON on port 3000:                                     │
│               {                                                              │
│                 "status": "placeholder",                                     │
│                 "message": "no_start_script" | "start_failed",               │
│                 "detail": "...",                                             │
│                 "hint": "Create start_app.sh..."                             │
│               }                                                              │
│                                                                              │
│   Mounted Volumes:                                                           │
│   /home/user/workspace  → source code (from host)                           │
│   /home/user/history    → session history (from host)                       │
│   /home/user/logs       → process logs (container-local)                    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Risks / Trade-offs

### Risk 1: Gateway Can Access All Workspace Ports

**Risk**: Gateway joining workspace network means it can theoretically reach any port on workspace containers.

**Mitigation**:
- Nginx config only proxies to port 3000
- Auth verification happens before proxy
- Workspace containers don't expose sensitive services (no Docker socket, no DB)

**Acceptance**: Acceptable for MVP. Future hardening can use network policies or separate proxy network.

### Risk 2: Supervisord Adds Complexity

**Risk**: Additional process manager means more things to debug.

**Mitigation**:
- Simple configuration with clear separation
- Log files in `/home/user/logs/` for debugging
- Health check monitors both processes

**Acceptance**: Standard pattern for multi-process containers.

### Risk 3: start_app.sh Security

**Risk**: Arbitrary script execution could be a security concern.

**Mitigation**:
- Script runs as non-root `user` account
- Container is already isolated
- Script is user-created (in their own workspace)

**Acceptance**: Acceptable within workspace isolation model.

### Trade-off: No Dynamic Process Management

**Trade-off**: Once start_app.sh is created, container must be recreated to pick it up (supervisord doesn't auto-detect new scripts).

**Mitigation**: Claude Agent can inform user that workspace needs restart.

**Acceptance**: Acceptable for MVP. Future: add supervisorctl RPC interface.

## Migration Plan

### Phase 1: Build New Workspace Image

```bash
# Build image with supervisord
cd workspace-templates/ubuntu-24.04
docker build -t atomsx-workspace:latest .
```

### Phase 2: Update Network Configuration

```yaml
# docker-compose.yml or docker-compose.prod.yml
gateway:
  networks:
    - default
    - workspaces

networks:
  workspaces:
    name: atomsx-workspaces
    external: true
```

### Phase 3: Deploy Changes

1. **New workspaces**: Automatically use new image and network config
2. **Existing workspaces**: Recreate with new image
   ```bash
   # For each running workspace
   docker stop workspace-{uuid}
   docker rm workspace-{uuid}
   # Backend will recreate with new image
   ```

### Rollback Strategy

1. **Network**: Remove Gateway from workspace network in docker-compose
2. **Image**: Revert to previous workspace image tag
3. **Database**: No schema changes, no rollback needed

## Open Questions

1. **Log rotation**: Should we configure logrotate for `/home/user/logs/`?
   - **Decision**: For MVP, rely on Docker log limits. Future: add logrotate.

2. **Graceful shutdown**: Should preview server get SIGTERM before container stops?
   - **Decision**: Supervisord handles graceful shutdown with default stopwaitsecs=10.

3. **Resource limits per process**: Should workspace-client and preview-server have separate memory limits?
   - **Decision**: For MVP, share container limits (512MB total). Future: cgroups per process.