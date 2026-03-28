## 1. Backend Dockerfile 代理支持

- [x] 1.1 在 `backend/Dockerfile` 顶部添加 ARG 声明：HTTP_PROXY、HTTPS_PROXY、NO_PROXY 及小写版本
- [x] 1.2 在 apt-get 命令前传递代理环境变量
- [x] 1.3 在 uv sync 命令前传递代理环境变量

## 2. Frontend Dockerfile 代理支持

- [x] 2.1 在 `frontend/Dockerfile.dev` 顶部添加 ARG 声明：HTTP_PROXY、HTTPS_PROXY、NO_PROXY 及小写版本
- [x] 2.2 在 npm install 命令前传递代理环境变量（使用 npm config set 方式）

## 3. Workspace Template Dockerfile 代理支持

- [x] 3.1 在 `workspace-template/Dockerfile` 顶部添加 ARG 声明：HTTP_PROXY、HTTPS_PROXY、NO_PROXY 及小写版本
- [x] 3.2 在 apt-get 命令前传递代理环境变量
- [x] 3.3 在 pip install 命令前传递代理环境变量
- [x] 3.4 在 npm install 命令前传递代理环境变量（使用 npm config set 方式）

## 4. docker-compose.yml 代理配置

- [x] 4.1 在 backend 服务 build.args 中添加代理变量传递（映射大写到小写：http_proxy: ${HTTP_PROXY:-}）
- [x] 4.2 在 celery-worker 服务 build.args 中添加代理变量传递（共享 backend Dockerfile）
- [x] 4.3 在 frontend 服务 build.args 中添加代理变量传递

## 5. 环境变量文档

- [x] 5.1 在 `.env.example` 中添加代理变量配置说明（使用大写形式）

## 6. 验证与测试

- [x] 6.1 代理环境下执行 `docker compose build`，代理变量正确传递
- [x] 6.2 验证构建完成的镜像不包含代理环境变量（docker inspect 检查通过）