## Why

生产部署需要一套完整的构建与导出流程。当前项目已有生产配置（docker-compose.prod.yml、各组件的 Dockerfile.prod），但缺少统一的生产构建脚本，无法一键打包所有组件并导出 Docker 镜像。这阻碍了快速交付与离线部署能力。

## What Changes

- 新增生产构建脚本 `scripts/build-production.sh`，支持一键构建所有生产组件
- 构建以下 Docker 镜像（按生产规格）：
  - `atomsx-frontend:prod` - Vue 前端生产镜像
  - `atomsx-backend:prod` - Django 后端生产镜像
  - `atomsx-gateway:prod` - OpenResty 网关镜像
  - `atomsx-workspace:prod` - Workspace 运行时镜像
- 导出镜像为 tar 文件至根目录 `exports/` 目录
- 新增 `scripts/export-images.sh` 导出脚本
- 支持增量构建与完整构建两种模式

## Capabilities

### New Capabilities

- `production-build`: 生产构建流程，包括 Docker 镜像构建、版本标记、镜像导出

### Modified Capabilities

<!-- 无现有规格变更 -->

## Impact

### 影响范围

- **新增文件**:
  - `scripts/build-production.sh` - 构建脚本
  - `scripts/export-images.sh` - 导出脚本
  - `exports/` - 导出目录（存放镜像 tar 文件）

### 不影响

- 不修改现有 Dockerfile 或 docker-compose 配置
- 不修改生产部署逻辑
- 不涉及 authentik（按用户要求排除）

### 安全影响

- 导出的镜像包含完整应用代码，需妥善保管
- 建议导出目录添加 `.gitignore` 排除

## Non-goals

- 不涉及 authentik 组件的构建
- 不涉及 Kubernetes 部署配置
- 不涉及 CI/CD 自动化（后续可扩展）
- 不涉及镜像推送到远程 Registry
- 不涉及运行时配置或环境变量管理