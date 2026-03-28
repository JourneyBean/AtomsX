## 1. Project Setup & Infrastructure

- [x] 1.1 Create project directory structure (frontend, backend, gateway configs)
- [x] 1.2 Initialize Django project with DRF, configure PostgreSQL connection
- [x] 1.3 Initialize Vue 3 frontend project with TypeScript and Vite
- [x] 1.4 Setup Docker Compose for local development (Authentik, PostgreSQL, Redis, Django, OpenResty)
- [x] 1.5 Configure environment variables and secrets management (.env template)
- [x] 1.6 Setup Celery with Redis as broker for async task processing

## 2. OIDC Authentication (Control Plane)

- [x] 2.1 Configure Authentik OIDC Provider in Docker Compose (client_id, redirect_uri, scopes)
- [x] 2.2 Install and configure Django OIDC client library (mozilla-django-oidc or similar)
- [x] 2.3 Create User model with OIDC fields (sub, email, display_name, created_at)
- [x] 2.4 Implement OIDC login flow: redirect to Provider, callback handling, token exchange
- [x] 2.5 Implement session management (session cookie, timeout configuration 24h default)
- [x] 2.6 Implement logout flow: session termination, optional Provider logout redirect
- [x] 2.7 Create authentication middleware for protected API endpoints
- [x] 2.8 Create AuditLog model and logging utility for auth events (LOGIN, LOGOUT)
- [x] 2.9 Write unit tests for OIDC login/logout flow
- [x] 2.10 Verify multi-provider readiness (architecture allows future extension)

## 3. Workspace Management (Control Plane)

- [x] 3.1 Create Workspace model (id UUID, owner FK, name, container_id, status, created_at, updated_at)
- [x] 3.2 Create Workspace API endpoints: POST /api/workspaces (create), GET /api/workspaces (list), GET /api/workspaces/:id (detail), DELETE /api/workspaces/:id (delete)
- [x] 3.3 Implement ownership validation: user can only access their own Workspaces
- [x] 3.4 Implement Workspace name uniqueness validation per user
- [x] 3.5 Create Celery task for Workspace container creation (Docker SDK)
- [x] 3.6 Create Celery task for Workspace container deletion (stop, remove, cleanup volume)
- [x] 3.7 Implement Workspace status transitions (creating → running → error, running → deleting → deleted)
- [x] 3.8 Add audit logging for Workspace events (CREATED, DELETED, STATUS_CHANGE)
- [x] 3.9 Write unit tests for Workspace API endpoints
- [x] 3.10 Write integration tests for Workspace lifecycle (create → running → delete)

## 4. Workspace Container Runtime

- [x] 4.1 Create Dockerfile for Workspace base image (includes: Agent Runtime env, Preview Server template)
- [x] 4.2 Implement container network isolation strategy (separate Docker network per Workspace or shared isolated network)
- [x] 4.3 Implement volume mounting for Workspace source files (isolated per Workspace)
- [x] 4.4 Configure container resource limits (memory, CPU) to prevent runaway consumption
- [x] 4.5 Implement Preview Server startup in container (Vite Dev Server for Vue project template)
- [x] 4.6 Implement port mapping strategy (dynamic host port or fixed with collision handling)
- [x] 4.7 Verify container cannot access Docker socket or other containers
- [x] 4.8 Create initial Workspace template (default Vue project structure)

## 5. Agent Conversation (Control Plane + Runtime)

- [x] 5.1 Create Session model (id UUID, workspace FK, user FK, messages JSON, status, created_at, updated_at)
- [x] 5.2 Create Session API endpoints: POST /api/sessions (start), GET /api/sessions/:id (resume/history)
- [x] 5.3 Implement SSE endpoint for streaming Agent responses (/api/sessions/:id/stream)
- [x] 5.4 Implement message sending endpoint: POST /api/sessions/:id/messages
- [x] 5.5 Create Celery task for Agent message processing with Claude Agent SDK
- [x] 5.6 Implement SSE channel push from Celery Worker to frontend (Redis pub/sub or direct)
- [x] 5.7 Implement message persistence in Session.messages array
- [x] 5.8 Implement user interrupt handling (stop Celery task, close SSE, mark message interrupted)
- [x] 5.9 Implement Session ownership validation (user can only access their Sessions)
- [x] 5.10 Add audit logging for message events and file modifications
- [x] 5.11 Define Agent file operation boundaries (allowed paths, forbidden operations)
- [x] 5.12 Write unit tests for Session API endpoints
- [x] 5.13 Write integration tests for Agent conversation flow (send → stream → persist)

## 6. Preview Gateway (OpenResty)

- [x] 6.1 Configure OpenResty Docker container and lua scripts directory
- [x] 6.2 Implement Preview URL routing (*.preview.local → Workspace container)
- [x] 6.3 Implement authentication verification lua script (forward to Django /api/auth/verify)
- [x] 6.4 Implement Workspace ownership check in authentication flow
- [x] 6.5 Handle 401/403 responses from authentication (return appropriate error to client)
- [x] 6.6 Implement proxy routing to Workspace container Preview Server
- [x] 6.7 Handle Workspace not running (503 response)
- [x] 6.8 Handle Workspace not found (404 response)
- [x] 6.9 Add audit logging for Preview access events
- [x] 6.10 Configure WebSocket/SSE passthrough for Preview Server hot reload signals
- [x] 6.11 Test Preview access with valid/invalid session
- [x] 6.12 Test Preview access forbidden for other user's Workspace

## 7. Frontend Implementation (Vue 3)

- [x] 7.1 Create Login page component with OIDC login button
- [x] 7.2 Implement OIDC callback handling (receive code, complete login)
- [x] 7.3 Create Workspace List page (display user's Workspaces, create new, delete)
- [x] 7.4 Create Workspace Detail page (chat panel left, Preview frame right)
- [x] 7.5 Implement SSE client for streaming Agent responses
- [x] 7.6 Implement chat message input and send functionality
- [x] 7.7 Implement interrupt button for stopping Agent response
- [x] 7.8 Implement Preview iframe component (load Preview URL)
- [x] 7.9 Implement session state management (Vue Store/Pinia)
- [x] 7.10 Implement logout functionality
- [x] 7.11 Handle authentication errors (session expired, redirect to login)
- [x] 7.12 Create responsive layout for desktop (left chat, right preview)

## 8. Hot Reload Integration

- [x] 8.1 Configure Vite Dev Server in Workspace template for HMR
- [x] 8.2 Implement file change detection in Workspace container (file watcher)
- [x] 8.3 Test hot reload flow: Agent modifies file → Preview updates
- [x] 8.4 Handle Preview Server restart scenarios (notify frontend, reconnect)

## 9. Security & Audit

- [x] 9.1 Verify multi-tenant isolation: user A cannot access user B's Workspace/Session/Preview
- [x] 9.2 Verify Workspace container cannot access Docker socket or other containers
- [x] 9.3 Implement comprehensive audit log queries for security review
- [x] 9.4 Verify Preview URLs require authentication (no anonymous access)
- [x] 9.5 Review Django CORS configuration for frontend communication
- [x] 9.6 Review Django CSRF protection settings
- [x] 9.7 Configure secure session cookie settings (HTTPS, SameSite)

## 10. Testing & Verification

- [x] 10.1 Write end-to-end test: Login → Create Workspace → Start Session → Send Message → See Preview
- [x] 10.2 Write test: Preview reflects file modification from Agent
- [x] 10.3 Write test: Interrupt Agent response mid-stream
- [x] 10.4 Write test: Resume existing Session with history
- [x] 10.5 Write test: Delete Workspace with active Session
- [x] 10.6 Write test: Access Preview without login (should fail)
- [x] 10.7 Write test: Access other user's Preview (should fail)
- [x] 10.8 Verify all audit logs are captured for key events
- [x] 10.9 Performance test: streaming response latency under typical load
- [x] 10.10 Document manual verification checklist for MVP demo

## 11. Documentation & Cleanup

- [x] 11.1 Create README with setup instructions (Docker Compose, environment variables)
- [x] 11.2 Document API endpoints (OpenAPI/Swagger or manual documentation)
- [x] 11.3 Document Workspace container architecture and limitations
- [x] 11.4 Document future evolution path (K8s migration, WebSocket, Builder/Deployer integration)
- [x] 11.5 Clean up temporary/simplified implementations (mark for future refactor)
- [x] 11.6 Create developer onboarding guide