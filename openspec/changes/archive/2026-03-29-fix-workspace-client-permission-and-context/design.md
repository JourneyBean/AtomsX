## Context

### 当前状态

```
┌─────────────────────────────────────────────────────────────────────┐
│                    workspace-client agent.py                         │
│                                                                     │
│  start_session():                                                   │
│    options_kwargs = {                                               │
│        "cwd": Path("/home/user/workspace"),                         │
│        "env": env_vars,                                             │
│    }                                                                │
│    # ❌ 缺少 permission_mode                                        │
│    # ❌ 缺少 system_prompt                                          │
│                                                                     │
│  权限评估流程:                                                       │
│  钩子 → 权限规则 → 权限模式(None) → canUseTool(None)                 │
│                          ↓                                          │
│                    默认需要用户确认，但没有确认流程                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 问题分析

1. **工具未执行**：`permission_mode` 未设置，SDK 默认进入需要用户确认的模式，但系统没有实现确认流程（前端没有审批 UI，后端没有 `can_use_tool` 回调）。

2. **路径幻觉**：Claude 不知道自己在容器中运行，使用了训练数据中的常见路径模式（如 macOS 开发者的 `/Users/xxx/Projects/...`）。

## Goals / Non-Goals

**Goals:**

- 让 Claude Agent SDK 能够直接执行工具调用，无需用户确认
- 告知 Claude 当前的运行环境，引导其使用正确的路径
- 最小化代码改动，快速让 MVP 跑起来

**Non-Goals:**

- 不实现细粒度权限控制
- 不实现路径校验和限制
- 不实现用户审批流程
- 不实现工具调用审计日志

## Decisions

### Decision 1: 使用 `bypassPermissions` 模式

**决策**：在 `ClaudeAgentOptions` 中设置 `permission_mode: "bypassPermissions"`

**理由**：
- MVP 阶段需要快速验证核心功能
- Workspace 容器本身已经是隔离环境，风险可控
- 实现审批流程需要前后端配合，工作量较大

**备选方案**：
- `acceptEdits`：只自动批准文件操作，其他命令仍需确认。但 MVP 阶段希望所有操作都能自动执行。
- 实现 `can_use_tool` 回调：可以做更细粒度的控制，但增加复杂度。

### Decision 2: 使用 `system_prompt` preset + append

**决策**：
```python
"system_prompt": {
    "type": "preset",
    "preset": "claude_code",
    "append": ENV_CONTEXT,
}
```

**理由**：
- 使用 `claude_code` preset 保留 Claude Code 的工具指令和安全指南
- 通过 `append` 添加环境特定的上下文信息
- 比完全自定义 system_prompt 更简单，且保留了内置的安全指令

**备选方案**：
- 完全自定义 `system_prompt`：会丢失 Claude Code 内置的工具指令和安全指南
- 依赖 `cwd` 参数：`cwd` 只是建议性的，不会阻止 Claude 使用其他路径

### Decision 3: 环境上下文内容

**决策**：在 `append` 中包含：
- 工作目录路径和用途
- 用户数据目录路径
- 路径使用规范和示例

**理由**：
- 清晰明确地告知 Claude 当前环境
- 提供正确的路径示例，减少幻觉
- 不包含敏感信息（如 token、API key）

## Risks / Trade-offs

### Risk 1: bypassPermissions 的安全风险

**风险**：Claude 可以在容器内执行任意命令和文件操作。

**缓解**：
- Workspace 容器本身就是隔离的沙箱环境
- 容器不拥有宿主机的高权限（无 Docker socket、无 K8s admin）
- 容器资源有限制（CPU、内存）

**后续改进**：实现 `can_use_tool` 回调，限制只能在特定目录下操作。

### Risk 2: system_prompt 可能被忽略

**风险**：Claude 可能不遵循 system_prompt 中的路径指引。

**缓解**：
- 使用 `cwd` 参数作为工作目录
- 通过明确的指令和示例引导正确行为

**后续改进**：实现 `can_use_tool` 回调进行路径校验，拒绝不在允许目录内的操作。

### Trade-off: 简单性 vs 控制力

**选择**：MVP 阶段优先简单性
- 使用 `bypassPermissions` 而不是细粒度权限控制
- 使用 `system_prompt` 引导而不是强制校验

**长期演进**：逐步增加控制力
1. Phase 1: bypassPermissions + system_prompt（当前）
2. Phase 2: can_use_tool 路径校验
3. Phase 3: 用户审批流程（需要前端配合）

## Implementation Overview

```
修改文件: workspace-templates/ubuntu-24.04/src/workspace_client/agent.py

1. 添加环境上下文常量 ENV_CONTEXT
2. 修改 start_session() 中的 options_kwargs
3. 修改 resume_session() 中的 options_kwargs
```