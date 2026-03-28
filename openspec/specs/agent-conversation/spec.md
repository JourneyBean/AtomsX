# Agent Conversation Capability

## Purpose

Enable streaming conversation between users and AI Agent within a workspace session.

## Requirements

### Requirement: User can start a Session with Agent

The system SHALL allow logged-in users to start a new conversation Session bound to a Workspace they own.

#### Scenario: Start new Session
- **WHEN** logged-in user requests to start Session on a Workspace they own
- **THEN** system creates Session record in database with: id (UUID), workspace_id, user_id, messages=[], status="active", created_at
- **AND** system returns HTTP 201 Created with Session metadata
- **AND** system creates SSE channel for streaming responses

#### Scenario: Start Session on other user's Workspace forbidden
- **WHEN** logged-in user requests to start Session on Workspace owned by another user
- **THEN** system returns HTTP 403 Forbidden

### Requirement: User can send message to Agent

The system SHALL allow logged-in users to send messages to the Agent within an active Session, and receive streaming responses.

#### Scenario: Send message and receive streaming response
- **WHEN** logged-in user sends message to active Session they own
- **THEN** system appends message to Session.messages
- **AND** system triggers Agent processing via Celery task
- **AND** system returns SSE endpoint URL for streaming responses
- **AND** Agent generates response incrementally
- **AND** each response chunk is pushed to SSE channel
- **AND** frontend receives and displays response in real-time

#### Scenario: Message includes file modification request
- **WHEN** user message requests file modification (e.g., "create a new component")
- **THEN** Agent interprets the request
- **AND** Agent executes file modification in Workspace container (within allowed paths)
- **AND** Agent confirms modification in response stream
- **AND** system creates audit record for file modification

#### Scenario: Agent encounters error during processing
- **WHEN** Agent processing fails (e.g., API error, file operation error)
- **THEN** system pushes error message to SSE channel
- **AND** system updates Session status to "error" temporarily
- **AND** system logs error for debugging

### Requirement: User can interrupt Agent response

The system SHALL allow logged-in users to interrupt an ongoing Agent response stream.

#### Scenario: Interrupt streaming response
- **WHEN** user clicks "Stop" or sends interrupt signal during Agent response streaming
- **THEN** system stops the Celery task generating the response
- **AND** system closes the SSE channel
- **AND** system marks current message as "interrupted" in Session.messages
- **AND** Agent does not continue processing after interrupt

### Requirement: User can resume a Session

The system SHALL allow logged-in users to resume a previously active Session and continue the conversation.

#### Scenario: Resume existing Session
- **WHEN** logged-in user requests to resume a Session they previously participated in
- **THEN** system loads Session record from database
- **AND** system returns Session with full message history
- **AND** system establishes new SSE channel for streaming
- **AND** user can continue sending messages

#### Scenario: Resume Session not owned
- **WHEN** logged-in user requests to resume Session belonging to another user
- **THEN** system returns HTTP 403 Forbidden

### Requirement: Session message history is persisted

The system SHALL persist all messages in a Session for history and recovery.

#### Scenario: Message persistence
- **WHEN** message is sent or received in Session
- **THEN** system stores message in Session.messages array with: role (user/agent), content, timestamp, status (complete/interrupted/error)
- **AND** messages are persisted in database

#### Scenario: History retrieval
- **WHEN** user resumes or views Session
- **THEN** system returns all stored messages in chronological order

### Requirement: SSE connection handles disconnection gracefully

The system SHALL handle SSE connection disconnection without losing Session state.

#### Scenario: Client disconnects during streaming
- **WHEN** SSE client disconnects (network issue, page close)
- **THEN** system continues Agent processing (if not interrupted)
- **AND** system stores completed response in Session.messages
- **AND** user can reconnect to see completed response

#### Scenario: Client reconnects after disconnect
- **WHEN** client reconnects to SSE endpoint for same Session
- **THEN** system provides any completed messages since disconnect
- **AND** system continues streaming if Agent still processing

### Requirement: Agent conversation events are audited

The system SHALL record audit logs for key Agent conversation events.

#### Scenario: Message audit
- **WHEN** user sends message to Agent
- **THEN** system creates audit record with: timestamp, user_id, session_id, workspace_id, message_role="user", message_summary (truncated)

#### Scenario: Response audit
- **WHEN** Agent completes response
- **THEN** system creates audit record with: timestamp, user_id, session_id, workspace_id, message_role="agent", response_summary (truncated)

#### Scenario: File modification audit
- **WHEN** Agent modifies file in Workspace
- **THEN** system creates audit record with: timestamp, user_id, session_id, workspace_id, event_type="FILE_MODIFIED", file_path, operation (create/modify/delete)