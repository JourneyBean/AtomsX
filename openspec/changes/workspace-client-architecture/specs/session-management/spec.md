# Session Management Capability

## Purpose

Enable users to create and manage AI conversation sessions bound to Workspaces.

## ADDED Requirements

### Requirement: User can create a Session in a Workspace

The system SHALL allow logged-in users to create a new conversation session in a Workspace they own.

#### Scenario: Successful Session creation
- **WHEN** logged-in user requests Session creation for a running Workspace they own
- **THEN** system creates Session record with: id (UUID), workspace, user, status="active", messages=[]
- **AND** system returns HTTP 201 Created with Session metadata

#### Scenario: Workspace not running
- **WHEN** user attempts to create Session in Workspace with status != "running"
- **THEN** system returns HTTP 400 Bad Request with error "Workspace is not running"

#### Scenario: Non-owner forbidden
- **WHEN** user attempts to create Session in Workspace owned by another user
- **THEN** system returns HTTP 403 Forbidden

### Requirement: User can send messages to a Session

The system SHALL allow logged-in users to send messages to their Sessions.

#### Scenario: Message sent to Workspace Client
- **WHEN** logged-in user sends message to active Session
- **THEN** system adds user message to Session.messages
- **AND** system sends task message to Workspace Client via WebSocket
- **AND** system returns SSE stream URL

#### Scenario: Workspace Client not connected
- **WHEN** user sends message but Workspace Client is not connected
- **THEN** system returns HTTP 503 Service Unavailable
- **AND** error message indicates "Workspace not connected"

#### Scenario: Session not active
- **WHEN** user sends message to Session with status != "active"
- **THEN** system returns HTTP 400 Bad Request

### Requirement: User can receive streaming responses

The system SHALL allow users to receive streaming responses via SSE.

#### Scenario: SSE stream connected
- **WHEN** user connects to SSE endpoint for a Session
- **THEN** system subscribes to Redis channel `session:{session_id}`
- **AND** system sends events as they arrive

#### Scenario: SSE events received
- **WHEN** Workspace Client sends stream messages
- **THEN** SSE client receives events: "text", "tool_use", "tool_result"
- **AND** SSE stream continues until "done" or "error" event

#### Scenario: SSE stream ends on done
- **WHEN** Workspace Client sends "complete" message
- **THEN** SSE client receives "done" event
- **AND** SSE stream closes

### Requirement: User can interrupt a Session

The system SHALL allow logged-in users to request interruption of ongoing Session activity.

#### Scenario: Interrupt requested
- **WHEN** logged-in user requests interrupt for their active Session
- **THEN** system sends interrupt message to Workspace Client
- **AND** system returns HTTP 202 Accepted

#### Scenario: Interrupt confirmed
- **WHEN** Workspace Client confirms interruption
- **THEN** SSE client receives "interrupted" event
- **AND** SSE stream closes

### Requirement: User can resume a Session

The system SHALL allow logged-in users to resume a previous Session.

#### Scenario: Resume with history
- **WHEN** logged-in user requests resume of their Session
- **AND** Session has claude_session_id saved
- **THEN** system sends resume message to Workspace Client with claude_session_id
- **AND** Workspace Client restores Claude Agent context

#### Scenario: Resume without history
- **WHEN** logged-in user requests resume of their Session
- **AND** Session has no claude_session_id (e.g., first message)
- **THEN** system starts new task instead of resume

### Requirement: User can list their Sessions

The system SHALL allow logged-in users to list their Sessions.

#### Scenario: List Sessions
- **WHEN** logged-in user requests Session list
- **THEN** system returns all Session records where user = current user
- **AND** each Session includes: id, workspace_id, status, created_at, message_count

### Requirement: User can view Session details

The system SHALL allow logged-in users to view Session details including message history.

#### Scenario: View own Session
- **WHEN** logged-in user requests details of Session they own
- **THEN** system returns Session record with messages array

#### Scenario: View other user's Session forbidden
- **WHEN** logged-in user requests details of Session owned by another user
- **THEN** system returns HTTP 403 Forbidden

### Requirement: User can delete a Session

The system SHALL allow logged-in users to delete their Sessions.

#### Scenario: Delete Session
- **WHEN** logged-in user requests deletion of Session they own
- **THEN** system deletes Session record
- **AND** system returns HTTP 204 No Content

#### Scenario: Active Session deletion
- **WHEN** user deletes Session with active streaming response
- **THEN** system terminates any ongoing WebSocket task
- **AND** system closes any open SSE streams