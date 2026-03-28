# API Documentation

## Authentication

All API endpoints require authentication via session cookie (after OIDC login).

### Endpoints

#### POST /api/auth/login
Initiate OIDC login flow.

**Response:** Redirect to OIDC provider

---

#### GET /api/auth/callback
Handle OIDC callback and complete authentication.

**Query Parameters:**
- `code` - Authorization code from provider
- `state` - CSRF state token

**Response:** Redirect to `/auth/callback` on success

---

#### POST /api/auth/logout
Logout the current user.

**Response:**
```json
{
  "redirect": "/login"
}
```

---

#### GET /api/auth/me
Get current user information.

**Response:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "display_name": "User Name",
  "oidc_sub": "provider-user-id",
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

## Workspaces

### GET /api/workspaces/
List workspaces owned by the current user.

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "My Workspace",
    "status": "running",
    "container_id": "container-hash",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

---

### POST /api/workspaces/
Create a new workspace.

**Request Body:**
```json
{
  "name": "New Workspace"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "name": "New Workspace",
  "status": "creating",
  ...
}
```

---

### GET /api/workspaces/:id
Get workspace details.

**Response:**
```json
{
  "id": "uuid",
  "name": "My Workspace",
  "status": "running",
  "container_id": "container-hash",
  "created_at": "...",
  "updated_at": "..."
}
```

---

### DELETE /api/workspaces/:id
Delete a workspace.

**Response:** `202 Accepted`

---

## Sessions

### POST /api/sessions?workspace_id=:id
Start a new session for a workspace.

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "workspace_id": "uuid",
  "user_id": "uuid",
  "messages": [],
  "status": "active",
  "created_at": "...",
  "updated_at": "..."
}
```

---

### GET /api/sessions/:id
Get session with message history.

**Response:**
```json
{
  "id": "uuid",
  "workspace_id": "uuid",
  "messages": [
    {
      "id": "msg-uuid",
      "role": "user",
      "content": "Hello!",
      "timestamp": "...",
      "status": "complete"
    },
    {
      "id": "msg-uuid",
      "role": "agent",
      "content": "Hi there!",
      "timestamp": "...",
      "status": "complete"
    }
  ],
  "status": "active",
  ...
}
```

---

### GET /api/sessions/:id/stream
SSE endpoint for streaming agent responses.

**Events:**
- `connected` - Connection established
- `content` - Response chunk
- `done` - Response complete
- `error` - Error occurred
- `interrupted` - Response interrupted

**Example Event:**
```
event: content
data: {"content": "Hello"}

event: done
data: {"message_id": "uuid"}
```

---

### POST /api/sessions/:id/messages
Send a message to the agent.

**Request Body:**
```json
{
  "content": "Create a hello world component"
}
```

**Response:**
```json
{
  "message_id": "uuid",
  "task_id": "celery-task-id",
  "stream_url": "/api/sessions/:id/stream"
}
```

---

### POST /api/sessions/:id/interrupt
Interrupt the current agent response.

**Request Body:**
```json
{
  "task_id": "celery-task-id"
}
```

**Response:**
```json
{
  "status": "interrupt_requested",
  "task_id": "celery-task-id"
}
```