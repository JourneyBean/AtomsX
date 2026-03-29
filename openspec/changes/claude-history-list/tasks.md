## 1. Workspace Client - History List Feature

- [x] 1.1 Add `get_history_list()` method to `SessionManager` class in `agent.py`
  - List all directories in `/home/user/history/`
  - Read `session.json` from each directory for metadata
  - Read first line of `messages.jsonl` to extract first user message
  - Return list sorted by `last_activity` descending
  - Handle empty or missing history directory gracefully

- [x] 1.2 Add `get_history` message handler in `main.py`
  - Handle incoming WebSocket message with type "get_history"
  - Call `SessionManager.get_history_list()`
  - Send response with type "history_list" containing sessions array

## 2. Backend - WebSocket Consumer

- [x] 2.1 Add `history_message()` handler to `WorkspaceConsumer` in `consumers.py`
  - Handle incoming WebSocket message with type "history_list"
  - Store response in Redis with key `history_request:{request_id}`
  - Include request_id matching from the request

- [x] 2.2 Add helper function `send_get_history_to_workspace()` in `consumers.py`
  - Send `get_history` message with unique `request_id`
  - Use Redis to store pending request
  - Return response or timeout after 5 seconds

## 3. Backend - History API Endpoint

- [x] 3.1 Create `WorkspaceHistoryListView` in `views.py`
  - GET `/api/workspaces/:id/history/`
  - Verify user owns the workspace
  - Check if Workspace Client is connected via channel_layer
  - If connected, send `get_history` via WebSocket and wait for response
  - If not connected or timeout, return HTTP 503 with error message
  - Return HTTP 200 with sessions list on success

- [x] 3.2 Add history URL route in `urls.py`
  - Add path for `history/` endpoint

## 4. Frontend - Types and Store

- [x] 4.1 Add `HistorySession` interface to `types/index.ts`
  - history_session_id: string
  - first_message: string
  - last_activity: string

- [x] 4.2 Add `resumeSession()` function to `stores/session.ts`
  - Call POST `/api/sessions/:id/resume/` with history_session_id and content
  - Handle SSE stream for resumed session response

## 5. Frontend - UI Components

- [x] 5.1 Add history sidebar to `WorkspaceDetailView.vue`
  - Add left sidebar panel with history list
  - Add "New" button at top to start new conversation
  - Display history items with first_message (truncated) and relative time
  - Sort by last_activity descending
  - Click on history item to resume that session

- [x] 5.2 Add offline status handling
  - Track when history API returns 503
  - Update workspace status display to show "offline"
  - Disable chat input when offline
  - Show error message in history sidebar when offline

- [x] 5.3 Add loading state for history list
  - Show loading indicator while fetching history
  - Handle error states gracefully

## 6. Testing

- [x] 6.1 Add unit tests for `SessionManager.get_history_list()` in Workspace Client
  - Test with empty history directory
  - Test with multiple history sessions
  - Test with malformed session.json

- [x] 6.2 Add API tests for `WorkspaceHistoryListView`
  - Test successful history retrieval
  - Test unauthorized workspace access
  - Test offline workspace client (503 response)

## 7. Documentation

- [x] 7.1 Update API documentation
  - Document GET `/api/workspaces/:id/history/` endpoint
  - Document WebSocket message types: `get_history`, `history_list`

## 8. History Messages Feature (Click to view, not resume)

- [x] 8.1 Add `get_history_messages()` method to `SessionManager` in `agent.py`
  - Read `messages.jsonl` from history directory
  - Return list of messages with role, content, timestamp

- [x] 8.2 Add `get_history_messages` message handler in `main.py`
  - Handle incoming WebSocket message with type "get_history_messages"
  - Call `SessionManager.get_history_messages()`
  - Send response with type "history_messages"

- [x] 8.3 Add `history_messages_message()` handler to `WorkspaceConsumer` in `consumers.py`
  - Handle incoming WebSocket message with type "history_messages"
  - Store response in Redis with key `history_messages_request:{request_id}`

- [x] 8.4 Add `send_get_history_messages_to_workspace()` helper in `consumers.py`
  - Send `get_history_messages` message with `request_id` and `history_session_id`

- [x] 8.5 Create `WorkspaceHistoryMessagesView` in `views.py`
  - GET `/api/workspaces/:id/history/:history_session_id/`
  - Fetch messages from Workspace Client (NOT calling Claude SDK)
  - Return HTTP 200 with messages list

- [x] 8.6 Add history messages URL route in `urls.py`
  - Add path for `history/:history_session_id/` endpoint

- [x] 8.7 Update frontend `resumeHistory()` in `WorkspaceDetailView.vue`
  - Change to only fetch and display messages (NOT call resumeSession)
  - Track `currentHistorySessionId` for sending new messages later
  - Only call Claude SDK when user sends a NEW message in resumed session

## 9. Auto-refresh Features

- [x] 9.1 Auto-refresh history list after sending message
  - Call `fetchHistoryList()` after `sendMessage()` or `resumeSession()` completes

- [x] 9.2 Auto-refresh file list after read/write tool calls
  - Detect tool_use events involving read/write operations in session store
  - Add `onFileOperation` callback system in session.ts
  - Add `refreshTrigger` prop to CodeView and FileTree
  - Trigger refresh when file-related tool calls are detected