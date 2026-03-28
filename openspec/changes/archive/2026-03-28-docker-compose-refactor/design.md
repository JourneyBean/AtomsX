## Context

当前平台使用单一 `docker-compose.yml` 同时用于开发和生产，存在以下问题：

**端口暴露现状**：
- PostgreSQL: 5432 → 宿主机
- Redis: 6379 → 宿主机
- Backend: 8000 → 宿主机
- Frontend: 5173 → 宿主机
- Authentik: 9000/9443 → 宿主机
- Workspace preview: 30000-30100 → 宿主机
- Gateway: 80/443 → 宿主机

**硬编码问题**：
- `frontend/vite.config.ts`: proxy target = `http://localhost:8000`
- `.env.example`: `OIDC_REDIRECT_URI=http://localhost:8000/api/auth/callback`
- `gateway/nginx.conf`: `server_name localhost`
- `backend/config/settings.py`: `ALLOWED_HOSTS` 包含 localhost/127.0.0.1

**依赖配置现状**：
- backend/celery-worker 有完整的 `depends_on` + healthcheck
- authentik 有基础的 `depends_on`
- gateway 缺少对 backend/frontend 的健康检查依赖
- frontend 缺少对 backend 的依赖

## Goals / Non-Goals

**Goals:**
- 所有服务间通信通过 Docker service name 解析
- 仅 Gateway (80/443) 暴露到宿主机（生产环境）
- 开发环境保留调试端口暴露（但明确标注为 dev-only）
- 完善所有服务的启动依赖链
- 分离 dev/prod 配置文件

**Non-Goals:**
- Kubernetes 运行配置
- CI/CD 流程改动
- Workspace 内部网络模型调整
- 业务逻辑代码改动

## Decisions

### Decision 1: 网络模型 - 单一 Internal Network

**选择**: 所有服务使用 Docker Compose default network，不创建额外网络

**原因**:
- Docker Compose default network 自动提供 service discovery
- 简化配置，无需额外 network 定义
- 未来迁移 Kubernetes 时，Service discovery 机制类似

**替代方案**:
- 多网络隔离（backend_net、frontend_net）→ 过度复杂，MVP 不需要

### Decision 2: 端口暴露策略

**选择**:
- 生产环境：仅 Gateway 80/443 暴露，其他服务无宿主机端口映射
- 开发环境：Gateway 80/443 + Backend 8000（可选调试）+ Frontend 5173（可选调试）

**原因**:
- Gateway 作为统一入口，符合平台架构原则
- 开发调试需要直连 backend/frontend 的能力（可选）
- 数据库/Redis 永不暴露，通过 service name 访问

**替代方案**:
- 全部不暴露，强制通过 Gateway → 开发调试不便
- 全部暴露 → 安全风险

### Decision 3: 服务名替代 localhost

**选择**: 所有配置使用 Docker service name

| 原配置 | 新配置 |
|--------|--------|
| `localhost:8000` (frontend proxy) | `backend:8000` |
| `localhost:5173` (CORS) | `frontend:5173` |
| `localhost` (nginx server_name) | `_` (catch-all) 或实际域名 |
| `localhost:8000` (OIDC redirect) | 通过 Gateway 访问 `/api/auth/callback` |

**原因**:
- Docker service name 在容器内可正确解析
- localhost/127.0.0.1 在容器内指向容器自身，非宿主机

### Decision 4: 文件分离策略

**选择**:
- `docker-compose.yml` → 基础定义（共享配置）
- `docker-compose.dev.yml` → 开发覆盖（端口暴露、volume mount、debug 工具）
- `docker-compose.prod.yml` → 生产覆盖（端口最小化、生产 Dockerfile、资源限制）

**使用方式**:
```bash
# 开发
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# 生产
docker compose -f docker-compose.yml -f docker-compose.prod.yml up
```

**原因**:
- Docker Compose 支持 multi-file override
- 避免维护两个完整副本
- 共享部分集中管理

**替代方案**:
- 两个独立文件 → 配置重复，维护负担
- 单文件 + env 判断 → 条件逻辑复杂

### Decision 5: Dockerfile 分离

**选择**:
- `backend/Dockerfile` → 开发构建（uv sync 含 dev dependencies）
- `backend/Dockerfile.prod` → 生产构建（多阶段、最小化）
- `frontend/Dockerfile.dev` → 开发构建（保留 node_modules）
- `frontend/Dockerfile.prod` → 生产构建（nginx 静态托管）

**原因**:
- 开发需要调试工具、热更新支持
- 生产需要最小镜像、安全优化

## Risks / Trade-offs

### Risk 1: 开发者习惯变更

**风险**: 开发者需使用新的 compose 命令，可能遗忘覆盖文件

**缓解**:
- 在 README.md 添加明确指引
- 提供 `make dev` / `make prod` 简化命令
- 在 `.env.example` 添加注释说明

### Risk 2: OIDC 回调 URL 变更

**风险**: Authentik 配置需同步更新 redirect URI

**缓解**:
- 明确在 tasks.md 中记录 Authentik 配置更新步骤
- 保持通过 Gateway 访问的统一路径

### Risk 3: 现有容器数据丢失

**风险**: 网络变更可能导致现有容器无法通信

**缓解**:
- 使用 `docker compose down` + `up` 重建网络
- Volume 数据保留，仅重建容器

### Trade-off: 开发调试便利性 vs 安全

开发环境保留部分端口暴露，换取调试便利性。生产环境严格执行最小暴露原则。

## Migration Plan

### Phase 1: 文件准备（不破坏现有）
1. 创建 `docker-compose.dev.yml`、`docker-compose.prod.yml`
2. 创建 `backend/Dockerfile.prod`、`frontend/Dockerfile.prod`
3. 更新硬编码配置文件

### Phase 2: 开发环境切换
1. 开发者使用新命令启动
2. 验证服务间通信正常
3. 验证 OIDC 流程

### Phase 3: 生产环境部署
1. 使用生产 compose 启动
2. 验证仅 Gateway 端口暴露
3. 验证数据库/Redis 不可从宿主机访问

### Rollback Strategy
- 保留原 `docker-compose.yml` 作为 fallback
- 可随时恢复原启动方式

## Open Questions

1. **Authentik 是否需要开发环境**: 生产环境是否需要 OIDC？开发环境可用 mock auth？
   - *建议*: MVP 阶段开发环境保留 Authentik，后续可考虑简化

2. **Gateway 是否需要健康检查依赖**: backend/frontend 的健康如何影响 Gateway？
   - *建议*: Gateway 依赖 backend 健康检查，frontend 在开发环境可跳过