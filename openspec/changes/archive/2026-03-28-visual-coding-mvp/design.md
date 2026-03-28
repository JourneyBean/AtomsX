## Context

本设计文档描述 MVP 纵向切片的技术实现方案。核心目标是在保持架构边界清晰的前提下，快速交付「登录 → 创建 Workspace → Agent 对话 → 实时预览」的完整用户流程。

当前状态：全新项目，无既有代码。技术栈已确定为 Vue 3 + Django 5.2 + PostgreSQL + Redis + OpenResty + Docker。

关键约束：
- Workspace 必须容器隔离，不能持有宿主高权限
- 预览路由必须强制登录态
- Agent 对话必须支持流式输出和会话恢复
- MVP 需要能在单机运行，但架构要可演进到 K8s

## Goals / Non-Goals

**Goals:**
- 实现完整的 OIDC 登录流程（单 Provider）
- 实现 Workspace 的创建、查看、删除，每个 Workspace 是隔离容器
- 实现 Agent 流式对话，支持 SSE 推送、历史恢复、用户中断
- 实现 Preview 路由，强制登录验证，支持热更新信号
- 建立多租户隔离：用户只能访问自己的 Workspace/Session

**Non-Goals:**
- 不实现发布/部署链路（Builder、Deployer、Deployment 模型）
- 不实现公开访问路由（Published App）
- 不实现多 Provider 切换、复杂权限模型
- 不实现 Workspace 暂停/恢复/快照
- 不实现生产级高可用部署

## Decisions

### 1. OIDC Provider 选型：使用 Authentik 作为本地开发 Provider

**决定**: MVP 阶段使用 Authentik 作为 OIDC Provider，本地 Docker Compose 部署。

**原因**:
- Authentik 是开源、自托管、易于本地部署的 OIDC Provider
- 避免 MVP 阶段绑定商业 SaaS（如 Auth0、Okta）
- 后期可平滑切换到企业 Provider（接口标准化）

**替代方案**:
- Keycloak：更成熟但配置复杂，启动较慢
- 直接对接 Auth0：绑定商业 SaaS，本地开发需 Mock

**临时简化**：仅支持一个 Provider，不实现 Provider 切换机制。

### 2. Workspace 容器管理：宿主 Docker + Django 控制

**决定**: MVP 阶段，Django 控制面通过 Docker SDK（docker-py）管理 Workspace 容器生命周期。

**原因**:
- 快速落地，无需引入 K8s 复杂度
- docker-py 提供足够的管理能力（创建、删除、状态查询）
- 容器网络隔离可通过 Docker Network 实现

**安全边界**:
- Django 进程持有 Docker 访问权限，Workspace 容器本身不持有
- Workspace 容器通过自定义 Network 隔离
- 容器内只运行：Agent Runtime + Preview Server（无 Docker/K8s 访问）

**演进路径**:
- 单机 → K8s：将 Docker SDK 替换为 K8s Client，容器模板转为 Pod Spec
- 状态归属不变：控制面管理元数据，Runtime 管理容器/Pod

### 3. Agent Runtime：Django + SSE + Claude Agent SDK

**决定**: Agent 对话使用 Django SSE 推送，Claude Agent SDK 在独立进程中运行。

**原因**:
- SSE 是单向流式输出的最简方案
- Django 内置 SSE 支持（StreamingHttpResponse + asyncio）
- Claude Agent SDK 需要独立进程以避免阻塞 Django Worker

**架构设计**:
- Django 接收用户消息，写入 Redis Queue
- Celery Worker 调用 Claude Agent SDK，生成流式响应
- 响应通过 SSE Channel 推送到前端
- Session State 存储在 PostgreSQL，支持恢复

**替代方案**:
- WebSocket（Django Channels）：双向能力更强，但 MVP 阶段 SSE 已足够
- 同步 API：无法支持流式，体验差

### 4. Preview 路由：OpenResty 反向代理 + 认证转发

**决定**: Preview 流量通过 OpenResty 反向代理到 Workspace 容器，认证由控制面 API 验证。

**原因**:
- OpenResty 可执行 Lua 脆片，做认证转发
- 统一入口便于审计和流量控制
- 预览域名：<workspace-id>.preview.local（MVP 阶段）

**认证流程**:
1. 用户访问 `<workspace-id>.preview.local`
2. OpenResty 携带 Cookie/Header 转发到 Django `/api/auth/verify`
3. Django 返回用户身份 + Workspace 访问权限
4. OpenResty 根据结果放行或拒绝
5. 放行后转发到对应 Workspace 容器的 Preview Server

**热更新信号**: Workspace Preview Server 通过 SSE 接收文件变更信号，触发前端刷新。

### 5. 数据模型设计

**决定**: MVP 核心模型：User、Workspace、Session。

**模型定义**:
- **User**: OIDC sub（唯一标识）、email、display_name、created_at
- **Workspace**: id（UUID）、owner（User FK）、name、container_id、status（creating/running/stopped/error）、created_at
- **Session**: id（UUID）、workspace（Workspace FK）、user（User FK）、messages（JSON）、status、created_at、updated_at

**状态归属**:
- User/Workspace/Session 元数据：控制面 PostgreSQL
- Workspace 容器状态：Docker（由控制面查询）
- Session 对话历史：控制面 PostgreSQL
- Workspace 文件系统：容器内 Volume（独立存储）

### 6. 网络隔离设计

**决定**: Workspace 容器使用独立 Docker Network，Preview Server 通过端口映射暴露。

**原因**:
- 简单隔离，无需 Overlay Network
- 每个容器内 Preview Server 监听固定端口（如 3000）
- OpenResty 通过宿主端口映射访问

**演进路径**:
- 单机：端口映射（随机宿主端口）
- K8s：Service + Ingress，NetworkPolicy 隔离

## Risks / Trade-offs

### Risk: Django 持有 Docker 权限 → 容器逃逸风险
- **影响**: Django 被攻破可能导致宿主机控制权泄露
- **缓解**: Django 仅持有最小 Docker 权限；运行在受限环境；审计所有容器操作
- **长期**: 迁移到 K8s 后，控制面只操作 K8s API，不直接接触宿主

### Risk: OpenResty 认证转发增加延迟
- **影响**: Preview 请求需先验证，影响响应时间
- **缓解**: 认证结果缓存（短 TTL）；Lua 脚本异步执行
- **长期**: 考虑 JWT 本地验证，减少控制面依赖

### Risk: Agent Runtime 进程管理复杂度
- **影响**: Celery Worker 状态管理、重启、故障恢复
- **缓解**: Celery Beat 监控 Worker 健康状态；重启机制
- **长期**: 评估独立 Agent Runtime Service 架构

### Trade-off: MVP 使用端口映射而非 NetworkPolicy
- **优势**: 快速落地，无 K8s 依赖
- **代价**: 隔离粒度较低，端口冲突风险
- **演进**: K8s NetworkPolicy 提供更强隔离

### Trade-off: SSE 单向而非 WebSocket 双向
- **优势**: 实现简单，Django 原生支持
- **代价**: 用户中断需通过单独 API，而非直接 Channel
- **演进**: 需要双向实时时迁移到 WebSocket

## Open Questions

1. **Preview Server 选型**: Workspace 内预览进程用什么技术栈？
   - 候选：Vite Dev Server（前端项目）、Node Express（通用）、各语言默认 Server
   - 建议：MVP 固定为 Vue 项目，使用 Vite Dev Server

2. **Agent 工具调用边界**: Agent 能执行哪些文件操作？
   - 需定义安全策略：允许读写哪些路径、禁止删除关键文件
   - 建议：MVP 阶段限制在 `/workspace/src` 目录内

3. **会话持久化粒度**: 消息历史如何存储？
   - 候选：完整 JSON、增量摘要、压缩存储
   - 建议：MVP 存储完整 JSON，后期评估摘要

## Migration Plan

**部署步骤**:
1. 启动 Authentik（OIDC Provider）
2. 启动 PostgreSQL + Redis
3. 启动 Django（控制面）+ Celery Worker
4. 启动 OpenResty（网关）
5. 启动前端 Vue App
6. 用户登录测试
7. Workspace 创建测试
8. Agent 对话测试
9. Preview 访问测试

**回滚策略**:
- 无数据迁移，直接停止服务即可
- 用户数据（Workspace 文件）独立存储，回滚不影响

## Architecture Diagram (Text)

```
┌─────────────────────────────────────────────────────────────────┐
│                         External Traffic                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      OpenResty Gateway                           │
│  - Preview: *.preview.local → auth verify → workspace container │
│  - API: /api/* → Django                                         │
│  - Frontend: /* → Vue App                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌───────────────────────┐       ┌───────────────────────┐
│   Django Control Plane│       │      Vue Frontend     │
│   - OIDC Auth         │       │   - Login Page        │
│   - Workspace API     │       │   - Workspace List    │
│   - Session API       │       │   - Chat Panel (SSE)  │
│   - SSE Endpoint      │       │   - Preview Frame     │
└───────────────────────┘       └───────────────────────┘
              │                               │
              ▼                               │
┌───────────────────────┐                     │
│    PostgreSQL         │                     │
│    - User             │                     │
│    - Workspace        │                     │
│    - Session          │                     │
└───────────────────────┘                     │
              │                               │
              ▼                               │
┌───────────────────────┐                     │
│       Redis           │                     │
│    - Session Cache    │                     │
│    - Celery Queue     │                     │
└───────────────────────┘                     │
              │                               │
              ▼                               │
┌───────────────────────┐                     │
│   Celery Worker       │◄────────────────────┘
│   - Claude Agent SDK  │     (SSE push to frontend)
│   - File Operations   │
└───────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Workspace Container Pool                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  Workspace A    │  │  Workspace B    │  │  Workspace C    │ │
│  │  - Agent Runtime│  │  - Agent Runtime│  │  - Agent Runtime│ │
│  │  - Preview Srv  │  │  - Preview Srv  │  │  - Preview Srv  │ │
│  │  - Source Files │  │  - Source Files │  │  - Source Files │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```