## Context

当前架构中，Agent 逻辑在 Backend Celery Worker 中执行，无法直接操作用户文件。Workspace 容器只运行 Node.js 环境，没有与 Backend 通信的能力。

需要设计一个新架构：Workspace Client 在容器内运行，主动连接 Backend，接收任务并调用 Claude Agent SDK 执行，实现真正的隔离执行。

### 当前状态

```
Browser ──SSE──▶ Backend ──Celery──▶ Agent (无文件访问能力)
                                   │
                                   ▼
                           Claude API
```

### 目标状态

```
Browser ──SSE──▶ Backend ◀──WebSocket──▶ Workspace Client
                   │                          │
                   │                    Claude Agent SDK
                   │                          │
                   │                          ▼
                   └──────────────────▶ 用户文件系统
```

## Goals / Non-Goals

**Goals:**

- 实现 Workspace Client Python 程序，支持多会话并行、会话恢复、用户中止、用户交互
- 实现 Django Channels WebSocket Server，处理 Workspace Client 连接
- 实现会话历史存储，支持恢复之前的对话
- 设计 Token 认证机制，保证连接安全
- 设计消息协议，覆盖所有交互场景

**Non-Goals:**

- 文件变更通知（后续演进）
- Agent 任务队列持久化（崩溃恢复）
- 自定义 Workspace 镜像支持
- Token 过期时间配置

## Decisions

### 1. WebSocket Server 选型

**决策：Django Channels**

**理由：**
- 与现有 Django 应用无缝集成
- 复用现有 Redis 作为 Channel Layer
- 复用现有认证、权限体系
- 学习成本较低

**备选方案：**
- aiohttp 单独服务：需要单独部署，与 Django 分离，认证复杂
- FastAPI 单独服务：同上，增加运维负担

### 2. Workspace Client 语言选型

**决策：Python**

**理由：**
- Claude Agent SDK 官方支持 Python
- 与 Backend (Django/Python) 技术栈一致，便于代码复用
- Python 3.12 + asyncio 成熟稳定

**备选方案：**
- Go：无官方 Claude Agent SDK 支持
- Node.js：有 SDK，但与 Backend 技术栈不一致

### 3. 虚拟环境管理

**决策：uv**

**理由：**
- 快速：比 pip 快 10-100 倍
- 现代：原生支持 pyproject.toml
- 锁定：自动生成 uv.lock 确保可重复构建

### 4. 会话历史存储位置

**决策：容器内 `/home/user/history/`**

**理由：**
- 历史与会话绑定，容器销毁时历史也销毁
- 无需 Backend 持久化，简化架构
- Claude Agent SDK 的 session_id 已足够用于恢复

**备选方案：**
- Backend 数据库：增加 DB 负担，需要额外清理逻辑
- Redis：不适合存储大量对话历史

### 5. API Key 获取方式

**决策：通过内部 HTTP API 动态获取**

**理由：**
- 不暴露在环境变量中，更安全
- 支持动态轮换
- 可以根据 workspace/user 动态配置

### 6. 消息协议设计

**决策：JSON over WebSocket**

消息类型：

```
Backend → Workspace Client:
  - task: 启动新会话任务
  - resume: 恢复已有会话
  - interrupt: 中止当前会话
  - user_input: 用户输入（响应 ask_user 请求）
  - ping: 心跳检测

Workspace Client → Backend:
  - stream: 流式输出（文本/工具调用）
  - ask_user: 请求用户输入
  - complete: 会话完成
  - error: 错误报告
  - interrupted: 会话已被中止
  - pong: 心跳响应
```

**理由：**
- JSON 易于调试和扩展
- 每条消息包含 session_id，支持多会话并行
- 与现有 SSE 流格式一致

### 7. Token 生命周期

**决策：容器创建时生成，容器关闭时删除**

**理由：**
- MVP 简化：无需过期时间配置
- 安全：Token 与容器生命周期绑定
- 实现简单：Celery 任务检测容器状态

**长期演进：**
- 支持 Token 过期时间
- 支持 Token 手动撤销
- 支持 Token 权限范围

## Architecture

### 组件交互

```
┌─────────────────────────────────────────────────────────────────────┐
│                              Browser                                 │
│                                                                     │
│   ┌─────────────────┐    SSE    ┌─────────────────┐               │
│   │   Session View  │◀──────────│   SSE Stream    │               │
│   └─────────────────┘           └─────────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
                                        ▲
                                        │ HTTP/SSE
                                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                            Backend (Django)                          │
│                                                                     │
│   ┌─────────────┐  ┌──────────────────┐  ┌───────────────────────┐ │
│   │   Views     │  │    Consumers     │  │    WorkspaceToken     │ │
│   │   (REST)    │  │   (WebSocket)    │  │       (Model)         │ │
│   └─────────────┘  └──────────────────┘  └───────────────────────┘ │
│          │                  │                        │             │
│          ▼                  ▼                        ▼             │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │                         Redis                                │  │
│   │   - Pub/Sub: session:{id} → SSE                             │  │
│   │   - Channel Layer: workspace:{id} → WebSocket               │  │
│   └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                           │
                                           │ WebSocket
                                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Workspace Container                            │
│                                                                     │
│   /home/user/workspace-client/     /home/user/                      │
│   ├── pyproject.toml               ├── workspace/   (bind mount)   │
│   ├── .venv/                       └── history/                     │
│   └── src/workspace_client/                                         │
│       ├── main.py                                                   │
│       ├── client.py                                                 │
│       ├── agent.py                                                  │
│       └── config.py                                                 │
│                                                                     │
│   User: user (uid=1000, gid=1000)                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 数据流

```
用户发送消息:
Browser ──POST──▶ Backend Views ──Redis──▶ WebSocket Consumer
                                               │
                                               ▼
                              Workspace Client ──Claude Agent──▶ 文件操作
                                       │
                                       ▼
                              Backend Consumer ──Redis──▶ SSE Stream
                                                               │
                                                               ▼
                                                          Browser
```

### 状态归属

| 状态 | 拥有者 | 存储位置 | 生命周期 |
|------|--------|----------|----------|
| Workspace | Backend | PostgreSQL | 用户创建 → 用户删除 |
| WorkspaceToken | Backend | PostgreSQL | 容器创建 → 容器关闭 |
| Session | Backend | PostgreSQL | 用户创建 → 用户删除 |
| Claude Session | Workspace Client | 容器内存 | 任务开始 → 任务完成 |
| Session History | Workspace Client | 容器文件系统 | 会话创建 → 容器销毁 |
| 用户文件 | Workspace Container | Bind Mount | 用户创建 → 用户删除 |

## Risks / Trade-offs

### Risk 1: WebSocket 连接断开

**风险：** 网络不稳定导致 WebSocket 断开，Agent 任务中断

**缓解：**
- Workspace Client 实现自动重连
- 支持 `resume` 恢复会话
- 记录 `claude_session_id` 用于恢复

### Risk 2: 容器资源不足

**风险：** 多会话并行时 CPU/内存不足

**缓解：**
- 容器资源限制（已有：512MB 内存，50% CPU）
- 限制最大并行会话数（MVP：不限制，监控后决定）
- 长期：支持会话队列

### Risk 3: Token 泄露

**风险：** Token 被恶意获取，伪装成 Workspace Client

**缓解：**
- Token 只在容器创建时注入，不暴露在日志
- Token 与 Workspace 绑定，无法跨 Workspace 使用
- 容器关闭时立即删除 Token

### Risk 4: 会话历史丢失

**风险：** 容器销毁时会话历史丢失

**缓解：**
- MVP 接受此限制
- 长期：支持历史导出到 Backend 或对象存储

### Trade-off: 简单性 vs 可靠性

**选择：** MVP 优先简单性
- 不实现消息持久化
- 不实现任务重试
- 不实现历史备份

**长期演进：** 逐步增加可靠性机制

## Migration Plan

### Phase 1: 基础设施准备

1. 添加 Django Channels 配置
2. 创建 WorkspaceToken Model
3. 实现 WebSocket Consumer（基础版）

### Phase 2: Workspace Client 开发

1. 创建 `workspace-templates/ubuntu-24.04/` 目录
2. 实现 `workspace-client` Python 包
3. 编写 Dockerfile 和 entrypoint

### Phase 3: 集成与测试

1. 修改 Workspace 创建任务
2. 实现 Token 清理 Celery 任务
3. 端到端测试

### Phase 4: 切换

1. 预构建新镜像
2. 新 Workspace 使用新架构
3. 旧 Workspace 保持原架构（不迁移）

### Rollback Strategy

- 保留原有 Celery Agent 任务代码
- 通过环境变量切换新旧架构
- 新架构失败时，回退到旧镜像

## Open Questions

1. **最大并行会话数？**
   - MVP：不限制，监控后决定
   - 需要根据资源使用情况调整

2. **会话历史是否需要导出？**
   - MVP：不导出，容器销毁时丢失
   - 后续：支持导出到 Backend 或对象存储

3. **是否支持自定义镜像？**
   - MVP：只提供 ubuntu-24.04
   - 后续：支持用户自定义 Dockerfile