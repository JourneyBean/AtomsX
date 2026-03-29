## Why

The realtime preview feature is currently non-functional due to a network routing mismatch. The Gateway cannot reach Workspace containers because they are on separate Docker networks, and the `container_host` field stores an incorrect format (`dind:{port}` instead of container name). Additionally, no preview server process is running on port 3000 in workspace containers.

This change fixes the full chain: network routing, container naming, process management, and user experience for the preview feature.

## What Changes

- **container_host format**: Changed from `dind:{port}` to `workspace-{uuid}:3000` for Docker DNS resolution
- **Network routing**: Gateway joins `atomsx-workspaces` network to reach workspace containers via container name
- **Process management**: Supervisord added to workspace image to manage workspace-client and preview-server processes
- **Preview server auto-start**: New mechanism with `start_app.sh` script support and fallback placeholder server
- **System prompt enhancement**: Added preview-related guidance to Claude Agent context

## Capabilities

### New Capabilities

- `preview-server-management`: Capability for managing preview server lifecycle within workspace containers, including auto-start mechanism, placeholder fallback, and start_app.sh script support

### Modified Capabilities

- `realtime-preview`: Network routing requirements changed - Gateway must be able to resolve workspace containers by name; container_host format standardized to Docker DNS compatible format
- `workspace-client`: Added preview server management responsibility; supervisord as process manager; environment context expanded with preview guidance

## Impact

### Code Changes

- `backend/apps/workspaces/tasks.py`: Change container_host format and network configuration
- `backend/apps/workspaces/models.py`: Update container_host documentation
- `gateway/docker-compose.yml`: Add network configuration for Gateway to join workspace network
- `workspace-templates/ubuntu-24.04/Dockerfile`: Add supervisord installation and configuration
- `workspace-templates/ubuntu-24.04/scripts/`: New scripts for supervisord, preview server, and placeholder
- `workspace-templates/ubuntu-24.04/src/workspace_client/agent.py`: Update ENV_CONTEXT with preview guidance

### Infrastructure Changes

- Gateway container will join `atomsx-workspaces` network (in addition to `atomsx-network`)
- Workspace containers will have supervisord as PID 1 instead of direct entrypoint

### API Changes

- None (internal routing change only)

### Dependencies

- `supervisor` package added to workspace image

## Non-goals

- Dynamic preview server configuration via API (future enhancement)
- Multiple preview servers per workspace (single port 3000 only)
- Preview server log streaming to frontend (can be added later)
- Custom port configuration (always 3000)

## Security Impact

- **Network**: Gateway gains access to workspace containers - but only on port 3000 (preview port)
- **Authentication**: No change - existing auth verification via Django session remains
- **Authorization**: No change - workspace ownership verification unchanged
- **Audit**: No change - existing PREVIEW_ACCESS audit events unchanged

## Rollout Plan

1. Deploy updated workspace image with supervisord
2. Update Gateway network configuration
3. Recreate existing workspace containers (rolling update)
4. Verify preview URLs work correctly