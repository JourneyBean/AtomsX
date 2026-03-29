## 1. Workspace Image - Supervisord Setup

- [x] 1.1 Install supervisor package in Dockerfile
- [x] 1.2 Create supervisord.conf with workspace-client and preview-server programs
- [x] 1.3 Create logs directory structure (/home/user/logs)
- [x] 1.4 Update Dockerfile ENTRYPOINT to use supervisord

## 2. Preview Server Implementation

- [x] 2.1 Create start_preview.sh script with start_app.sh detection logic
- [x] 2.2 Create placeholder_server.py with JSON response for no-script case
- [x] 2.3 Implement start_app.sh execution with error handling
- [x] 2.4 Add failure fallback to placeholder with error message
- [x] 2.5 Implement CORS handling in placeholder server

## 3. Backend - Container Host Format

- [x] 3.1 Update tasks.py to set container_host as "workspace-{uuid}:3000"
- [x] 3.2 Remove dind port mapping logic (not needed for DNS resolution)
- [x] 3.3 Update container_host field documentation in models.py

## 4. Network Configuration

- [x] 4.1 Update docker-compose.yml to add atomsx-workspaces network definition
- [x] 4.2 Configure Gateway service to join both networks
- [x] 4.3 Update docker-compose.dev.yml with matching network config

## 5. Claude Agent Context Enhancement

- [x] 5.1 Update ENV_CONTEXT in agent.py with preview guidance
- [x] 5.2 Add preview port information (3000)
- [x] 5.3 Add start_app.sh creation instructions
- [x] 5.4 Add common framework start commands (Vite, Next.js, Python HTTP)

## 6. Testing & Verification

- [x] 6.1 Test workspace container starts with supervisord
- [x] 6.2 Test placeholder server returns correct JSON when no start_app.sh
- [x] 6.3 Test start_app.sh execution and error handling
- [x] 6.4 Test Gateway can reach workspace container via DNS name
- [x] 6.5 Test full preview URL flow (auth → proxy → response)
- [x] 6.6 Test process auto-restart on failure

## 7. Documentation & Cleanup

- [x] 7.1 Update workspace template README with supervisord info
- [x] 7.2 Add log file location documentation
- [x] 7.3 Remove obsolete entrypoint.sh if fully replaced