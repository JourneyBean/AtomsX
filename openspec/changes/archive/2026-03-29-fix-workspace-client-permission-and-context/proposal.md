## Why

当前 workspace-client 调用 Claude Agent SDK 时存在两个关键问题：

1. **工具调用未执行**：未配置 `permission_mode`，导致工具调用需要用户审批，但系统没有实现审批流程，工具实际上不会执行。

2. **路径幻觉问题**：未配置 `system_prompt` 告知 Claude 当前的运行环境，导致 Claude 使用训练数据中的常见路径（如 `/Users/zhengzhong/Projects/...`），而不是正确的容器内路径（`/home/user/workspace`）。

这是 MVP 阶段必须修复的问题，否则 AI Agent 无法真正操作文件系统，核心功能无法工作。

## What Changes

### 新增配置

- 在 `ClaudeAgentOptions` 中添加 `permission_mode: "bypassPermissions"`，允许所有工具调用自动执行
- 在 `ClaudeAgentOptions` 中添加 `system_prompt`，告知 Claude 容器环境信息：
  - 工作目录：`/home/user/workspace`
  - 用户数据目录：`/home/user/data`
  - 路径使用规范

### 修改组件

- **workspace-client/agent.py**：修改 `start_session()` 和 `resume_session()` 方法，添加权限模式和系统提示配置

## Capabilities

### New Capabilities

无新增能力，这是对现有 `workspace-client` 能力的修复。

### Modified Capabilities

- `workspace-client`: 修复 Claude Agent SDK 配置，添加权限模式和系统提示

## Impact

### 控制面 (Backend)

无影响。

### Workspace Runtime

- `workspace-templates/ubuntu-24.04/src/workspace_client/agent.py` 需要修改
- 不影响镜像构建，只是代码层面的配置修改

### 安全边界

- **MVP 阶段**：使用 `bypassPermissions` 模式，允许所有工具调用
- **后续演进**：应实现 `can_use_tool` 回调进行路径校验，限制只能在 `/home/user/workspace` 和 `/home/user/data` 下操作

### 用户体验

- 用户发送消息后，Claude 可以直接创建、修改文件，无需等待审批
- 文件路径将正确使用容器内路径，不会出现幻觉路径

## Non-goals

- 不实现细粒度的权限控制（如 `can_use_tool` 回调）
- 不实现用户审批流程（需要前端配合）
- 不实现路径校验和限制
- 不实现审计日志记录工具调用