## Why

当前实现通过挂载宿主 Docker socket (`/var/run/docker.sock`) 来管理 Workspace 容器，这违反了架构原则：**控制面组件不应持有宿主级别的高权限基础设施控制能力**。如果 Django/Celery 进程被攻破，攻击者可直接控制宿主机上的所有容器，存在严重的容器逃逸风险。

Docker-in-Docker (dind) 提供了真正的隔离：控制面组件只能操作 dind 容器内的 Docker daemon，无法访问宿主机的真实 Docker 环境，符合安全边界清晰的原则。

## What Changes

- **BREAKING**: 移除宿主 Docker socket 挂载，替换为 Docker-in-Docker 服务
- 新增 `dind` 服务到 docker-compose.yml，作为隔离的 Docker daemon
- 新增环境变量配置：`DIND_HOST`（dind 服务地址）和 `DIND_SOCKET_PATH`（dind socket 文件路径）
- 更新 Django settings 默认 DOCKER_HOST 从宿主 socket 改为 dind socket
- 更新 `docker_utils.py` 和 `tasks.py` 的 Docker client 初始化逻辑
- Workspace 容器、镜像、网络、卷全部在 dind 环境内创建和管理
- 移除对宿主 Docker 的任何依赖

## Capabilities

### New Capabilities

- `dind-config`: Docker-in-Docker 配置管理能力，包括 dind socket 路径配置、健康检查、连接验证

### Modified Capabilities

- `workspace-management`: 容器生命周期管理需求变更——从使用宿主 Docker 改为使用 dind Docker daemon；Workspace 容器网络隔离要求不变，但创建环境从宿主改为 dind 内部

## Impact

**受影响代码**:
- `backend/apps/workspaces/docker_utils.py` — Docker client 初始化
- `backend/apps/workspaces/tasks.py` — Celery 任务中的 Docker 操作
- `backend/config/settings.py` — DOCKER_HOST 配置默认值
- `docker-compose.yml` — 新增 dind 服务，修改 backend/celery-worker 挂载

**受影响系统**:
- Backend 容器：不再挂载宿主 `/var/run/docker.sock`
- Celery Worker 容器：不再挂载宿主 `/var/run/docker.sock`
- Authentik Worker：保持不变（其 Docker socket 用途与 Workspace 管理无关）

**安全性提升**:
- 控制面组件只能操作 dind 内的容器，无法逃逸到宿主
- 即使 Django/Celery 被攻破，攻击者只能影响 dind 环境，无法控制宿主机真实容器
- 符合架构原则：Workspace 和控制面都不应持有宿主高权限

**非目标 (Non-goals)**:
- 不涉及 K8s 迁移路径修改
- 不改变 Workspace 容器内部的运行内容（Agent Runtime、Preview Server）
- 不改变多租户隔离模型
- 不涉及 Published App 或部署链路（本次仅针对开发态 Workspace）