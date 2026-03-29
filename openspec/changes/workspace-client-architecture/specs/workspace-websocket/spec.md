# Workspace WebSocket Capability

## Purpose

Enable Backend to accept WebSocket connections from Workspace Clients and route messages appropriately.

## ADDED Requirements

### Requirement: Backend accepts Workspace Client WebSocket connections

The system SHALL allow Backend to accept WebSocket connections at `/ws/workspace/{workspace_id}/`.

#### Scenario: Valid connection accepted
- **WHEN** Workspace Client connects to `/ws/workspace/{workspace_id}/` with valid Token in Authorization header
- **THEN** system verifies token against WorkspaceToken model
- **AND** system accepts WebSocket connection
- **AND** system sends `{"type": "connected", "workspace_id": "..."}`

#### Scenario: Invalid token rejected
- **WHEN** Workspace Client connects with invalid token
- **THEN** system closes WebSocket connection with code 4001 (Unauthorized)
- **AND** system logs rejection reason

#### Scenario: Non-existent workspace rejected
- **WHEN** Workspace Client connects with workspace_id that does not exist
- **THEN** system closes WebSocket connection with code 4004 (Not Found)

### Requirement: Backend routes task messages to Workspace Client

The system SHALL allow Backend to send task messages to connected Workspace Client.

#### Scenario: Send task to workspace
- **WHEN** Backend receives user message for a session in workspace
- **THEN** system sends `{"type": "task", "session_id": "...", "message": "..."}` to Workspace Client via WebSocket

#### Scenario: Workspace not connected
- **WHEN** Backend attempts to send task but Workspace Client is not connected
- **THEN** system returns error to user "Workspace not connected"
- **AND** system logs connection status

### Requirement: Backend receives and routes stream messages

The system SHALL allow Backend to receive stream messages from Workspace Client and route to SSE.

#### Scenario: Stream message routed to SSE
- **WHEN** Workspace Client sends `{"type": "stream", "session_id": "...", ...}`
- **THEN** system publishes message to Redis channel `session:{session_id}`
- **AND** SSE clients subscribed to that channel receive the event

#### Scenario: Complete message ends SSE stream
- **WHEN** Workspace Client sends `{"type": "complete", "session_id": "..."}`
- **THEN** system publishes "done" event to Redis channel
- **AND** SSE stream ends

#### Scenario: Error message sent to SSE
- **WHEN** Workspace Client sends `{"type": "error", "session_id": "...", "error_message": "..."}`
- **THEN** system publishes "error" event to Redis channel
- **AND** SSE stream ends with error

### Requirement: Backend handles ask_user messages

The system SHALL allow Backend to handle user input requests from Workspace Client.

#### Scenario: Ask user message forwarded to SSE
- **WHEN** Workspace Client sends `{"type": "ask_user", "session_id": "...", "questions": [...]}`
- **THEN** system publishes "ask_user" event to Redis channel
- **AND** SSE client receives the questions

#### Scenario: User input forwarded to Workspace Client
- **WHEN** user submits answer via HTTP API
- **THEN** system sends `{"type": "user_input", "session_id": "...", "request_id": "...", "input": {...}}` to Workspace Client

### Requirement: Backend handles interrupt messages

The system SHALL allow Backend to send and receive interrupt messages.

#### Scenario: Forward interrupt to Workspace Client
- **WHEN** user requests interrupt via HTTP API
- **THEN** system sends `{"type": "interrupt", "session_id": "..."}` to Workspace Client

#### Scenario: Interrupted message forwarded to SSE
- **WHEN** Workspace Client sends `{"type": "interrupted", "session_id": "..."}`
- **THEN** system publishes "interrupted" event to Redis channel
- **AND** SSE stream ends

### Requirement: Backend provides agent configuration API

The system SHALL allow Workspace Client to fetch Agent configuration via internal HTTP API.

#### Scenario: Get agent config
- **WHEN** Workspace Client requests `GET /api/internal/agent-config/{workspace_id}/` with valid internal token
- **THEN** system returns `{"anthropic_api_key": "...", "anthropic_base_url": "..."}`
- **AND** API uses internal authentication (not user authentication)

#### Scenario: Unauthorized request rejected
- **WHEN** request to internal API lacks valid internal token
- **THEN** system returns HTTP 401 Unauthorized

### Requirement: WebSocket connection supports heartbeat

The system SHALL allow WebSocket connection to maintain liveness via ping/pong.

#### Scenario: Ping sent periodically
- **WHEN** Backend sends `{"type": "ping", "timestamp": ...}`
- **THEN** Workspace Client responds with `{"type": "pong", "timestamp": ...}`

#### Scenario: No pong received
- **WHEN** Workspace Client does not respond to ping within timeout
- **THEN** system closes WebSocket connection
- **AND** system logs connection timeout