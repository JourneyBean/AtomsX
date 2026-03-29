## Why

当前 Workspace 创建后使用固定的 prebuilt 镜像，当 workspace-templates 代码更新并重新构建镜像后，现有 Workspace 无法使用最新镜像。用户需要 "升级" Workspace 到最新版本，同时保留原有的 workspace 数据和 history 记录。

MVP 阶段此功能可让用户快速获得最新的 Workspace Client 特性（如 agent.py 改进、bug fix 等），无需删除 workspace 再重建。

## What Changes

- 新增 `recreating` 状态，表示 Workspace 正在重建容器
- 新增 `POST /api/workspaces/:id/recreate/` API 端点
- 新增 `recreate_workspace_container()` Celery 任务
- 前端 WorkspaceListView 添加 Recreate 按钮
- 支持从 `running`、`stopped`、`error` 状态触发 recreate

## Capabilities

### New Capabilities

无新 capability。Recreate 是 workspace-management 能力的扩展。

### Modified Capabilities

- `workspace-management`: 添加 Workspace recreate 能力，允许用户使用最新镜像重建容器，同时保留数据

## Impact

- **控制面**: 新增 API 端点和 Celery 任务
- **状态模型**: Workspace.status 新增 `recreating` 状态，状态转换规则扩展
- **前端**: WorkspaceListView 添加 Recreate 按钮，状态显示支持 `recreating`
- **数据**: 无变化，data_dir_path 保持不变，workspace 和 history 数据完整保留
- **安全边界**: 无变化，新容器沿用同样的隔离策略和网络配置

## Non-goals

- 不实现批量 recreate（一次操作多个 workspace）
- 不实现 recreate 确认对话框
- 不显示镜像版本信息
- 不实现 recreate 回滚机制
- 不处理 recreate 过程中的 active session（WebSocket 连接会被强制断开，history 已保存）