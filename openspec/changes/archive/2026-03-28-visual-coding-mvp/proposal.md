## Why

我们需要验证可视化 Coding 平台的核心价值闭环：用户登录后，在隔离的 Workspace 中与 AI Agent 对话，边聊边改，实时看到代码变更效果。这是平台的首个 MVP 纵向切片，旨在用最小可行功能验证产品假设，同时建立清晰的架构边界，为后续迭代奠定基础。

## What Changes

- **新增** OIDC 用户认证流程，支持用户通过外部身份提供商登录
- **新增** Workspace 创建与管理能力，每个用户可创建隔离的开发沙箱
- **新增** Agent 流式对话界面，支持 SSE 流式输出、会话持久化、中断恢复
- **新增** 实时 Preview 能力，仅登录用户可访问，展示 Workspace 内运行的应用
- **新增** 基础多租户隔离，确保用户间 Workspace 和数据隔离

### Non-goals（本期不包含）

- 发布与部署链路（Deployment、Builder、镜像构建）
- 公开访问与自定义域名（Published App 路由）
- 正式生产环境部署
- 多身份提供商切换（仅支持单一 OIDC Provider）
- 复杂权限模型（仅区分已登录/未登录）
- Workspace 高级生命周期管理（暂停、恢复、快照）

## Capabilities

### New Capabilities

- `oidc-auth`: 用户通过 OIDC Provider 登录、登出，平台获取用户身份信息并维护会话
- `workspace-management`: 用户创建、查看、删除自己的 Workspace，每个 Workspace 是隔离的容器化开发环境
- `agent-conversation`: 用户与 AI Agent 进行流式对话，支持 SSE 推送、会话历史、中断与恢复
- `realtime-preview`: 登录用户查看绑定到当前 Workspace 的实时应用预览，支持热更新

### Modified Capabilities

*None - 首次创建，无既有能力变更*

## Impact

### 架构层级

- **控制面（Django）**：新增用户、Workspace、Session 模型与 API；新增 OIDC 认证中间件
- **Workspace Runtime**：建立容器隔离运行模板，Agent Runtime 与 Preview Server 运行其中
- **预览网关（OpenResty）**：新增 Preview 路由规则，强制登录态访问控制

### 安全边界

- **多租户隔离**：用户只能访问自己的 Workspace 和 Session；Workspace 间网络隔离
- **访问控制**：Preview 路由强制验证登录态，未登录用户无法访问预览内容
- **审计**：记录登录、Workspace 创建/删除、会话开始/结束等关键事件

### 用户价值

- 用户获得完整的「登录 → 创建项目 → 对话开发 → 实时预览」体验
- 平台验证核心产品假设，收集早期用户反馈
- 为后续发布、公开访问、高级权限模型预留架构扩展空间

### 平台价值

- 建立清晰的代码边界与职责分离
- 验证容器隔离方案的可行性
- 积累 Agent 对话与预览联调经验