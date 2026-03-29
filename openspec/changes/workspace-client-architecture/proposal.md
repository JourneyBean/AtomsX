## Why

当前 Workspace 容器是一个"空白"的 Node.js 环境，Agent 逻辑在 Backend Celery Worker 中执行，无法直接操作用户文件。为了实现真正的隔离执行和文件操作能力，需要在 Workspace 容器内运行 Workspace Client 程序，主动连接 Backend，接收任务并调用 Claude Agent SDK 执行。

这是 MVP 的核心能力：让 AI 智能体能够真正在用户的开发环境中读取、修改文件，并运行命令。

## What Changes

### 新增组件

- **Workspace Client**：Python 程序，作为容器 entrypoint 启动，主动连接 Backend WebSocket
  - 支持多会话并行执行
  - 支持会话恢复（使用 Claude Agent SDK 的 resume 能力）
  - 支持用户中止操作
  - 支持请求用户输入（AskUserQuestion）
  - 会话历史保存到 `/home/user/history/`

- **Django Channels WebSocket Server**：处理 Workspace Client 连接
  - Token 认证机制
  - 消息路由到对应 Session
  - 与现有 SSE 流集成

- **WorkspaceToken Model**：认证密钥管理
  - 容器创建时生成
  - 容器关闭时清理

### 修改组件

- **Workspace 镜像**：`workspace-templates/ubuntu-24.04/`
  - 基于 Ubuntu 24.04
  - 包含 Python 3.12 + uv + Node.js
  - 打包 workspace-client 代码
  - 用户 uid/gid=1000

- **Workspace 创建任务**：生成 Token 并注入环境变量

- **Session 处理逻辑**：从 Celery 任务改为 WebSocket 消息转发

### 移除组件

- **原有 Agent Celery 任务**：`process_agent_message` 任务将被替换

## Capabilities

### New Capabilities

- `workspace-client`: Workspace Client 程序，在容器内运行，连接 Backend，执行 Agent 任务
- `workspace-websocket`: Backend WebSocket 服务，用于与 Workspace Client 双向通信
- `workspace-token`: Workspace 认证密钥管理，用于验证 Workspace Client 连接
- `session-history`: 会话历史存储与恢复，支持用户查看和继续之前的对话

### Modified Capabilities

- `workspace-management`: Workspace 创建流程修改，需要生成 Token 并注入环境变量
- `session-management`: Session 处理逻辑修改，从 Celery 任务改为 WebSocket 消息转发

## Impact

### 控制面 (Backend)

- 新增 Django Channels 配置和 WebSocket Consumer
- 新增 WorkspaceToken Model
- 新增内部 API：`/api/internal/agent-config/`（供 Workspace Client 获取 API Key）
- 修改 Workspace 创建任务
- 新增 Celery 任务：清理过期 Token
- 依赖：`channels`、`channels-redis`、`daphne`

### Workspace Runtime

- 新增 `workspace-templates/ubuntu-24.04/` 目录
- 新增 `workspace-client` Python 包
- 依赖：`claude-agent-sdk`、`websockets`、`httpx`、`pydantic`

### 网络与通信

- 新增 WebSocket 端点：`/ws/workspace/<workspace_id>/`
- 现有 SSE 流保持不变，继续用于 Browser → Backend 通信

### 安全边界

- Token 仅在容器创建时注入，不暴露在日志或 API 响应中
- API Key 通过内部 API 动态获取，不在环境变量中持久化
- 容器关闭时 Token 自动失效

### 部署影响

- 需要部署 Daphne 或 uvicorn 作为 ASGI 服务器
- 需要预构建新的 Workspace 镜像
- 现有 Workspace 需要重建才能使用新架构

## Non-goals

- 不实现文件变更通知（后续演进）
- 不实现 Workspace 间通信
- 不实现 Agent 任务队列持久化（崩溃恢复）
- 不支持自定义 Workspace 镜像（MVP 只提供 ubuntu-24.04）
- 不实现 Token 过期时间配置（MVP 永不过期，依赖容器生命周期）
- 不迁移现有 Session 数据到新架构