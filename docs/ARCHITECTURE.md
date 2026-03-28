# Workspace Container Architecture

## Overview

Each workspace runs in an isolated Docker container with:
- **Agent Runtime**: Python environment with Claude SDK
- **Preview Server**: Vite Dev Server for Vue.js applications
- **Source Files**: Isolated Docker volume

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

## Security Model

### Container Isolation

1. **Network Isolation**: All workspace containers are connected to an isolated Docker network (`atomsx-workspaces`)

2. **No Docker Socket Access**: Containers cannot access the host's Docker socket

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

### File Operation Boundaries

Agent file operations are restricted to:
- **Allowed paths**: `/workspace/src/`, `/workspace/public/`, `/workspace/components/`
- **Forbidden paths**: `/workspace/node_modules/`, `/workspace/.git/`, `/workspace/.env`
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

## Known Limitations (MVP)

1. **Single-machine deployment**: Cannot scale to multiple hosts
2. **No container checkpointing**: Cannot pause/resume workspaces
3. **Fixed resource limits**: All workspaces have the same limits
4. **No GPU support**: Containers cannot access GPU

## Future Evolution

### Kubernetes Migration

1. Replace Docker SDK with Kubernetes Python client
2. Convert containers to Pods with:
   - Init container for workspace setup
   - Main container for preview server
   - Sidecar for agent runtime
3. Use NetworkPolicies for isolation
4. Use ResourceQuotas for multi-tenant limits

### WebSocket Support

When bidirectional real-time communication is needed:
1. Add Django Channels with Redis channel layer
2. Replace SSE with WebSocket connections
3. Enable real-time collaborative features

### Builder/Deployer Integration

For publishing capabilities:
1. Create separate Builder service for image builds
2. Create Deployer service for K8s deployments
3. Store deployment manifests in database
4. Implement rollback via image tags