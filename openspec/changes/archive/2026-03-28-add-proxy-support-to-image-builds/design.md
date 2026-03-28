## Context

当前项目包含 3 个 Dockerfile 和 1 个 docker-compose.yml，用于构建：
- **Backend**: Django 后端服务（Python 依赖）
- **Frontend**: Vue 前端开发服务（Node.js 依赖）
- **Workspace Template**: Workspace 基础镜像（包含 Node.js + Python + Agent Runtime）

所有镜像构建过程都涉及网络请求：
- `apt-get` 安装系统依赖
- `pip` 安装 Python 包
- `npm` 安装 Node.js 包
- `docker pull` 拉取基础镜像（隐式）

当前没有任何代理变量支持，导致在需要代理的企业网络环境中构建失败。

## Goals / Non-Goals

**Goals:**
- 所有 Dockerfile 支持通过构建参数传递代理变量
- docker-compose.yml 的 build 配置自动从环境变量传递代理
- 代理变量同时支持大写和小写形式（Docker 最佳实践）
- 不改变镜像最终运行时的网络配置

**Non-Goals:**
- 不涉及容器运行时的代理配置
- 不修改已发布应用的网络策略
- 不在 workspace-template 中默认设置代理环境变量到运行时

## Decisions

### 1. 使用 ARG 而非 ENV

**决定**: 使用 `ARG` 声明代理变量，在需要时通过临时 ENV 传递给命令。

**原因**:
- `ARG` 仅在构建阶段有效，不会持久化到镜像层
- 避免代理信息被意外固化到最终镜像中
- 符合 Docker 官方最佳实践

**替代方案**: 直接使用 `ENV` — 拒绝，因为会导致代理设置被固化到镜像，可能在无代理环境下引起问题。

### 2. 支持大小写双形式

**决定**: 同时声明 `HTTP_PROXY` 和 `http_proxy` 等大小写形式。

**原因**:
- 不同工具对代理变量大小写敏感度不同
- `apt-get` 使用大写，部分 `pip` 版本使用小写
- Docker BuildKit 推荐同时支持两种形式

### 3. docker-compose 使用环境变量自动传递

**决定**: 在 `build.args` 中使用 `${HTTP_PROXY:-}` 形式，从宿主机环境变量读取，无值时传递空字符串。

**原因**:
- 无需修改 docker-compose.yml 即可适配不同环境
- 开发环境无需设置代理时不会报错
- 生产部署时可通过环境变量注入代理

### 4. 仅在网络命令处传递代理

**决定**: 不全局设置 ENV，而是在 `apt-get`、`pip`、`npm` 命令前临时设置。

**原因**:
- 减少对构建过程的影响范围
- 部分命令可能需要绕过代理（如访问本地资源）
- 更精细的控制，避免意外副作用

## Risks / Trade-offs

**[代理变量泄露到镜像层]** → 使用 ARG 并在命令完成后立即清除临时 ENV，确保不持久化。

**[某些包源不支持代理]** → NO_PROXY 变量允许指定绕过代理的地址，用户可配置内部镜像源地址。

**[BuildKit 与 legacy builder 行为差异]** → 统一使用 BuildKit 格式（建议在 docker-compose.yml 中显式启用 BuildKit）。

**[workspace-template 运行时可能需要代理]** → 这是运行时配置问题，不在本次变更范围内，由运维单独处理。