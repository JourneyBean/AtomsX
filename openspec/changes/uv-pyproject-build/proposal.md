## Why

当前后端使用传统的 pip + requirements.txt 方式管理依赖，存在以下问题：
- 依赖安装速度慢，影响开发迭代效率
- 缺乏虚拟环境自动隔离，依赖冲突风险高
- 缺乏锁定文件机制，构建可复现性差
- Docker 构建时 pip 安装耗时长，镜像构建效率低

uv 是新一代 Python 包管理器，可显著改善这些问题：
- 依赖安装速度提升 10-100 倍
- 自动管理虚拟环境，无需手动 venv
- 内置 uv.lock 锁定文件，确保构建可复现
- Docker 集成简单，官方提供 uv 静态镜像

**Why Now**: MVP 阶段需要快速迭代，高效的开发构建流程是基础设施必备。

## What Changes

- 引入 uv 作为 Python 包管理工具，替代 pip
- 完善 pyproject.toml 配置，适配 uv 最佳实践
- 添加 uv.lock 锁定文件，确保依赖版本可复现
- 重构 Dockerfile，使用 uv 构建后端镜像
- 更新开发文档，说明 uv 使用方式

## Capabilities

### New Capabilities

- `uv-build-system`: 定义后端 Python 构建系统，包括 uv 工具配置、pyproject.toml 规范、锁定文件管理、Docker 构建流程

### Modified Capabilities

无。本次变更仅涉及构建工具升级，不影响现有功能需求规格。

## Impact

**代码层**:
- `backend/pyproject.toml`: 完善配置，添加 uv 相关配置项
- `backend/Dockerfile`: 重构为 uv 构建流程
- 新增 `backend/uv.lock`: 依赖锁定文件

**开发流程**:
- 本地开发使用 `uv sync`、`uv run` 命令
- 新增依赖使用 `uv add <package>`
- 运行测试使用 `uv run pytest`

**Docker 构建**:
- 使用 `ghcr.io/astral-sh/uv:python3.12` 基础镜像或复制 uv 二进制
- 构建时间预计缩短 50%+

**依赖**:
- 引入 uv 工具 (无需 pip install，为独立二进制)
- 移除对 pip 的依赖

## Non-goals

- 不涉及生产部署策略变更
- 不涉及 CI/CD 配置（后续单独变更）
- 不涉及前端构建流程
- 不涉及 workspace 容器构建（workspace 有独立构建流程）

## Security & Isolation Impact

- 无安全边界变更
- 无多租户隔离影响
- uv.lock 确保依赖版本透明可审计

## User Value

- 开发者：更快的依赖安装、更稳定的环境隔离
- 平台：更短的镜像构建时间、更可复现的构建产物