# Workspace Client Capability

## Purpose

Enable Workspace containers to run a Python program that connects to Backend, receives tasks, and executes them using Claude Agent SDK.

## ADDED Requirements

### Requirement: Workspace Client connects to Backend on startup

The system SHALL allow Workspace Client to establish a WebSocket connection to Backend upon container startup.

#### Scenario: Successful connection
- **WHEN** Workspace Client starts with valid WORKSPACE_ID, ATOMSX_AUTH_TOKEN, and ATOMSX_BACKEND_WS_URL
- **THEN** system connects to WebSocket endpoint `/ws/workspace/{workspace_id}/`
- **AND** system sends Authorization header with Token
- **AND** system receives "connected" confirmation message

#### Scenario: Invalid token rejected
- **WHEN** Workspace Client connects with invalid or expired token
- **THEN** system closes WebSocket connection with code 4001
- **AND** Workspace Client logs authentication error

#### Scenario: Automatic reconnection
- **WHEN** WebSocket connection is lost
- **THEN** Workspace Client attempts to reconnect with exponential backoff
- **AND** Workspace Client logs reconnection attempts

### Requirement: Workspace Client processes task messages

The system SHALL allow Workspace Client to receive and process task messages from Backend.

#### Scenario: New task received
- **WHEN** Backend sends `{"type": "task", "session_id": "...", "message": "..."}`
- **THEN** Workspace Client creates a new Claude Agent session
- **AND** Workspace Client starts processing the message
- **AND** Workspace Client streams responses back to Backend

#### Scenario: Resume task received
- **WHEN** Backend sends `{"type": "resume", "session_id": "...", "claude_session_id": "...", "message": "..."}`
- **THEN** Workspace Client resumes the specified Claude Agent session
- **AND** Workspace Client continues processing with preserved context

### Requirement: Workspace Client supports multiple parallel sessions

The system SHALL allow Workspace Client to handle multiple sessions concurrently.

#### Scenario: Multiple sessions running
- **WHEN** Backend sends multiple task messages with different session_ids
- **THEN** Workspace Client creates independent Claude Agent sessions for each
- **AND** each session processes independently
- **AND** responses are correctly routed by session_id

#### Scenario: Session isolation
- **WHEN** one session encounters an error
- **THEN** other sessions continue unaffected
- **AND** error is reported only for the affected session

### Requirement: Workspace Client handles interrupt requests

The system SHALL allow Workspace Client to interrupt ongoing sessions.

#### Scenario: User requests interrupt
- **WHEN** Backend sends `{"type": "interrupt", "session_id": "..."}`
- **THEN** Workspace Client calls `agent.interrupt()` for that session
- **AND** Workspace Client sends `{"type": "interrupted", "session_id": "..."}` back to Backend
- **AND** partial content is preserved if available

### Requirement: Workspace Client handles user input requests

The system SHALL allow Workspace Client to request and receive user input during execution.

#### Scenario: Agent requests user input
- **WHEN** Claude Agent SDK calls AskUserQuestion tool
- **THEN** Workspace Client sends `{"type": "ask_user", "session_id": "...", "questions": [...]}` to Backend
- **AND** Workspace Client waits for response

#### Scenario: User provides input
- **WHEN** Backend sends `{"type": "user_input", "session_id": "...", "request_id": "...", "input": {...}}`
- **THEN** Workspace Client provides the input to the waiting Claude Agent session
- **AND** session continues execution

### Requirement: Workspace Client streams responses

The system SHALL allow Workspace Client to stream responses back to Backend.

#### Scenario: Text chunk streamed
- **WHEN** Claude Agent generates text content
- **THEN** Workspace Client sends `{"type": "stream", "session_id": "...", "chunk_type": "text", "content": "..."}` to Backend

#### Scenario: Tool use streamed
- **WHEN** Claude Agent invokes a tool
- **THEN** Workspace Client sends `{"type": "stream", "session_id": "...", "chunk_type": "tool_use", "tool_use_id": "...", "tool_name": "...", "tool_input": {...}}` to Backend

#### Scenario: Session completes
- **WHEN** Claude Agent session finishes
- **THEN** Workspace Client sends `{"type": "complete", "session_id": "...", "claude_session_id": "...", "usage": {...}}` to Backend

#### Scenario: Session errors
- **WHEN** Claude Agent session encounters an error
- **THEN** Workspace Client sends `{"type": "error", "session_id": "...", "error_message": "..."}` to Backend

### Requirement: Workspace Client runs as non-root user

The system SHALL ensure Workspace Client runs with uid=1000, gid=1000.

#### Scenario: User identity
- **WHEN** Workspace Client process is running
- **THEN** process runs as user "user" with uid=1000, gid=1000
- **AND** all files created are owned by user 1000