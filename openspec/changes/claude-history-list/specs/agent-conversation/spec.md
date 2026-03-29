# Agent Conversation Delta Spec

## ADDED Requirements

### Requirement: User can resume session from history directory

The system SHALL allow logged-in users to resume a Claude session from Workspace Client history directory and continue the conversation.

#### Scenario: Resume from history with new message
- **WHEN** logged-in user sends POST to `/api/sessions/:id/resume/` with valid history_session_id and content
- **AND** Workspace Client is connected via WebSocket
- **THEN** system creates user message in Session.messages
- **AND** system sends `resume` message to Workspace Client via WebSocket with history_session_id and prompt
- **AND** Workspace Client loads history from `/home/user/history/{history_session_id}/`
- **AND** Workspace Client continues conversation with Claude using loaded context
- **AND** system streams response via SSE

#### Scenario: Resume from history while Workspace Client disconnected
- **WHEN** logged-in user attempts to resume from history
- **AND** Workspace Client is NOT connected
- **THEN** system returns HTTP 503 Service Unavailable
- **AND** response includes error message indicating Workspace Client is unavailable

### Requirement: Resume API accepts history_session_id parameter

The system SHALL accept history_session_id in the resume API to identify which historical session to continue.

#### Scenario: Resume API with history_session_id
- **WHEN** user calls POST `/api/sessions/:id/resume/` with body:
  ```json
  {
    "history_session_id": "20260328-1425-a3f2",
    "content": "继续修改这个功能"
  }
  ```
- **THEN** system validates history_session_id format (YYYYMMDD-HHMM-xxxx)
- **AND** system passes history_session_id to Workspace Client
- **AND** Workspace Client loads the corresponding session from history directory