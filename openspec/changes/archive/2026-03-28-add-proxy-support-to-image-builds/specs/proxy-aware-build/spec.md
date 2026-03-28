## ADDED Requirements

### Requirement: Dockerfile 构建参数支持代理变量

所有 Dockerfile MUST 声明以下构建参数以支持代理配置：
- `HTTP_PROXY` / `http_proxy`
- `HTTPS_PROXY` / `https_proxy`
- `NO_PROXY` / `no_proxy`

代理变量 MUST 仅用于构建阶段，SHALL NOT 持久化到最终镜像的运行时环境变量中。

#### Scenario: 构建时传递代理变量
- **WHEN** 构建者通过 `--build-arg HTTP_PROXY=http://proxy.example.com:8080` 构建镜像
- **THEN** 镜像构建过程中的网络请求 MUST 通过指定的代理服务器

#### Scenario: 构建时不传递代理变量
- **WHEN** 构建者未传递任何代理变量
- **THEN** 构建过程 MUST 正常执行，直接访问网络资源（不通过代理）

#### Scenario: 代理变量不持久化到镜像
- **WHEN** 镜像构建完成
- **THEN** 最终镜像 MUST NOT 包含 HTTP_PROXY、HTTPS_PROXY、NO_PROXY 等代理环境变量

### Requirement: apt-get 命令支持代理

Dockerfile 中所有 `apt-get` 命令 MUST 支持通过代理变量访问软件源。

#### Scenario: apt-get 通过代理下载
- **WHEN** HTTP_PROXY 或 http_proxy 构建参数已设置
- **AND** 执行 `apt-get update` 或 `apt-get install`
- **THEN** apt MUST 使用指定的代理访问 Debian/Ubuntu 软件源

### Requirement: pip 命令支持代理

Dockerfile 中所有 `pip` / `uv pip` 命令 MUST 支持通过代理变量访问 PyPI。

#### Scenario: pip 通过代理下载包
- **WHEN** HTTPS_PROXY 或 https_proxy 构建参数已设置
- **AND** 执行 `pip install` 或 `uv sync`
- **THEN** pip MUST 使用指定的代理访问 PyPI 服务器

### Requirement: npm 命令支持代理

Dockerfile 中所有 `npm install` 命令 MUST 支持通过代理变量访问 npm registry。

#### Scenario: npm 通过代理下载包
- **WHEN** HTTP_PROXY 或 HTTPS_PROXY 构建参数已设置
- **AND** 执行 `npm install`
- **THEN** npm MUST 使用指定的代理访问 npm registry

### Requirement: docker-compose build 自动传递代理变量

docker-compose.yml 中所有服务的 `build.args` MUST 自动从宿主机环境变量传递代理变量，格式为 `${HTTP_PROXY:-}`，无值时传递空字符串。

#### Scenario: docker-compose build 传递代理
- **WHEN** 宿主机设置了环境变量 HTTP_PROXY=http://proxy.example.com:8080
- **AND** 执行 `docker-compose build`
- **THEN** 所有服务的构建过程 MUST 自动接收该代理变量

#### Scenario: docker-compose build 无代理环境
- **WHEN** 宿主机未设置代理相关环境变量
- **AND** 执行 `docker-compose build`
- **THEN** 构建 MUST 正常执行，无代理配置传递（不报错）

### Requirement: NO_PROXY 变量支持绕过代理

构建过程 MUST 支持 NO_PROXY 变量，允许指定不需要通过代理访问的地址。

#### Scenario: 指定绕过代理的地址
- **WHEN** NO_PROXY 设置为 `localhost,127.0.0.1,.internal.example.com`
- **AND** 构建过程访问匹配该模式的地址
- **THEN** 请求 MUST 直接访问，不通过代理服务器