## Context

当前 Workspace 创建流程中，Celery 任务 `create_workspace_container` 在执行时需要检查镜像是否存在，不存在时动态拉取基础镜像（如 `node:20-slim`）。这个过程可能耗时数分钟，导致用户等待 Workspace 进入 running 状态的时间过长。

镜像构建发生在 dind（Docker-in-Docker）环境中，与宿主机 Docker 仓库隔离。预构建机制需要将镜像提前构建并推送到 dind 仓库中，以便 Workspace 创建时直接使用。

### Workspace 镜像架构

Workspace 镜像基于 Ubuntu 24.04，包含：
- Python 3.12 + uv 包管理器
- Node.js 20.x
- workspace-client（Python 程序，运行 Claude Agent SDK）
- 用户配置（uid=1000, gid=1000）

镜像构建源码位于 `workspace-templates/ubuntu-24.04/`。

### 当前流程

```
用户创建 Workspace → Celery 任务启动 → 检查镜像 → (不存在) 拉取镜像 → 创建容器 → 返回
```

### 目标流程

```
运维预构建镜像 → 从 Dockerfile 构建 → 镜像保存到 dind 仓库
用户创建 Workspace → Celery 任务启动 → 检查镜像 → (存在) 直接创建容器 → 返回
```

## Goals / Non-Goals

**Goals:**

- 实现 Django 管理命令 `prebuild_workspace_images`，支持手动/自动化预构建
- 预构建镜像保存到 dind 或宿主机 Docker 仓库
- Celery 任务设置 5 分钟超时，防止长时间阻塞
- Workspace 创建优先使用预构建镜像，提升启动速度

**Non-Goals:**

- 不实现多版本镜像管理（MVP 简化）
- 不实现镜像自动更新/定期同步（后续演进）
- 不修改 Workspace 容器资源配置和安全策略
- 不实现 Builder 服务解耦（保持 Django 命令模式）

## Decisions

### Decision 1: Django 管理命令作为预构建入口

**选择**: 使用 Django 管理命令 `python manage.py prebuild_workspace_images`

**理由**:
- 与现有 Django 架构一致，易于维护
- 可通过 CI/CD 或手动触发
- 无需引入额外服务（Builder）降低 MVP复杂度

**备选方案**:
- Celery 定时任务自动构建 → 增加调度复杂度，MVP 不需要
- 独立 Builder 服务 → 过度设计，后续可演进

### Decision 2: 从 Dockerfile 构建镜像

**选择**: 从 `workspace-templates/ubuntu-24.04/Dockerfile` 构建镜像

**理由**:
- Workspace 镜像包含自定义组件（workspace-client、Python 依赖等）
- Dockerfile 构建确保镜像内容可控可审计
- 支持本地开发和 CI/CD 环境构建

**构建路径**:
```
workspace-templates/ubuntu-24.04/
├── Dockerfile              # 镜像定义
├── pyproject.toml          # Python 依赖
├── scripts/
│   └── entrypoint.sh       # 容器入口脚本
└── src/
    └── workspace_client/   # Python 包源码
```

**命令支持**:
```bash
# 从 Dockerfile 构建（推荐）
python manage.py prebuild_workspace_images --build

# 仅拉取基础镜像（开发调试用）
python manage.py prebuild_workspace_images --pull-base

# 强制重新构建
python manage.py prebuild_workspace_images --build --force
```

### Decision 3: 镜像存储位置

**选择**: 优先存储到 dind 仓库，开发环境支持宿主机 Docker 仓库

**理由**:
- 生产环境 Workspace 容器运行在 dind 中，镜像必须在 dind 仓库
- 开发环境可能直接使用宿主机 Docker（`DOCKER_HOST` 设置），需要兼容
- 使用 `docker.from_env()` 自动适配目标仓库

**实现**:
```python
# 根据DIND_ENABLED 或 DOCKER_HOST 决定目标仓库
client = docker.from_env()# 自动连接到正确的 Docker daemon
```

### Decision 3: Celery 超时配置（可配置）

**选择**: 使用环境变量和 Django settings 实现可配置超时

**配置方式**:
```python
# settings.py - 默认值
WORKSPACE_CREATION_SOFT_TIMEOUT = int(os.environ.get('WORKSPACE_CREATION_SOFT_TIMEOUT', 300))# 默认 5 分钟
WORKSPACE_CREATION_HARD_TIMEOUT = int(os.environ.get('WORKSPACE_CREATION_HARD_TIMEOUT', 360))# 默认 6 分钟
```

**任务级配置**:
```python
@shared_task(
    bind=True,
    soft_time_limit=settings.WORKSPACE_CREATION_SOFT_TIMEOUT,
    time_limit=settings.WORKSPACE_CREATION_HARD_TIMEOUT,
)
def create_workspace_container(self, workspace_id: str):...
```

**理由**:
- 环境变量优先，便于不同部署环境调整（开发/生产）
- Django settings 作为 fallback，保持一致性
- 超时值可在运维时根据网络/镜像大小灵活调整
- 软超时允许任务记录错误日志，硬超时防止资源泄漏

**备选方案**:
- 硬编码值 → 不灵活，无法适应不同环境
- 全局 Celery 超时 → 影响所有任务，不合适

### Decision 4: Workspace 创建任务镜像策略

**选择**: 优先使用预构建镜像，不存在时返回错误（不自动拉取）

**流程**:
```
1. 检查 settings.WORKSPACE_BASE_IMAGE 是否存在于 dind
2. 存在 → 直接使用
3. 不存在 → 标记 Workspace error 状态，提示运行 prebuild 命令
```

**理由**:
- Workspace 镜像包含 workspace-client，必须从 Dockerfile 构建
- 不再使用 node:20-slim 作为 fallback（缺少必要组件）
- 明确提示运维人员执行预构建，避免意外行为

**开发环境例外**:
- 开发时可通过 `--pull-base` 参数拉取基础镜像用于调试
- 基础镜像不会包含 workspace-client，仅用于 Dockerfile 开发测试

## Risks / Trade-offs

### Risk 1: 预构建镜像过期

**风险**: 预构建镜像可能包含过时的依赖或安全漏洞

**缓解**:
- 运维定期执行预构建命令更新镜像
- 后续演进可添加镜像版本管理

### Risk 2: dind 存储空间不足

**风险**: 多个镜像占用 dind 存储空间

**缓解**:
- MVP 仅预构建单一基础镜像，空间占用可控
- 监控 dind 存储使用率，设置清理策略

### Risk 3: 超时配置不当导致任务异常终止

**风险**: 用户设置过短的超时值可能导致正常任务被错误终止

**缓解**:
- 提供合理的默认值（软超时 300秒，硬超时 360秒）
- 文档中说明超时设置建议值和最小值限制
- 监控任务超时频率，异常高频时发出告警

## Migration Plan

### 部署步骤

1. 确保 `workspace-templates/ubuntu-24.04/` 目录存在且包含完整源码

2. 执行 Django 管理命令构建镜像
   ```bash
   # 在 Backend 容器中执行
   python manage.py prebuild_workspace_images --build

   # 或在宿主机执行（需要指定 Dockerfile 路径）
   docker build -t atomsx-workspace:latest workspace-templates/ubuntu-24.04/
   ```

3. 验证镜像已保存到 dind 仓库
   ```bash
   docker images | grep atomsx-workspace
   ```

4. 创建新 Workspace 测试启动速度

### 回滚策略

- 移除超时配置，恢复默认行为
- 如需使用旧版镜像，手动 pull 并 tag
- Workspace 创建任务会检查镜像是否存在，无镜像时返回明确错误