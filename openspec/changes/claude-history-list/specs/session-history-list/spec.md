# Session History List Capability

## Purpose

Allow users to view and resume Claude conversation history stored in Workspace Client containers.

## Requirements

### Requirement: User can list session history

The system SHALL allow logged-in users to retrieve a list of Claude session histories for a Workspace they own.

#### Scenario: List history successfully
- **WHEN** logged-in user requests history list for a Workspace they own
- **AND** Workspace Client is connected via WebSocket
- **THEN** system sends `get_history` message to Workspace Client via WebSocket
- **AND** Workspace Client reads `/home/user/history/` directory
- **AND** system returns HTTP 200 with list of sessions sorted by last_activity descending
- **AND** each session includes: history_session_id, first_message (truncated to 50 chars), last_activity

#### Scenario: List history when Workspace Client offline
- **WHEN** logged-in user requests history list for a Workspace they own
- **AND** Workspace Client is NOT connected via WebSocket
- **THEN** system returns HTTP 503 Service Unavailable
- **AND** response includes error: "workspace client offline"

#### Scenario: List history request timeout
- **WHEN** logged-in user requests history list for a Workspace they own
- **AND** Workspace Client is connected but does not respond within 5 seconds
- **THEN** system returns HTTP 503 Service Unavailable
- **AND** response includes error: "workspace client timeout"

#### Scenario: List history for unauthorized Workspace
- **WHEN** logged-in user requests history list for a Workspace they do NOT own
- **THEN** system returns HTTP 403 Forbidden

### Requirement: History data format is standardized

The system SHALL return session history in a consistent format.

#### Scenario: History response format
- **WHEN** history list is retrieved successfully
- **THEN** each history session includes:
  - history_session_id: string (format: "YYYYMMDD-HHMM-xxxx")
  - first_message: string (truncated to 50 characters)
  - last_activity: string (ISO 8601 timestamp)

#### Scenario: First message extraction
- **WHEN** Workspace Client reads history
- **THEN** first_message is extracted from the first line of messages.jsonl
- **AND** first_message is the "user" field from that line
- **AND** first_message is truncated to 50 characters if longer

### Requirement: User can resume session from history

The system SHALL allow logged-in users to resume a historical Claude session and continue the conversation.

#### Scenario: Resume history session successfully
- **WHEN** logged-in user sends POST to `/api/sessions/:id/resume/` with history_session_id and content
- **AND** Workspace Client is connected
- **THEN** system sends `resume` message to Workspace Client via WebSocket
- **AND** Workspace Client loads session from `/home/user/history/{history_session_id}/`
- **AND** Workspace Client replays conversation history to Claude Agent SDK
- **AND** user can continue the conversation with the new message

#### Scenario: Resume non-existent history session
- **WHEN** logged-in user attempts to resume with invalid history_session_id
- **THEN** Workspace Client returns error
- **AND** system returns HTTP 404 Not Found

#### Scenario: Resume without content
- **WHEN** logged-in user sends POST to `/api/sessions/:id/resume/` with history_session_id but no content
- **THEN** system returns HTTP 400 Bad Request
- **AND** response includes error: "content is required"

### Requirement: Workspace Client handles history messages

The system SHALL have Workspace Client respond to WebSocket messages for history operations.

#### Scenario: Workspace Client handles get_history
- **WHEN** Workspace Client receives WebSocket message with type "get_history"
- **THEN** Workspace Client lists all directories in `/home/user/history/`
- **AND** for each directory, reads session.json for metadata
- **AND** for each directory, reads first line of messages.jsonl for first_message
- **AND** Workspace Client sends response with type "history_list"

#### Scenario: Workspace Client handles resume
- **WHEN** Workspace Client receives WebSocket message with type "resume" and history_session_id
- **THEN** Workspace Client loads session from `/home/user/history/{history_session_id}/`
- **AND** Workspace Client initializes Claude Agent SDK with conversation history
- **AND** Workspace Client sends new message to Claude

#### Scenario: History directory does not exist
- **WHEN** Workspace Client receives "get_history" message
- **AND** `/home/user/history/` directory does not exist or is empty
- **THEN** Workspace Client returns empty sessions list