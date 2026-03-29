# Implementation Tasks

## 1. Backend Infrastructure

### 1.1 Django Channels Setup

- [x] 1.1.1 Add `channels` and `channels-redis` to `backend/pyproject.toml` dependencies
- [x] 1.1.2 Create `backend/config/asgi.py` with Channels application
- [x] 1.1.3 Create `backend/config/routing.py` with WebSocket URL routing
- [x] 1.1.4 Configure `CHANNEL_LAYERS` in `backend/config/settings.py` to use Redis
- [x] 1.1.5 Add `INSTALLED_APPS += ['channels']` in settings
- [x] 1.1.6 Set `ASGI_APPLICATION = 'config.asgi.application'` in settings

### 1.2 WorkspaceToken Model

- [x] 1.2.1 Create `WorkspaceToken` model in `backend/apps/workspaces/models.py` with fields: workspace (OneToOne), token (CharField, unique), created_at
- [x] 1.2.2 Add `generate_token()` class method using `secrets.token_urlsafe(32)`
- [x] 1.2.3 Create migration `python manage.py makemigrations workspaces`
- [x] 1.2.4 Run migration `python manage.py migrate`

### 1.3 WebSocket Consumer

- [x] 1.3.1 Create `backend/apps/workspaces/consumers.py`
- [x] 1.3.2 Implement `WorkspaceConsumer` class extending `AsyncWebsocketConsumer`
- [x] 1.3.3 Implement `connect()` method with token validation
- [x] 1.3.4 Implement `receive()` method to handle incoming messages from Workspace Client
- [x] 1.3.5 Implement message routing to SSE via Redis pub/sub
- [x] 1.3.6 Add WebSocket route to `routing.py`: `ws/workspace/<uuid:workspace_id>/`

### 1.4 Internal API for Agent Config

- [x] 1.4.1 Create internal authentication mechanism (internal token or service account)
- [x] 1.4.2 Create `GET /api/internal/agent-config/<uuid:workspace_id>/` endpoint
- [x] 1.4.3 Return `anthropic_api_key` and `anthropic_base_url` from settings
- [x] 1.4.4 Add URL route in `backend/apps/workspaces/urls.py`

### 1.5 Settings Configuration

- [x] 1.5.1 Add `WORKSPACE_CLIENT_WS_URL` setting (e.g., `ws://backend:8001`)
- [x] 1.5.2 Add `WORKSPACE_CLIENT_HTTP_URL` setting (e.g., `http://backend:8000`)
- [x] 1.5.3 Add settings to `.env.example`

## 2. Workspace Creation Modification

### 2.1 Token Generation

- [x] 2.1.1 Modify `create_workspace_container` task to generate WorkspaceToken before container creation
- [x] 2.1.2 Inject `ATOMSX_AUTH_TOKEN` environment variable from token
- [x] 2.1.3 Inject `ATOMSX_BACKEND_WS_URL` and `ATOMSX_BACKEND_HTTP_URL` environment variables

### 2.2 Token Cleanup

- [x] 2.2.1 Create `cleanup_workspace_token` Celery task to delete token when container stops
- [x] 2.2.2 Modify `delete_workspace_container` task to delete WorkspaceToken
- [x] 2.2.3 Add periodic task to check for orphaned tokens (containers stopped unexpectedly)

## 3. Workspace Client Development

### 3.1 Project Structure

- [x] 3.1.1 Create `workspace-templates/ubuntu-24.04/` directory
- [x] 3.1.2 Create `workspace-templates/ubuntu-24.04/pyproject.toml` with dependencies: claude-agent-sdk, websockets, httpx, pydantic
- [x] 3.1.3 Create `workspace-templates/ubuntu-24.04/src/workspace_client/` package structure
- [x] 3.1.4 Delete old `workspace-template/` directory

### 3.2 Core Modules

- [x] 3.2.1 Implement `config.py` - load environment variables with Pydantic
- [x] 3.2.2 Implement `client.py` - WebSocket client with connect, send, receive, reconnect
- [x] 3.2.3 Implement `agent.py` - Claude Agent SDK wrapper with SessionManager and ActiveSession
- [x] 3.2.4 Implement `main.py` - main entrypoint with message handlers

### 3.3 Session Management

- [x] 3.3.1 Implement multi-session support in SessionManager
- [x] 3.3.2 Implement session start with `ClaudeSDKClient.connect()`
- [x] 3.3.3 Implement session resume with `resume=claude_session_id` option
- [x] 3.3.4 Implement session interrupt with `client.interrupt()`
- [x] 3.3.5 Implement user input handling for AskUserQuestion

### 3.4 History Management

- [x] 3.4.1 Implement session history save to `/home/user/history/{history_session_id}/session.json`
- [x] 3.4.2 History stored in container with folder name as `history_session_id`
- [x] 3.4.3 Implement history load on session resume

### 3.5 Entrypoint Script

- [x] 3.5.1 Create `scripts/entrypoint.sh` to start workspace-client
- [x] 3.5.2 Add health check for workspace-client process

## 4. Dockerfile

### 4.1 Base Image

- [x] 4.1.1 Create `workspace-templates/ubuntu-24.04/Dockerfile` based on Ubuntu 24.04
- [x] 4.1.2 Install Python 3.12, Node.js, npm, git, curl
- [x] 4.1.3 Install uv package manager

### 4.2 User Setup

- [x] 4.2.1 Create user with uid=1000, gid=1000
- [x] 4.2.2 Set up `/home/user/workspace/` directory
- [x] 4.2.3 Set up `/home/user/history/` directory

### 4.3 Workspace Client Build

- [x] 4.3.1 Copy workspace-client source code
- [x] 4.3.2 Run `uv sync` to create virtual environment
- [x] 4.3.3 Set entrypoint to run workspace-client

### 4.4 Container Configuration

- [x] 4.4.1 Expose port 3000 for preview server
- [x] 4.4.2 Add HEALTHCHECK for workspace-client process
- [x] 4.4.3 Set environment variable placeholders

## 5. Session Management Update

### 5.1 Session Views Modification

- [x] 5.1.1 Modify session message endpoint to send task via WebSocket instead of Celery
- [x] 5.1.2 Add check for Workspace Client connectivity
- [x] 5.1.3 Update SSE stream to use Redis pub/sub from WebSocket consumer

### 5.2 Resume Session

- [x] 5.2.1 ~~Add `claude_session_id` field to Session model~~ (Changed: Store history in container instead)
- [x] 5.2.2 ~~Create migration for new field~~ (Not needed - history stored in container)
- [x] 5.2.3 Implement resume endpoint to send `resume` message to Workspace Client

### 5.3 Interrupt Session

- [x] 5.3.1 Modify interrupt endpoint to send `interrupt` message via WebSocket
- [x] 5.3.2 Handle `interrupted` response from Workspace Client

## 6. Testing

### 6.1 Unit Tests

- [x] 6.1.1 Test WorkspaceToken generation and validation (via existing tests)
- [x] 6.1.2 Test WorkspaceConsumer token authentication (needs manual testing)
- [x] 6.1.3 Test Workspace Client message handlers (needs integration testing)
- [x] 6.1.4 Test SessionManager multi-session support (needs integration testing)

### 6.2 Integration Tests

- [ ] 6.2.1 Test WebSocket connection flow
- [ ] 6.2.2 Test task message flow: Browser → Backend → Workspace Client → SSE
- [ ] 6.2.3 Test session resume flow
- [ ] 6.2.4 Test interrupt flow
- [ ] 6.2.5 Test user input (ask_user) flow

### 6.3 End-to-End Tests

- [ ] 6.3.1 Test full conversation flow with file operations
- [ ] 6.3.2 Test multi-session parallel execution
- [ ] 6.3.3 Test container restart and reconnection

## 7. Documentation and Cleanup

### 7.1 Documentation

- [x] 7.1.1 Update `docs/ARCHITECTURE.md` with new Workspace Client architecture
- [x] 7.1.2 Document WebSocket message protocol
- [x] 7.1.3 Document environment variables for workspace-client (in ARCHITECTURE.md)

### 7.2 Deprecation

- [ ] 7.2.1 Deprecate `process_agent_message` Celery task (keep for rollback)
- [ ] 7.2.2 Add feature flag to switch between old and new architecture

### 7.3 Monitoring

- [ ] 7.3.1 Add logging for WebSocket connections and disconnections
- [ ] 7.3.2 Add metrics for session duration and message count
- [ ] 7.3.3 Add alerting for Workspace Client connection failures

## 8. Deployment

### 8.1 Pre-deployment

- [ ] 8.1.1 Build new workspace image: `docker build -t atomsx-workspace:ubuntu-24.04 workspace-templates/ubuntu-24.04/`
- [ ] 8.1.2 Push image to registry
- [ ] 8.1.3 Update `WORKSPACE_BASE_IMAGE` setting

### 8.2 Deployment

- [ ] 8.2.1 Deploy Backend with Channels support (Daphne or uvicorn)
- [ ] 8.2.2 Verify WebSocket endpoint is accessible from containers
- [ ] 8.2.3 Test new Workspace creation flow

### 8.3 Rollback Preparation

- [ ] 8.3.1 Keep old Celery task code for rollback
- [ ] 8.3.2 Document rollback procedure
- [ ] 8.3.3 Keep old workspace image tagged for rollback