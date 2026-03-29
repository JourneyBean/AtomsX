# Session History Capability

## Purpose

Enable storage and retrieval of conversation history for session recovery and continuity.

## ADDED Requirements

### Requirement: System saves session history on completion

The system SHALL save conversation history when a session completes.

#### Scenario: History saved on completion
- **WHEN** Claude Agent session completes successfully
- **THEN** Workspace Client saves history to `/home/user/history/sessions/{session_id}.json`
- **AND** file contains: session_id, claude_session_id, messages, usage, status="completed"

#### Scenario: History saved on interruption
- **WHEN** Claude Agent session is interrupted
- **THEN** Workspace Client saves history with status="interrupted"
- **AND** partial content is preserved

#### Scenario: History saved on error
- **WHEN** Claude Agent session encounters error
- **THEN** Workspace Client saves history with status="error"
- **AND** error message is recorded

### Requirement: History file contains complete conversation

The system SHALL store complete conversation data in history files.

#### Scenario: History file structure
- **WHEN** history file is saved
- **THEN** file contains:
  - session_id (Backend session ID)
  - claude_session_id (Claude Agent SDK session ID)
  - workspace_id
  - created_at (ISO 8601)
  - updated_at (ISO 8601)
  - status ("active" | "completed" | "interrupted" | "error")
  - messages (array of {role, content, timestamp})
  - usage ({total_input_tokens, total_output_tokens, total_cost_usd})

### Requirement: System maintains session index

The system SHALL maintain an index of all sessions for quick lookup.

#### Scenario: Index updated on session save
- **WHEN** session history is saved
- **THEN** Workspace Client updates `/home/user/history/index.json`
- **AND** index contains session summary: session_id, claude_session_id, created_at, updated_at, status, message_count, preview

#### Scenario: Index sorted by recency
- **WHEN** index is read
- **THEN** sessions are sorted by updated_at descending

### Requirement: System loads history on session resume

The system SHALL load previous history when resuming a session.

#### Scenario: History loaded for resume
- **WHEN** Workspace Client receives `{"type": "resume", "session_id": "...", "claude_session_id": "..."}`
- **THEN** Workspace Client loads history from `/home/user/history/sessions/{session_id}.json`
- **AND** Workspace Client restores Claude Agent session with `resume=claude_session_id`
- **AND** messages array is available for context

#### Scenario: History file not found
- **WHEN** Workspace Client attempts to load history for non-existent session_id
- **THEN** Workspace Client starts fresh session (no error)
- **AND** Workspace Client logs warning

### Requirement: Claude session ID is preserved

The system SHALL preserve Claude Agent SDK session ID for recovery.

#### Scenario: Claude session ID returned
- **WHEN** Claude Agent session is created
- **THEN** claude_session_id is captured from ResultMessage or init message
- **AND** claude_session_id is included in "complete" message to Backend
- **AND** claude_session_id is saved in history file

#### Scenario: Claude session ID used for resume
- **WHEN** resuming a session
- **THEN** claude_session_id from history is passed to Claude Agent SDK `resume` option
- **AND** Claude Agent continues with full context

### Requirement: History is scoped to Workspace

The system SHALL store history within the Workspace container.

#### Scenario: History location
- **WHEN** history is saved
- **THEN** file is written to `/home/user/history/sessions/` inside container

#### Scenario: History deleted with container
- **WHEN** Workspace container is deleted
- **THEN** history files are deleted with container
- **AND** history is not available after container deletion