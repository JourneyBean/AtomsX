## Context

当前 Workspace 容器通过 `create_workspace_container` Celery 任务创建，使用 `WORKSPACE_BASE_IMAGE` 镜像。镜像通过 `prebuild_workspace_images` 管理命令预构建，同名覆盖旧版本。

用户已有 workspace 使用旧镜像，无法自动升级。Recreate 功能允许用户主动触发重建，使用最新 prebuilt 镜像，同时保留 `data_dir_path`（workspace + history 数据）。

### 当前架构

```
┌─────────────────────────────────────────────────────────────────────┐
│  Workspace 生命周期                                                  │
│                                                                     │
│  Create:                                                            │
│  ┌──────────┐    create_workspace_container    ┌──────────┐         │
│  │ creating │────────────────────────────────▶│ running  │         │
│  └──────────┘                                   └──────────┘         │
│       │                                               │              │
│       ▼                                               ▼              │
│  ┌──────────┐                                   ┌──────────┐         │
│  │  error   │                                   │  stopped │         │
│  └──────────┘                                   └──────────┘         │
│       │                                               │              │
│       └──────────────────────────────────────────────▶│              │
│                                                       │              │
│                                                       ▼              │
│                                                 ┌──────────┐         │
│                                                 │ deleting │         │
│                                                 └──────────┘         │
│                                                     │                │
│                                                     ▼                │
│                                                 [deleted]            │
└─────────────────────────────────────────────────────────────────────┘
```

### 关键数据结构

```python
Workspace:
  id: UUID              # 保持不变
  container_id: str     # recreate 后更新为新容器 ID
  data_dir_path: str    # 保持不变，bind mount 源
  status: str           # 新增 recreating 状态
```

## Goals / Non-Goals

**Goals:**
- 用户可通过 UI 或 API 触发 workspace recreate
- Recreate 保持同一个 workspace UUID 和 data_dir_path
- 使用最新 prebuilt 镜像创建新容器
- 状态转换清晰可审计

**Non-Goals:**
- 批量 recreate 多个 workspace
- 显示镜像版本或变更信息
- recreate 确认对话框
- 处理 recreate 期间的 active session（强制断开，history 已保存）

## Decisions

### 1. 状态模型：新增 `recreating` 状态

**选择**: 新增 `recreating` 状态，而非复用 `creating`

**理由**:
- `creating` 只能从无状态进入（新建 workspace）
- `recreating` 明确表示"重建现有 workspace"，语义清晰
- Audit log 可区分 create 和 recreate 事件
- 前端 UI 可显示不同状态文案

**状态转换规则**:
```
running  → recreating → running | error
stopped  → recreating → running | error
error    → recreating → running | error
creating → recreating (不允许，create 未完成)
deleting → recreating (不允许，deleting 是终态)
```

### 2. Task 实现：独立 `recreate_workspace_container` 任务

**选择**: 新增独立 Celery task，而非组合 delete + create

**理由**:
- 单一 task 简化错误处理和状态管理
- 避免两阶段操作中间状态不一致
- 可复用 create/delete 的核心逻辑（Docker 操作）
- timeout 配置与 create 一致

**任务流程**:
```
1. 获取 workspace 和 data_dir_path
2. 如果有旧容器: 停止(timeout=10s) → 删除
3. 删除旧 WorkspaceToken
4. 创建新 WorkspaceToken
5. 创建新容器 (同 data_dir_path, 同 bind mounts)
6. 启动新容器
7. 更新 workspace: container_id, status=running
8. Audit log
```

### 3. API 设计：POST `/api/workspaces/:id/recreate/`

**选择**: 独立 recreate 端点，而非复用 POST create

**理由**:
- URL 语义明确: `recreate` 是动作动词
- 无需 request body，简化调用
- 返回 202 Accepted (异步任务)
- 可单独设置权限和 rate limit

**响应设计**:
```json
// 成功
{
  "id": "workspace-uuid",
  "status": "recreating"
}

// 错误场景
- 403: 非 owner
- 400: status=deleting (不允许 recreate)
- 409: status=recreating (避免重复触发)
```

### 4. Session 处理：强制断开

**选择**: Recreate 时强制断开 WebSocket 连接

**理由**:
- MVP 简化：不等待 session 结束
- History 数据已实时保存到 `/home/user/history`
- 用户可重新连接并恢复 session
- 避免 "温和等待" 的复杂性（timeout、通知机制）

**影响**: Frontend 会收到 WebSocket disconnect 事件，可显示提示 "Workspace recreate in progress"

### 5. stopped 状态处理：允许 recreate

**选择**: `stopped → recreating → running` 允许

**理由**:
- stopped 状态无容器，recreate = create
- 结果一致：用最新镜像启动容器
- 统一入口，简化用户理解
- 无需额外的 "start" 功能

## Risks / Trade-offs

### Risk: Recreate 中途失败导致 workspace 进入 error 状态

**Mitigation**:
- Task 有 retry 机制（max_retries=3）
- error 状态可再次触发 recreate
- data_dir_path 不变，数据不丢失

### Risk: 预构建镜像不存在

**Mitigation**:
- Task 检查镜像存在性，不存在时返回错误
- 错误信息提示运维运行 `prebuild_workspace_images --build`
- 与 create 流程一致

### Risk: 新镜像 agent.py 有 bug

**Mitigation**:
- 用户可再次 recreate（回滚需运维重建旧镜像）
- MVP 不承诺镜像版本管理

### Trade-off: 强制断开 session vs 温和等待

**选择强制断开**:
- MVP 简化实现
- History 数据已保存，可恢复
- 后续可演进为"温和等待 + 通知"

## Migration Plan

### 部署步骤

1. Backend: models.py 新增 `recreating` 状态，修改 `transition_status`
2. Backend: tasks.py 新增 `recreate_workspace_container` task
3. Backend: views.py 新增 `WorkspaceRecreateView`
4. Backend: urls.py 添加路由
5. Frontend: types/index.ts 添加 `recreating` 状态
6. Frontend: WorkspaceListView.vue 添加 Recreate 按钮

### 回滚策略

- 无数据迁移，回滚只需删除新增代码
- 无数据兼容性问题

## Open Questions

无待解决问题。设计已覆盖 MVP 需求。