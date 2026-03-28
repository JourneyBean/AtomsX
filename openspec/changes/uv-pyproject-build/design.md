## Context

当前后端构建系统使用 pip + pyproject.toml (setuptools)，存在以下问题：
- pip 安装依赖速度慢（Docker 构建中约 30-60 秒）
- 缺乏虚拟环境自动管理，需手动维护
- 缺乏锁定文件，构建可复现性差
- Docker 镜像体积较大（包含 pip 缓存）

uv 是 Astral 公司开发的新一代 Python 包管理器：
- Rust 实现，安装速度比 pip 快 10-100 倍
- 自动管理虚拟环境
- 内置锁定文件 (uv.lock)
- 支持直接从 pyproject.toml 读取依赖
- 官方提供 Docker 集成方案

## Goals / Non-Goals

**Goals:**
- 使用 uv 替代 pip 进行依赖管理
- 完善 pyproject.toml 配置，适配 uv 最佳实践
- 生成 uv.lock 锁定文件，确保构建可复现
- 重构 Dockerfile，使用 uv 构建镜像
- 缩短 Docker 构建时间 50%+

**Non-Goals:**
- 不涉及 CI/CD 配置（后续单独变更）
- 不涉及生产部署策略变更
- 不涉及前端构建流程
- 不涉及 workspace 容器构建

## Decisions

### Decision 1: 使用 uv 作为包管理器

**选择**: uv
**替代方案**:
- pip + pip-tools: 传统方案，生成 requirements.txt 锁定文件，但速度慢
- poetry: 功能完整但速度不如 uv，且需额外配置
- pdm: 类似 poetry，社区较小

**理由**:
- uv 安装速度最快（实测 Django + DRF 依赖约 2 秒完成）
- 自动管理虚拟环境，无需手动 venv
- uv.lock 格式清晰，兼容性好
- Astral 团队活跃（也是 ruff 开发者），维护质量高
- Docker 集成简单，官方提供最佳实践

### Decision 2: Dockerfile 构建策略

**选择**: 复制 uv 二进制到标准 Python 镜像
**替代方案**:
- 使用 `ghcr.io/astral-sh/uv:python3.12` 官方镜像
- 使用多阶段构建

**理由**:
- 标准镜像更可控，方便后续添加其他依赖
- 复制 uv 二进制简单，不增加镜像体积（约 10MB）
- 官方镜像可能版本滞后，标准镜像更新灵活

**构建流程**:
```
1. FROM python:3.12-slim
2. COPY uv binary from official image
3. COPY pyproject.toml + uv.lock
4. uv sync --frozen --no-dev (生产构建不含 dev 依赖)
5. COPY application code
```

### Decision 3: pyproject.toml 配置结构

**选择**: 保留 setuptools 后端，使用 uv 管理依赖
**替代方案**:
- hatch: uv 原生支持，但 hatch build 不够成熟
- 完全移除 build-system: 无法 pip install

**理由**:
- setuptools 仍是主流构建后端，wheel 发布兼容性好
- uv 可以直接读取 [project.dependencies]，无需修改
- 保持 pip install 兼容性，方便其他开发者

**新增配置**:
```toml
[tool.uv]
dev-dependencies = [...]  # uv 管理开发依赖

[tool.ruff]  # 可选：后续添加 lint 配置
```

### Decision 4: uv.lock 管理

**选择**: 将 uv.lock 纳入 Git 版本控制
**理由**:
- 确保所有开发者依赖版本一致
- Docker 构建可复现
- 审计时可追踪依赖版本变化

## Risks / Trade-offs

**Risk**: uv 尚未完全成熟，可能存在边缘 bug
→ **Mitigation**: uv 已被多家公司采用（包括大型 Django 项目），核心功能稳定；保留 pip 兼容性作为 fallback

**Risk**: 团队成员需学习新工具
→ **Mitigation**: uv 命令简洁（uv add、uv sync、uv run），学习成本低；提供开发文档

**Risk**: uv.lock 文件体积较大（复杂项目可达 MB）
→ **Mitigation**: 后端依赖数量有限，预计 uv.lock 约 50-100KB，可接受

**Trade-off**: 不使用 uv 官方 Docker 镜像
→ 选择复制 uv 二进制方式，换取对基础镜像的灵活控制

## Migration Plan

**Phase 1: 本地开发迁移**
1. 安装 uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
2. 运行 `uv sync` 生成虚拟环境和 uv.lock
3. 测试 `uv run pytest` 验证功能

**Phase 2: Docker 构建迁移**
1. 更新 Dockerfile，添加 uv 二进制
2. 测试 Docker 构建，验证镜像功能
3. 对比构建时间，确认性能提升

**Phase 3: 文档更新**
1. 更新 README/开发文档，说明 uv 使用方式
2. 添加常见问题解答

**Rollback**: 如遇重大问题，可快速回退到 pip + pyproject.toml 方案（已存在）

## Open Questions

无。技术方案明确，可直接实施。