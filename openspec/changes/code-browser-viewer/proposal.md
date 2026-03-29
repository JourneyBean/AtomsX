## Why

用户在与 AI Agent 协作时，需要能够实时查看 Agent 生成的代码文件。当前 Workspace Detail View 只能通过 Preview iframe 查看运行效果，无法直接浏览和查看源代码文件。

提供代码浏览功能可以：
- 让用户直观了解 Agent 修改了哪些文件
- 方便用户学习和理解生成的代码
- 增强用户对 Agent 工作的信任和掌控感

## What Changes

### 新增组件

- **CodeView**：代码浏览面板，作为 Workspace Detail View 右侧面板的 Code Tab
  - Tab 切换：Preview / Code
  - 包含 FileTree 和 FileContent 两个子组件

- **FileTree**：树形文件浏览器
  - 懒加载目录结构（点击展开时加载子目录）
  - 显示文件/文件夹图标
  - 支持文件选中

- **FileContent**：文件内容展示区
  - 文本文件：Monaco Editor 只读展示
  - 图片文件：直接显示图片
  - 大文件 (>2MB)：提示"文件过大，无法展示"
  - 二进制文件：提示"无法打开" + 下载按钮

- **Backend File APIs**：
  - `GET /api/workspaces/:id/tree/?path=<relative_path>` - 获取目录结构
  - `GET /api/workspaces/:id/files/<path>` - 获取文件内容
  - `GET /api/workspaces/:id/files/<path>?raw=1` - 获取二进制流（图片/下载）

### 修改组件

- **WorkspaceDetailView**：添加 Tab 切换，引入 CodeView

### 新增依赖

- **Frontend**：`@guolao/vue-monaco-editor` - Monaco Editor Vue 3封装

## Capabilities

### New Capabilities

- `file-browser`: 代码文件浏览能力，支持树形目录导航和文件内容查看

### Modified Capabilities

- `workspace-management`: Workspace API 扩展，新增文件相关 endpoints

## Impact

### 控制面 (Backend)

- 新增 `WorkspaceFileView` API View
  - 目录树查询 endpoint
  - 文件内容查询 endpoint
  - 二进制流 endpoint
- 路径安全验证（禁止 `..`、绝对路径、跳出workspace目录）
- 文件类型/大小判断逻辑

### Frontend

- 新增组件：`CodeView.vue`、`FileTree.vue`、`FileContent.vue`
- 新增 composable：`useFileBrowser.ts`
- 新增 types：`file.ts`
- 新增依赖：`@guolao/vue-monaco-editor`

### 用户体验

- 右侧面板增加 Tab 切换，可选择查看 Preview 或 Code
- Code Tab 下可浏览工作空间所有文件
- Tab 切换时记住当前选中的文件状态

### 安全边界

- 文件 API 仅返回当前用户拥有的 Workspace 文件
- 路径验证确保无法访问 workspace 目录外的文件
- 二进制文件通过 `?raw=1` 参数单独获取，避免 XSS

## Non-goals

- 不实现文件编辑功能（后续演进）
- 不实现文件上传功能
- 不实现文件搜索功能
- 不实现文件变更实时同步（需要手动刷新目录）
- 不支持非 UTF-8 编码的文本文件显示