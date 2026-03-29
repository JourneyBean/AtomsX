## Context

项目当前已有完整的生产构建配置：
- `docker-compose.prod.yml` - 生产环境 compose 配置
- `frontend/Dockerfile.prod` - Vue 前端多阶段构建（node → nginx）
- `backend/Dockerfile.prod` - Django 后端多阶段构建（builder → runtime）
- `gateway/Dockerfile` - OpenResty 网关镜像
- `workspace-templates/ubuntu-24.04/Dockerfile` - Workspace 运行时镜像

缺少的是：
1. 统一的构建入口脚本
2. 镜像导出能力（用于离线部署或分发）

## Goals / Non-Goals

**Goals:**

- 提供一键构建所有生产镜像的脚本
- 支持将镜像导出为 tar 文件，便于离线部署
- 构建产物可追溯（包含版本信息）
- 脚本可复用，支持增量构建和完整构建

**Non-Goals:**

- 不涉及镜像推送至 Registry（后续可扩展）
- 不涉及 CI/CD 流程自动化
- 不涉及 authentik 构建
- 不涉及 Kubernetes 配置

## Decisions

### 1. 脚本位置：`scripts/` 目录

**选择**: 将构建脚本放在项目根目录的 `scripts/` 文件夹下。

**原因**: 与项目现有结构一致，便于查找。脚本属于工具类，不是核心业务代码。

**替代方案**: 放在 `build/` 或 `.ci/` - 暂不采用，保持简单。

### 2. 导出目录：`exports/`

**选择**: 在项目根目录创建 `exports/` 存放导出的镜像 tar 文件。

**原因**: 清晰的输出位置，便于用户定位。添加 `.gitignore` 防止误提交大文件。

**替代方案**: 使用时间戳子目录（如 `exports/2026-03-29/`） - 可作为后续扩展。

### 3. 镜像命名规范

**选择**: 使用 `atomsx-<component>:prod` 作为镜像名称。

**原因**: 与现有 docker-compose.prod.yml 中隐含的命名一致，便于直接使用。

**镜像列表**:
| 镜像名称 | 构建源 |
|---------|--------|
| `atomsx-frontend:prod` | frontend/Dockerfile.prod |
| `atomsx-backend:prod` | backend/Dockerfile.prod |
| `atomsx-gateway:prod` | gateway/Dockerfile |
| `atomsx-workspace:prod` | workspace-templates/ubuntu-24.04/Dockerfile |

### 4. 构建模式：完整构建 vs 增量构建

**选择**: 默认完整构建，提供 `--incremental` 参数支持增量构建。

**原因**: 生产构建建议完整构建确保一致性，但增量构建可节省时间。

### 5. 导出格式：单独 tar 文件

**选择**: 每个镜像导出为单独的 tar 文件，而非合并为一个。

**原因**: 便于单独使用某个镜像，减少单文件过大问题。

**文件命名**: `atomsx-<component>-prod.tar`

## Risks / Trade-offs

### 风险：导出文件过大

- **Risk**: 四个镜像合计可能超过 1GB，占用磁盘空间
- **Mitigation**: 脚本完成后提示文件大小，建议用户及时清理

### 风险：构建时间较长

- **Risk**: 首次完整构建可能耗时 10-20 分钟
- **Mitigation**: 支持增量构建，显示构建进度

### 风险：代理配置

- **Risk**: 网络受限环境需配置代理
- **Mitigation**: 脚本支持传入 HTTP_PROXY 等环境变量

## Implementation Overview

### 脚本结构

```
scripts/
├── build-production.sh   # 主构建脚本
└── export-images.sh      # 导出脚本
```

### build-production.sh 流程

```
1. 解析参数（--incremental, --proxy 等）
2. 检查 Docker 是否可用
3. 按顺序构建各组件镜像
4. 输出构建结果摘要
```

### export-images.sh 流程

```
1. 创建 exports/ 目录
2. 遍历镜像列表
3. docker save 导出为 tar
4. 输出导出结果摘要（含文件大小）
```

## Migration Plan

无需迁移，新增脚本不影响现有流程。

部署方式：
1. 运行 `scripts/build-production.sh` 构建镜像
2. 运行 `scripts/export-images.sh` 导出镜像
3. 将 exports/ 目录打包传输至目标环境

## Open Questions

- 是否需要支持镜像压缩（gzip）？建议后续扩展
- 是否需要生成构建报告（JSON）？建议后续扩展