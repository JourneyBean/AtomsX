## Context

### 当前架构

```
Browser ──SSE──▶ Backend ◀──WebSocket──▶ Workspace Client
                   │                          │
                   │                    Claude Agent SDK
                   │                          │
                   │                          ▼
                   └──────────────────▶ /home/user/history/
```

历史对话存储在 Workspace 容器内的 `/home/user/history/` 目录：

```
/home/user/history/
├── 20260328-1425-a3f2/              ← history_session_id
│   ├── session.json                 ← 元数据
│   │   {
│   │     "session_id": "uuid",
│   │     "history_session_id": "20260328-1425-a3f2",
│   │     "workspace_id": "uuid",
│   │     "created_at": "2026-03-28T14:25:00Z",
│   │     "last_activity": "2026-03-28T14:30:00Z"
│   │   }
│   └── messages.jsonl               ← 对话记录
│       {"timestamp": "...", "user": "帮我创建...", "assistant": "..."}
└── 20260329-0815-b4c1/
    ├── session.json
    └── messages.jsonl
```

### 核心约束

1. **历史数据隔离**：历史存储在容器内，Backend 无法直接访问文件系统
2. **必须通过 WebSocket**：Backend 需要向 Workspace Client 请求历史数据
3. **现有 resume API**：`POST /api/sessions/:id/resume/` 已支持从历史恢复

## Goals / Non-Goals

**Goals:**

- 实现 Backend → Workspace Client 的历史列表请求-响应机制
- 前端展示历史对话列表，支持恢复对话
- 检测 Workspace Client 连接状态，显示 offline 状态

**Non-Goals:**

- 不实现 Backend 缓存历史元数据
- 不实现历史对话分页
- 不实现删除历史对话

## Decisions

### 1. 历史列表获取方式

**决策：WebSocket Request-Response 模式**

```
Frontend              Backend                  Workspace Client
   │                     │                           │
   │ GET /history/       │                           │
   │────────────────────▶│                           │
   │                     │ ──WebSocket──────────────▶│
   │                     │ {"type":"get_history"}    │
   │                     │                           │
   │                     │                           │ 读取 history/
   │                     │                           │
   │                     │ {"type":"history_list",   │
   │                     │  "sessions":[...]}        │
   │                     │◀──────────────────────────│
   │                     │                           │
   │ 200 OK {sessions:[]}│                           │
   │◀────────────────────│                           │
```

**理由：**
- 复用现有 WebSocket 连接，无需额外端口
- Workspace Client 已有文件系统访问能力
- 最小改动原则

**备选方案：**

| 方案 | 优点 | 缺点 |
|------|------|------|
| A. WebSocket Request-Response | 复用连接，改动小 | 需要请求-响应匹配逻辑 |
| B. 容器内 HTTP API | REST 风格简单 | 需要额外端口和认证 |
| C. Backend 缓存元数据 | 前端直接查询 | 数据同步复杂，增加 DB 负担 |

### 2. 请求-响应匹配机制

**决策：使用 Redis 作为临时存储**

Backend 发送 `get_history` 消息后：
1. 生成唯一 `request_id`
2. 在 Redis 中设置 key `history_request:{request_id}`，过期时间 10 秒
3. Workspace Client 响应时包含 `request_id`
4. Backend 通过 `request_id` 匹配请求和响应

```
Backend:
  1. request_id = uuid4()
  2. Redis.set(f"history_request:{request_id}", "pending", ex=10)
  3. WebSocket.send({"type": "get_history", "request_id": request_id})
  4. 轮询 Redis 等待响应（最多 5 秒）

Workspace Client:
  1. 收到 {"type": "get_history", "request_id": "..."}
  2. 生成历史列表
  3. WebSocket.send({"type": "history_list", "request_id": "...", "sessions": [...]})

Backend Consumer:
  1. 收到 {"type": "history_list", "request_id": "...", "sessions": [...]}
  2. Redis.set(f"history_request:{request_id}", json.dumps(sessions), ex=10)
```

**理由：**
- 简单可靠，无需复杂的状态管理
- 超时自动清理
- 支持并发请求

### 3. 历史数据格式

**决策：返回最小必要信息**

```typescript
interface HistorySession {
  history_session_id: string    // 文件夹名
  first_message: string         // 截取 50 字符
  last_activity: string         // ISO timestamp
}
```

**理由：**
- 减少数据传输量
- 前端按 `last_activity` 排序
- 点击恢复时使用现有的 `resume` API

### 4. 离线状态检测

**决策：基于 WebSocket 连接状态 + 请求超时**

```
状态判断逻辑：
  1. 检查 channel_layer 是否有 workspace 的 group 成员
  2. 如果有成员，发送 get_history 请求
  3. 5 秒内无响应 → 返回 503，前端显示 offline
  4. 如果无成员 → 直接返回 503
```

**理由：**
- 复用 Django Channels 的 group 机制
- 无需额外的健康检查

## Risks / Trade-offs

### Risk 1: WebSocket 连接不稳定

**风险：** 网络波动导致请求丢失

**缓解：**
- 前端显示 offline 状态，引导用户刷新
- 请求超时设置 5 秒，快速失败

### Risk 2: 历史数据丢失

**风险：** 容器销毁时历史丢失

**缓解：**
- MVP 接受此限制
- 长期：支持历史导出到 Backend 或对象存储

### Risk 3: 并发请求

**风险：** 多个前端同时请求历史列表

**缓解：**
- 每个请求有独立的 `request_id`
- Redis key 包含 `request_id`，互不干扰

## Migration Plan

无需迁移，纯新增功能。

### 部署步骤

1. 部署 Backend 更新（views.py, consumers.py, urls.py）
2. 重新构建 Workspace 镜像（包含 workspace-client 更新）
3. 部署前端更新

### 回滚策略

- Backend API 返回 404 即可，前端显示"历史不可用"
- Workspace Client 消息类型向后兼容

## Open Questions

1. **是否需要限制历史数量？**
   - 当前设计：一次性加载全部
   - 后续优化：限制返回最近 50 条

2. **是否需要历史搜索功能？**
   - 当前设计：不支持
   - 后续优化：在 Workspace Client 实现全文搜索