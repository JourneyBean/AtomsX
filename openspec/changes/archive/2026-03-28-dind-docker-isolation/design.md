## Context

当前架构中，Django backend 和 Celery worker 通过挂载宿主 Docker socket (`/var/run/docker.sock`) 来管理 Workspace 容器。这种方式存在安全风险：控制面组件持有宿主级别权限，违反架构原则「Workspace 不应直接拥有宿主 Docker 或其他高权限基础设施控制能力」。

**当前状态**:
- `docker-compose.yml` 中 backend 和 celery-worker 都挂载 `/var/run/docker.sock`
- `docker_utils.py` 和 `tasks.py` 使用 `docker.from_env()` 连接 Docker
- `settings.py` 中 `DOCKER_HOST` 默认值为 `unix:///var/run/docker.sock`

**约束**:
- 必须通过环境变量或指定 socket 文件路径配置 dind
- 不允许使用宿主 Docker socket
- 需保持与现有 docker-py SDK 的兼容性
- MVP 阶段可简化，但需为 K8s 迁移预留路径

## Goals / Non-Goals

**Goals:**
- 实现完全隔离的 Docker 环境：Workspace 容器在 dind 内运行，与宿主 Docker 完全隔离
- 提供灵活的配置方式：支持环境变量 `DIND_SOCKET_PATH` 或直接指定 socket 路径
- 保持现有代码兼容：docker-py SDK 通过 `DOCKER_HOST` 环境变量连接 dind
- 确保健康检查：dind 服务启动后才能开始创建 Workspace

**Non-Goals:**
- 不实现 TLS 加密（MVP 简化，dind 与控制面在同一安全域）
- 不实现多 dind 实例负载均衡
- 不改变 Workspace 容器内部的运行内容
- 不涉及部署链路（Builder/Deployer）的 dind 改造

## Decisions

### 1. 使用官方 docker:dind 镜像，禁用 TLS

**决定**: 使用 `docker:dind` 宯方镜像，设置 `DOCKER_TLS_CERTDIR=""` 禁用 TLS。

**原因**:
- 官方镜像维护良好，版本与 docker-py SDK 兼容
- MVP 阶段 dind 与 backend/celery-worker 在同一 docker-compose 网络内，属于同一安全域
- 禁用 TLS 简化配置，减少证书管理复杂度
- 后期生产环境可启用 TLS 或迁移到 K8s

**替代方案**:
- 启用 TLS：增加证书生成和分发复杂度，MVP 阶段收益不大
- 使用第三方 dind 镜像：维护风险，不如官方镜像可靠

### 2. Socket 挂载路径策略

**决定**: 将 dind socket 挂载到 backend/celery-worker 的 `/var/run/dind/docker.sock`。

**原因**:
- 与宿主 socket 路径 `/var/run/docker.sock` 区分，避免混淆
- 明确标识这是 dind socket，不是宿主 socket
- 可通过环境变量灵活配置

**配置优先级**:
1. `DIND_SOCKET_PATH` 环境变量（如 `/var/run/dind/docker.sock`）
2. `DOCKER_HOST` 环境变量（如 `unix:///var/run/dind/docker.sock`）
3. 默认值：`unix:///var/run/dind/docker.sock`

### 3. dind 服务配置

**决定**: dind 服务配置如下：

```yaml
dind:
  image: docker:dind
  privileged: true  # dind 必须特权运行
  environment:
    DOCKER_TLS_CERTDIR: ""  # 禁用 TLS
  volumes:
    - dind_data:/var/lib/docker  # 持久化镜像、容器、卷
  command: ["--storage-driver=vfs"]  # MVP 简化存储
```

**原因**:
- `privileged: true` 是 dind 运行的必要条件
- `vfs` 存储驱动简单可靠，避免 overlay2 在某些环境的问题
- `dind_data` 卷持久化所有 dind 内的 Docker 数据

**演进路径**:
- 生产环境：考虑 `overlay2` 存储驱动，启用 TLS
- K8s 迁移：替换为 Kaniko 或其他无特权构建方案

### 4. Docker Client 初始化逻辑

**决定**: `docker_utils.py` 和 `tasks.py` 保持使用 `docker.from_env()`，通过环境变量控制连接目标。

**原因**:
- docker-py SDK 原生支持 `DOCKER_HOST` 环境变量
- 无需修改现有代码逻辑，只需修改环境变量配置
- 保持与 K8s 迁移后的兼容性（K8s 环境下 `DOCKER_HOST` 可指向不同服务）

**代码变更**:
```python
# docker_utils.py
class WorkspaceContainerManager:
    def __init__(self):
        # docker.from_env() 自动读取 DOCKER_HOST
        self.client = docker.from_env()
```

**settings.py 变更**:
```python
# Docker configuration
DIND_ENABLED = os.environ.get('DIND_ENABLED', 'true').lower() == 'true'
DIND_SOCKET_PATH = os.environ.get('DIND_SOCKET_PATH', '/var/run/dind/docker.sock')
DOCKER_HOST = os.environ.get('DOCKER_HOST', f'unix://{DIND_SOCKET_PATH}')
```

### 5. 健康检查依赖

**决定**: backend 和 celery-worker 等待 dind 健康检查通过后再启动。

**原因**:
- Docker client 连接需要 dind daemon 先就绪
- 避免 Workspace 创建任务因 dind 未就绪而失败

**实现**:
```yaml
backend:
  depends_on:
    dind:
      condition: service_healthy
celery-worker:
  depends_on:
    dind:
      condition: service_healthy
```

## Risks / Trade-offs

### Risk: dind 需要特权模式运行
- **影响**: dind 容器本身持有特权，可能成为攻击目标
- **缓解**: dind 容器内只有 Docker daemon，不运行用户代码；与 Workspace 容器完全隔离；控制面组件不持有特权，只连接 socket
- **长期**: K8s 环境下使用无特权构建方案（如 Kaniko）

### Risk: dind 数据卷丢失导致所有 Workspace 数据丢失
- **影响**: dind 内的镜像、容器、卷全部丢失
- **缓解**: 定期备份策略（生产环境）；MVP 阶段数据可重建
- **长期**: 数据持久化策略独立于 dind（如使用外部存储）

### Risk: dind daemon 故障导致 Workspace 无法管理
- **影响**: 无法创建/删除 Workspace，现有 Workspace 无法访问
- **缓解**: 健康检查和自动重启策略；监控 dind daemon 状态
- **长期**: 多 dind 实例或 K8s 高可用部署

### Trade-off: 禁用 TLS 简化配置但降低安全性
- **优势**: MVP 快速落地，配置简单
- **代价**: dind socket 在网络内可被访问
- **缓解**: dind 与控制面在同一安全域，外部流量无法直接访问
- **演进**: 生产环境启用 TLS

## Open Questions

1. **Workspace 预览端口访问**: dind 内的 Workspace 容器端口如何暴露给 OpenResty gateway？
   - 候选方案：dind 网络与宿主网络打通，或使用端口映射链（宿主 → dind → workspace）
   - 建议：MVP 使用端口映射链，生产环境考虑独立网络方案

2. **镜像构建位置**: workspace-base 镜像应该在哪里构建？
   - 当前：tasks.py 在 dind 内构建（从 workspace-template）
   - 建议：保持现状，镜像构建在 dind 内完成

## Migration Plan

**部署步骤**:
1. 添加 `dind` 服务到 docker-compose.yml
2. 创建 `dind_data` 卷用于持久化
3. 修改 backend/celery-worker 的 `depends_on` 等待 dind
4. 修改 backend/celery-worker 的 volumes：移除宿主 socket，挂载 dind socket
5. 更新 settings.py 的 Docker 配置默认值
6. 验证 Workspace 创建/删除流程正常

**回滚策略**:
- 恢复宿主 socket 挂载
- 恢复 settings.py 默认值
- 删除 dind 服务和相关卷
- 注意：dind 内的 Workspace 数据会丢失，需重新创建