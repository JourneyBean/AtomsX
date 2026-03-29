# WebSocket Message Protocol

## Overview

The Workspace Client communicates with the Backend via WebSocket. This document describes the message format and types.

## Connection

### URL Format

```
ws://{ATOMSX_BACKEND_WS_URL}/ws/workspace/{workspace_id}/?token={ATOMSX_AUTH_TOKEN}
```

### Authentication

- Token is passed via query parameter `token`
- Token must match `WorkspaceToken` for the workspace
- Connection is rejected with code 4001 if token is invalid

## Message Format

All messages are JSON objects with a `type` field.

```json
{
  "type": "<message_type>",
  "session_id": "<uuid>",
  ...additional fields...
}
```

## Backend → Workspace Client Messages

### task

Start a new task in a new session.

```json
{
  "type": "task",
  "session_id": "uuid",
  "prompt": "User message content"
}
```

### resume

Resume a previous session from history.

```json
{
  "type": "resume",
  "session_id": "uuid",
  "history_session_id": "20260328-1425-a3f2",
  "prompt": "Optional message to send after resume"
}
```

### interrupt

Interrupt the current task.

```json
{
  "type": "interrupt",
  "session_id": "uuid",
  "reason": "user_requested"
}
```

### user_input

Provide user input in response to `ask_user`.

```json
{
  "type": "user_input",
  "session_id": "uuid",
  "request_id": "uuid",
  "input": {
    "selected_option": "option_1",
    "custom_input": "optional text"
  }
}
```

### ping

Keepalive ping (Backend can send, client responds with pong).

```json
{
  "type": "ping",
  "timestamp": "2026-03-28T10:00:00Z"
}
```

## Workspace Client → Backend Messages

### started

Acknowledge session started.

```json
{
  "type": "started",
  "session_id": "uuid",
  "history_session_id": "20260328-1425-a3f2",
  "claude_session_id": "claude-sdk-session-id"
}
```

### resumed

Acknowledge session resumed.

```json
{
  "type": "resumed",
  "session_id": "uuid"
}
```

### stream

Streaming content chunk.

```json
{
  "type": "stream",
  "session_id": "uuid",
  "content": "Text content from Claude"
}
```

Or for tool use:

```json
{
  "type": "stream",
  "session_id": "uuid",
  "tool_name": "Read",
  "tool_input": {"file_path": "/home/user/workspace/src/main.py"}
}
```

### ask_user

Request user input.

```json
{
  "type": "ask_user",
  "session_id": "uuid",
  "request_id": "uuid",
  "question": "Which approach would you like?",
  "options": [
    {"label": "Option A", "description": "Description of A"},
    {"label": "Option B", "description": "Description of B"}
  ]
}
```

### complete

Task completed successfully.

```json
{
  "type": "complete",
  "session_id": "uuid",
  "response": "Final response text"
}
```

### interrupted

Task was interrupted.

```json
{
  "type": "interrupted",
  "session_id": "uuid",
  "success": true
}
```

### error

Error occurred.

```json
{
  "type": "error",
  "session_id": "uuid",
  "error": "Error message"
}
```

### pong

Response to ping.

```json
{
  "type": "pong"
}
```

## SSE Integration

The Backend forwards messages to SSE clients via Redis pub/sub:

- Channel: `session:{session_id}`
- Events are forwarded to SSE stream

### SSE Event Types

| WebSocket Type | SSE Event | Description |
|----------------|-----------|-------------|
| stream | message | Streaming content |
| ask_user | ask_user | Request user input |
| complete | done | Task completed |
| interrupted | interrupted | Task interrupted |
| error | error | Error occurred |

## Error Handling

### Connection Errors

- Code 4001: Authentication failed
- Connection closed unexpectedly: Client should attempt reconnection

### Message Errors

- Invalid JSON: Logged, message ignored
- Unknown type: Logged, message ignored
- Missing required fields: Error response sent

## Reconnection

The Workspace Client implements automatic reconnection:

1. On disconnect, wait `reconnect_delay` seconds (default: 5)
2. Attempt to reconnect
3. If failed, double delay (max: 60 seconds)
4. Repeat until connected or shutdown