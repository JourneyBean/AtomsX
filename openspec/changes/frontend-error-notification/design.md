## Context

当前前端应用（Vue 3 + Pinia + TypeScript）没有统一的用户反馈机制。所有 API 调用的错误处理仅通过 `console.error` 输出，用户无法感知操作失败原因。需要实现一个全局 Toast/Notification 系统，在用户操作失败时提供可见反馈。

**当前状态**：
- `stores/session.ts` 和 `stores/auth.ts` 中 API 错误仅 console.error
- `views/*.vue` 中 catch 块无用户反馈逻辑
- 无全局通知容器或 Toast 组件

**约束**：
- 纯前端变更，不影响后端、Workspace、网关等
- 使用现有技术栈（Vue 3 + Pinia），不引入额外 UI 库
- MVP 优先，保持简单

## Goals / Non-Goals

**Goals:**
- 实现全局 Toast 组件，支持成功/警告/错误三种类型
- 实现 Notification Store 统一管理通知状态
- 在关键 API 调用失败时显示错误提示
- 通知自动消失（默认 3 秒）
- 用户可手动关闭通知

**Non-Goals:**
- 不做通知持久化或历史记录
- 不做桌面推送
- 不做后端错误码标准化映射
- 不做重试机制（本次仅显示错误）

## Decisions

### 1. 通知位置：右上角固定

**决定**：通知容器固定在页面右上角。

**备选方案**：
- A. 右上角固定（选中）—— 符合常见 UX 模式，不遮挡左侧对话区和右侧预览区
- B. 顶部居中 —— 可能遮挡标题栏
- C. 底部 —— 不符合错误提示习惯，用户注意力在上方

### 2. 技术实现：Pinia Store + Vue 组件

**决定**：使用 Pinia Store 管理通知列表，Toast 组件渲染通知。

**备选方案**：
- A. Pinia Store + 自定义组件（选中）—— 轻量，无外部依赖
- B. 第三方库（如 vue-toastification）—— MVP 阶段不需要额外依赖，后续可替换
- C. Vue 3 Teleport + 直接 DOM 操作 —— 不符合响应式架构

**实现结构**：
```
stores/notification.ts    -> NotificationStore（管理通知队列）
components/Toast.vue      -> 单个通知组件
components/ToastContainer.vue -> 通知容器（右上角）
App.vue                   -> 引入 ToastContainer
```

### 3. 通知 API 设计：函数式调用

**决定**：通过 Store action 调用，支持 `showError()`, `showSuccess()`, `showWarning()`。

**接口**：
```typescript
interface Notification {
  id: string
  type: 'success' | 'warning' | 'error'
  message: string
  duration: number  // ms, 默认 3000
}

// Store actions
showError(message: string, duration?: number)
showSuccess(message: string, duration?: number)
showWarning(message: string, duration?: number)
remove(id: string)
clear()
```

### 4. 集成策略：渐进式改造

**决定**：先改造关键 API 调用点，后续逐步覆盖。

**首批集成点**：
- `WorkspaceListView.vue`: createWorkspace, deleteWorkspace
- `WorkspaceDetailView.vue`: 启动/停止 workspace
- `stores/session.ts`: startSession, sendMessage
- `stores/auth.ts`: login, logout（可选）

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 通知堆叠过多影响 UI | 限制最大显示数量（如 5 条），超出自动移除最旧 |
| 错误信息过长 | 截断或换行显示，最大高度限制 |
| 错误信息不够友好 | 后续迭代可添加错误码映射，本次直接显示后端返回信息 |

## Migration Plan

1. 创建 NotificationStore 和 Toast 组件
2. 在 App.vue 中引入 ToastContainer
3. 逐个改造 API 调用点，添加错误通知
4. 测试关键场景

**回滚**：移除 ToastContainer 引入即可，不影响现有功能。

## Open Questions

- 错误信息是否需要翻译/本地化？（MVP 阶段暂不做）
- 是否需要添加"查看详情"按钮？（暂不做，直接显示完整信息）