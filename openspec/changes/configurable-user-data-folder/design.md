## Context

当前 Workspace 容器创建时使用 Docker 默认的 volume 管理策略，用户数据存储位置不明确，无法支持：
- 数据备份与恢复
- 多节点迁移（未来演进）
- 存储容量规划

需要引入统一的用户数据存储策略，通过配置项控制存储根目录，并使用 UUID 二级分片结构组织数据。

**状态归属**：
- 数据目录路径由 Django 控制面配置
- 实际目录创建由 Celery 任务执行（调用 Docker API）
- 目录内容归属于具体 Workspace（UUID 对应）

## Goals / Non-Goals

**Goals:**
- 定义可配置的用户数据存储根目录
- 实现 UUID 二级分片目录结构
- 将用户数据目录挂载为容器家目录
- 支持开发环境与生产环境不同默认路径

**Non-Goals:**
- 数据备份策略（后续独立需求）
- 存储配额限制（后续独立需求）
- 跨节点数据同步（Kubernetes 阶段考虑）

## Decisions

### 1. 数据目录结构设计

**决定**: 采用 `{uuid[0]}/{uuid[1]}/{full_uuid}/` 二级分片结构

**理由**:
- UUID 首字符分片（16 个目录）避免根目录文件过多
- UUID 第二字符分片（256 个子目录）进一步分散
- 支持单机百万级 Workspace 而不出现目录性能问题
- 与 GitLab、Gitea 等项目的仓库存储策略一致

**替代方案**:
- 单层 `{full_uuid}/`：当用户量大时根目录文件过多，影响性能
- 用户 ID 分片：用户可能创建多个 Workspace，无法准确预估目录数

**结构示例**:
```
/var/opt/atomsx/
├── a/
│   ├── b/
│   │   └── ab123456-7890-.../
│   │       ├── workspace/    # 用户代码仓
│   │       └── history/      # 对话历史
│   ├── c/
│   │   └── ac789012-3456-.../
│   │       ├── workspace/
│   │       └── history/
```

### 2. 挂载策略

**决定**: 将用户数据目录 `{uuid[0]}/{uuid[1]}/{full_uuid}/` 直接挂载为容器内 `/home/user`

**理由**:
- 简化容器内路径管理，所有用户数据统一在家目录下
- `workspace/` 作为代码仓目录，`history/` 存储对话历史
- 符合用户对"家目录"的直觉认知

**替代方案**:
- 挂载为 `/data`：需要额外配置让 Agent 知道代码路径，增加复杂度
- 多个独立 volume：需要分别管理 workspace 和 history 的挂载，增加运维复杂度

### 3. 配置项设计

**决定**: 使用 Django settings 配置 `WORKSPACE_DATA_ROOT`，支持环境变量覆盖

**配置项**:
```python
# settings.py
WORKSPACE_DATA_ROOT = os.environ.get(
    'ATOMSX_WORKSPACE_DATA_ROOT',
    '/var/opt/atomsx/workspaces'
)
```

**理由**:
- 环境变量覆盖支持不同部署环境
- 统一默认值 `/var/opt/atomsx/workspaces`，开发环境通过 docker compose 挂载实现持久化
- 配置名 `ATOMSX_WORKSPACE_DATA_ROOT` 明确归属，避免与其他配置冲突

### 4. 目录创建时机与责任划分

**决定**: 目录创建由 Celery 任务在容器启动前执行

**流程**:
1. Django API 收到 Workspace 创建请求
2. 计算 UUID，生成数据目录路径
3. Celery 任务调用 `os.makedirs()` 创建目录结构
4. 调用 Docker API 创建容器，挂载数据目录

**责任划分**:
- Django：配置管理、路径计算、任务调度
- Celery：目录创建、Docker API 调用
- Docker：容器运行、volume 挂载

**替代方案**:
- Docker volume 自动创建：路径不可控，无法实现 UUID 分片结构
- Django 直接创建：阻塞 API 请求，影响响应速度

### 5. 目录权限设计

**决定**: 目录权限 `0755`，容器内用户 UID 映射

**理由**:
- 宿主机目录 `0755` 确保服务进程可访问
- 容器内用户 UID 可通过 Docker `--user` 参数映射
- 不引入复杂的 ACL 权限管理（MVP 阶段保持简单）

**临时简化**:
- MVP 阶段容器内使用 root 用户运行（简化开发）
- 后续演进为非 root 用户 + UID 映射

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| 数据目录创建失败导致 Workspace 创建失败 | 任务失败后更新 Workspace 状态为 error，记录错误信息 |
| 容器销毁后数据目录残留 | 明确设计：数据目录生命周期独立于容器，支持后续"数据恢复"场景 |
| 存储空间耗尽 | 后续增加配额限制能力（当前 Non-goal） |
| UUID 分片后数据迁移复杂 | 设计文档明确，后续迁移工具需支持分片结构 |

## Migration Plan

1. 配置项发布：更新 Django settings，无需数据库迁移
2. 存储目录准备：生产环境创建 `/var/opt/atomsx/` 并设置权限
3. 服务重启：Django + Celery 重启生效
4. 回滚：恢复旧配置项即可，已创建目录不影响系统运行

## Open Questions

- [ ] 是否需要支持用户自定义数据目录位置？（当前设计：平台统一管理）
- [ ] 对话历史目录结构是否需要进一步定义？（当前设计：由 Agent 会话能力决定）

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Django 控制面                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ settings.WORKSPACE_DATA_ROOT                         │    │
│  │ = /var/opt/atomsx/workspaces                         │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Celery Task: create_workspace_container             │    │
│  │  1. compute path: {root}/{uuid[0]}/{uuid[1]}/{uuid} │    │
│  │  2. mkdir -p path/workspace path/history            │    │
│  │  3. docker create --mount type=bind,src=path,dst=/home/user │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     宿主机存储                               │
│  /var/opt/atomsx/                                           │
│  ├── a/b/ab1234-.../                                        │
│  │   ├── workspace/    ← 挂载到容器 /home/user/workspace   │
│  │   └── history/      ← 挂载到容器 /home/user/history     │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Workspace 容器                             │
│  /home/user/                                                │
│  ├── workspace/    # 用户代码仓                              │
│  └── history/      # 对话历史                                │
└─────────────────────────────────────────────────────────────┘
```