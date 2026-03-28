## Why

在企业网络环境中，很多部署环境需要通过代理访问外部资源。当前所有镜像构建（Dockerfile 和 docker-compose.yml）都没有代理变量支持，导致在需要代理的网络环境中构建镜像时，`apt-get`、`pip`、`npm` 等包管理器无法正常下载依赖，构建失败。

这是 MVP 阶段必须解决的问题，确保平台能在各种网络环境下正常部署。

## What Changes

- 在所有 Dockerfile 中添加 `ARG` 声明支持 `HTTP_PROXY`、`HTTPS_PROXY`、`NO_PROXY` 及其小写版本
- 在 `apt-get`、`pip`、`npm` 等网络命令前传递代理环境变量
- 在 docker-compose.yml 的 `build` 配置中添加 `args` 传递代理变量
- 在 workspace-template 构建脚本中支持代理变量

## Capabilities

### New Capabilities

- `proxy-aware-build`: 镜像构建过程支持代理环境变量传递，确保在代理网络环境下能正常构建

### Modified Capabilities

无。这是纯基础设施层面的增强，不影响任何现有的功能规格。

## Impact

- **影响层级**: 构建层（Builder）
- **受影响文件**:
  - `backend/Dockerfile`
  - `frontend/Dockerfile.dev`
  - `workspace-template/Dockerfile`
  - `docker-compose.yml`
- **安全影响**: 无。代理变量仅用于构建阶段，不改变运行时安全边界
- **多租户影响**: 无。构建过程在平台控制面执行，不影响 Workspace 隔离

## Non-goals

- 不涉及运行时代理配置（容器运行时的代理设置由运维单独处理）
- 不修改已发布应用的网络配置
- 不在 Workspace 内部默认设置代理（Workspace 的代理由用户自行配置）