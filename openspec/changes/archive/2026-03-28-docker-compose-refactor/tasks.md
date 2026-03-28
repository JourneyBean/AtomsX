## 1. Docker Compose 文件分离

- [x] 1.1 创建 `docker-compose.dev.yml` 开发环境覆盖文件，包含：端口暴露 (8000, 5173)、volume mount、debug 环境变量
- [x] 1.2 创建 `docker-compose.prod.yml` 生产环境覆盖文件，包含：仅 Gateway 端口、生产 Dockerfile 引用、资源限制、restart policy
- [x] 1.3 修改现有 `docker-compose.yml` 为基础定义，移除端口映射（dev/prod 覆盖处理），保留共享配置
- [x] 1.4 为 Gateway 添加对 backend 的健康检查依赖 (`depends_on` + `condition: service_healthy` 或 `condition: service_started` with healthcheck)
- [x] 1.5 为 frontend 添加对 backend 的依赖（开发环境）
- [x] 1.6 验证 dind 服务 healthcheck 配置正确，确保 backend/celery 依赖正确触发

## 2. 生产环境 Dockerfile 创建

- [x] 2.1 创建 `backend/Dockerfile.prod` 多阶段构建：builder stage (uv sync --frozen)、runtime stage (最小化，不含 pytest 等开发依赖)
- [x] 2.2 创建 `frontend/Dockerfile.prod` 多阶段构建：build stage (npm run build)、runtime stage (nginx 静态托管)
- [x] 2.3 配置 frontend nginx 生产配置：静态文件服务、反向代理到 backend、gzip 压缩
- [ ] 2.4 测试生产 Dockerfile 构建成功，镜像大小符合预期

## 3. 硬编码配置整改

- [x] 3.1 修改 `frontend/vite.config.ts`: proxy target 从 `http://localhost:8000` 改为 `http://backend:8000`
- [x] 3.2 修改 `gateway/nginx.conf`: `server_name localhost` 改为 `server_name _` (catch-all) 或支持环境变量注入
- [x] 3.3 修改 `.env.example`: 添加注释说明 localhost 仅用于本地开发，Docker 环境使用 service name
- [x] 3.4 修改 OIDC redirect URI 配置：确保通过 Gateway 路径访问，更新 Authentik 配置（如有必要）
- [x] 3.5 检查 `backend/config/settings.py` ALLOWED_HOSTS：确认包含 `backend` service name，添加说明注释
- [x] 3.6 全局搜索并整改其他 localhost/127.0.0.1 硬编码（排除测试代码和文档）

## 4. 端口暴露整改

- [x] 4.1 从 `docker-compose.yml` 移除 postgres 端口映射 `5432:5432`（仅 dev 可选暴露）
- [x] 4.2 从 `docker-compose.yml` 移除 redis 端口映射 `6379:6379`（仅 dev 可选暴露）
- [x] 4.3 从 `docker-compose.yml` 移除 backend 端口映射 `8000:8000`（移到 dev override）
- [x] 4.4 从 `docker-compose.yml` 移除 frontend 端口映射 `5173:5173`（移到 dev override）
- [x] 4.5 从 `docker-compose.yml` 移除 authentik 端口映射 `9000:9000` 和 `9443:9443`（生产环境不暴露）
- [x] 4.6 检查 workspace preview 端口范围 `30000-30100`，确认仅在 dind 内部使用，不映射到宿主机（生产）

## 5. 服务健康检查完善

- [x] 5.1 确认 postgres healthcheck 配置：`pg_isready -U atomsx`，interval 5s，retries 5
- [x] 5.2 确认 redis healthcheck 配置：`redis-cli ping`，interval 5s，retries 5
- [x] 5.3 为 backend 添加 healthcheck（可选生产）：HTTP `/api/health` 或 admin endpoint
- [x] 5.4 确认所有依赖数据库的服务使用 `condition: service_healthy`
- [x] 5.5 测试启动顺序：`docker compose up` 时 postgres/redis 先健康，再启动 backend/celery/authentik

## 6. 便捷启动命令

- [x] 6.1 创建或更新 `Makefile`，添加 `dev` 命令：`docker compose -f docker-compose.yml -f docker-compose.dev.yml up`
- [x] 6.2 添加 `prod` 命令：`docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
- [x] 6.3 添加 `down` 命令：停止所有服务
- [x] 6.4 添加 `build-prod` 命令：构建生产镜像
- [x] 6.5 添加 `logs` 命令：查看服务日志

## 7. 文档更新

- [x] 7.1 更新 `README.md`：添加开发环境启动说明（使用 `make dev` 或 compose 命令）
- [x] 7.2 更新 `README.md`：添加生产环境部署说明（使用 `make prod`）
- [x] 7.3 添加端口暴露说明表格：对比 dev vs prod 端口暴露差异
- [x] 7.4 添加网络模型说明：服务间通过 Docker service name 通信

## 8. 验收测试

- [ ] 8.1 测试开发环境启动：`make dev`，所有服务正常启动，端口 80/443/8000/5173 可访问
- [ ] 8.2 测试开发环境服务间通信：frontend proxy 到 backend 正常，backend 连接 postgres/redis 正常
- [ ] 8.3 测试生产环境启动：`make prod`，仅端口 80/443 暴露，数据库/Redis 不可从宿主机访问
- [ ] 8.4 测试 OIDC 流程：通过 Gateway 访问 Authentik，回调 URL 正常
- [ ] 8.5 测试 Gateway 路由：`/api/*` 路由到 backend，其他路由到 frontend
- [ ] 8.6 测试 Celery worker：任务队列正常连接 Redis，可执行异步任务
- [ ] 8.7 验证镜像大小：生产 Dockerfile 构建的镜像小于开发镜像

## 9. 环境变量整理（补充整改）

- [x] 9.1 开发环境使用宿主机 Docker socket，禁用 dind（在 docker-compose.dev.yml 中设置 `replicas: 0`）
- [x] 9.2 所有环境变量集中到 .env/.env.example，docker-compose.yml 使用 `${VAR:-default}` 引用
- [x] 9.3 归一化基础设施变量名：
  - PostgreSQL: POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD（所有服务共用）
  - Redis: REDIS_HOST, REDIS_PORT（所有服务共用）
  - Authentik 使用自身命名规范（AUTHENTIK_POSTGRESQL__*），但值引用同一组环境变量
- [x] 9.4 backend/celery 在开发环境直接挂载 `/var/run/docker.sock`，移除 dind 依赖