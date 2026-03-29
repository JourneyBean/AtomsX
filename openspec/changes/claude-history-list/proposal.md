## Why

用户在 Workspace 中与 Claude Agent 对话后，历史对话被保存在容器内的 `/home/user/history/` 目录中，但目前前端无法查看和恢复这些历史对话。这导致用户每次进入 Workspace 都只能开始新对话，无法继续之前的工作上下文。

此功能是 MVP 的核心体验之一：让用户能够无缝恢复之前的工作状态，保持工作的连续性。

## What Changes

- **新增历史对话列表 API**：Backend 提供 `GET /api/workspaces/:id/history/` 接口，通过 WebSocket 向 Workspace Client 请求历史列表
- **新增 WebSocket 消息类型**：Workspace Client 支持 `get_history` 消息，返回历史会话列表
- **前端历史对话侧边栏**：在 WorkspaceDetailView 左侧添加历史对话列表，按最后活动时间排序
- **恢复历史对话能力**：点击历史项可恢复该对话继续对话（使用现有 resume API）
- **离线状态显示**：当 Workspace Client 未连接或请求超时时，页面状态显示为 "offline"

## Capabilities

### New Capabilities

- `session-history-list`: 查看 Workspace Client 存储的 Claude 会话历史列表，支持恢复历史对话继续对话

### Modified Capabilities

- `agent-conversation`: 扩展会话能力，支持从历史恢复会话（基于现有 resume API 的前端集成）

## Impact

### 控制面 (Backend)

- `apps/workspaces/views.py`: 新增 `WorkspaceHistoryListView`
- `apps/workspaces/consumers.py`: 新增 `history_message` 消息处理
- `apps/workspaces/urls.py`: 新增 history 路由

### Workspace Runtime

- `workspace-templates/ubuntu-24.04/src/workspace_client/agent.py`: 新增 `get_history_list()` 方法
- `workspace-templates/ubuntu-24.04/src/workspace_client/main.py`: 处理 `get_history` 消息类型

### 前端

- `views/WorkspaceDetailView.vue`: 新增历史对话侧边栏
- `stores/session.ts`: 新增 `resumeSession()` 方法
- `types/index.ts`: 新增 `HistorySession` 类型

### API 变更

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/workspaces/:id/history/` | 获取历史对话列表 |

### WebSocket 消息变更

| Direction | Type | Description |
|-----------|------|-------------|
| Backend → Client | `get_history` | 请求历史列表 |
| Client → Backend | `history_list` | 返回历史列表数据 |

## Non-goals

- 不实现历史对话分页加载（后续优化）
- 不实现 Backend 缓存历史元数据（后续优化）
- 不实现删除历史对话功能
- 不实现历史对话搜索功能
- 不实现跨 Workspace 的历史同步

## Security Considerations

- 历史数据存储在 Workspace 容器内，容器销毁时历史随之销毁
- 历史列表 API 需验证用户对 Workspace 的所有权
- WebSocket 通信复用现有 Token 认证机制