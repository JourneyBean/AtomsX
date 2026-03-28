# AtomsX Backend

Django 5.2 后端服务，使用 uv 进行依赖管理。

## 开发环境设置

### 安装 uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 pip
pip install uv
```

### 初始化项目

```bash
# 进入 backend 目录
cd backend

# 同步依赖（创建 .venv 并安装所有依赖）
uv sync

# 激活虚拟环境（可选，uv run 会自动使用）
source .venv/bin/activate
```

## 常用命令

### 依赖管理

```bash
# 安装所有依赖
uv sync

# 添加新依赖
uv add <package-name>

# 添加开发依赖
uv add --dev <package-name>

# 移除依赖
uv remove <package-name>

# 更新所有依赖
uv sync --upgrade
```

### 运行命令

```bash
# 在虚拟环境中运行命令
uv run <command>

# 示例：运行 Django 开发服务器
uv run python manage.py runserver

# 示例：运行测试
uv run pytest

# 示例：Django 管理命令
uv run python manage.py migrate
uv run python manage.py createsuperuser
```

### 测试

```bash
# 运行所有测试
uv run pytest

# 运行特定测试文件
uv run pytest apps/users/tests.py

# 带覆盖率报告
uv run pytest --cov=apps --cov-report=html
```

## Docker 构建

```bash
# 构建镜像
docker build -t atomsx-backend:latest .

# 构建时使用代理
docker build \
  --build-arg HTTP_PROXY=http://proxy:port \
  --build-arg HTTPS_PROXY=http://proxy:port \
  -t atomsx-backend:latest .

# 运行容器
docker run -p 8000:8000 atomsx-backend:latest
```

## 项目结构

```
backend/
├── apps/                    # Django 应用
│   ├── core/               # 核心功能
│   ├── users/              # 用户管理
│   ├── workspaces/         # 工作空间管理
│   └── sessions/           # 会话管理
├── config/                  # Django 配置
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── pyproject.toml          # 项目配置和依赖
├── uv.lock                 # 锁定的依赖版本
├── .python-version         # Python 版本 (3.12)
└── Dockerfile              # Docker 构建文件
```

## 依赖说明

### 核心依赖
- **Django 5.2**: Web 框架
- **Django REST Framework 3.15**: API 框架
- **PostgreSQL (psycopg2-binary)**: 数据库驱动
- **Redis**: 缓存和 Celery broker
- **Celery**: 异步任务队列

### 开发依赖
- **pytest**: 测试框架
- **pytest-django**: Django 测试工具
- **pytest-cov**: 覆盖率报告

## 故障排除

### uv sync 失败

如果遇到依赖安装问题：

```bash
# 清除缓存重新安装
rm -rf .venv uv.lock
uv sync
```

### Python 版本问题

项目需要 Python 3.11-3.12。使用 uv 管理版本：

```bash
# 查看可用 Python 版本
uv python list

# 安装特定版本
uv python install 3.12

# 固定项目 Python 版本
uv python pin 3.12
```

### Docker 构建问题

如果 Docker 构建时依赖下载失败：

```bash
# 检查代理设置
docker build --build-arg HTTP_PROXY=$HTTP_PROXY ...
```

### VS Code 集成

选择正确的 Python 解释器：

1. 打开命令面板 (Cmd+Shift+P)
2. 选择 "Python: Select Interpreter"
3. 选择 `.venv` 中的 Python 解释器

## 从 pip 迁移

如果你习惯使用 pip：

| pip 命令 | uv 等价命令 |
|---------|------------|
| `pip install -r requirements.txt` | `uv sync` |
| `pip install <pkg>` | `uv add <pkg>` |
| `pip install -e .` | `uv sync` |
| `pip freeze > requirements.txt` | (自动管理 uv.lock) |
| `python -m venv .venv` | (uv sync 自动创建) |