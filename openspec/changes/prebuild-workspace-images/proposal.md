## Why

当前 Workspace 创建流程中，Celery 任务需要动态检查并拉取镜像，导致 Workspace 启动延迟。对于 MVP阶段，用户期望快速进入开发环境，镜像构建/拉取等待时间影响体验。通过预构建镜像机制，可以显著缩短 Workspace 创建时间，提升用户进入开发环境的速度。

## What Changes

- 添加 Django 管理命令 `prebuild_workspace_images`，实现镜像预构建能力
- 预构建的镜像保存到 dind/宿主机 Docker 仓库中
- Celery 任务超时时间改为可配置（默认软超时 5 分钟，硬超时 6 分钟），支持环境变量调整
- Workspace 创建任务优先使用预构建镜像，仅在不存在时 fallback 拉取

## Capabilities

### New Capabilities

- `image-prebuild`: 镜像预构建能力，通过 Django 管理命令预先构建并缓存 Workspace镜像到 Docker 仓库

### Modified Capabilities

- `workspace-management`: 修改 Workspace 创建流程的超时配置，并优化镜像获取策略（优先使用预构建镜像）

## Impact

- **控制面**: 新增 Django 管理命令（`backend/apps/workspaces/management/commands/prebuild_workspace_images.py`）
- **Celery 配置**: 在 `settings.py` 中添加可配置超时设置（`WORKSPACE_CREATION_SOFT_TIMEOUT`、`WORKSPACE_CREATION_HARD_TIMEOUT`），支持环境变量覆盖
- **Workspace 创建任务**: 修改 `backend/apps/workspaces/tasks.py`，优先使用预构建镜像，使用可配置超时值
- **运维**: 需要在部署流程中加入镜像预构建步骤；可通过环境变量调整超时时间以适应不同环境
- **安全边界**: 无变化，镜像仍运行在 dind隔离环境中，不涉及宿主机权限变更

## Non-goals

- 不实现镜像版本管理或多版本共存（MVP 简化）
- 不实现镜像自动更新/同步机制（后续演进）
- 不修改 Workspace 容器运行配置（资源限制、安全策略保持不变）
- 不实现镜像构建的 Builder 服务解耦（保持当前简单模式）