## Why

当前 Docker Compose 配置存在多个安全和架构问题：
1. **端口过度暴露**：PostgreSQL (5432)、Redis (6379)、Backend (8000)、Frontend (5173)、Authentik (9000/9443)、Workspace 端口范围 (30000-30100) 都暴露到宿主机，违反最小权限原则
2. **硬编码 localhost**：多处代码使用 localhost/127.0.0.1，在容器间通信时无法正确解析
3. **环境混淆**：开发和生产共用同一 docker-compose.yml，缺乏明确的环境分离
4. **启动顺序依赖不完整**：部分服务缺少 healthcheck condition 的 depends_on 配置

这些整改是 MVP 阶段基础设施安全加固的必要工作，为后续多租户隔离和生产部署奠定基础。

## What Changes

- **BREAKING**: 移除所有非必要端口暴露，仅保留 Gateway (80/443) 作为唯一外部入口
- 重构所有 localhost/127.0.0.1 硬编码，改为 Docker service name 解析
- 分离开发环境 (`docker-compose.dev.yml`) 与生产环境 (`docker-compose.prod.yml`)
- 完善 `depends_on` 配置，确保数据库、Redis 健康后才启动依赖服务
- 生产环境 Dockerfile 优化（多阶段构建、生产配置）
- 网络模型整改：所有服务间通信通过 Docker internal network

## Capabilities

### New Capabilities
- `docker-network-isolation`: Docker 网络隔离规范，定义服务间通信规则、端口暴露策略
- `docker-compose-env-separation`: 开发/生产环境分离规范，定义不同环境的 Docker Compose 配置差异

### Modified Capabilities
- 无现有 spec 需修改（specs 目录为空）

## Impact

- **代码改动**：frontend/vite.config.ts (proxy target)、backend/config/settings.py (ALLOWED_HOSTS)、gateway/nginx.conf (server_name)、.env.example
- **新增文件**：docker-compose.dev.yml、docker-compose.prod.yml、backend/Dockerfile.prod、frontend/Dockerfile.prod
- **删除/重构**：现有 docker-compose.yml 拆分为 dev/prod 版本
- **外部影响**：开发流程变更：开发者需使用 `docker compose -f docker-compose.dev.yml up`
- **安全加固**：数据库、Redis 不再暴露到宿主机，降低攻击面

## Non-goals

- 不涉及 Kubernetes 配置（保持单机 Docker Compose 模式）
- 不修改现有业务逻辑代码
- 不涉及 CI/CD 流程改动
- 不改变 Workspace 容器内部网络模型（本次仅整改平台控制面）