## Phase 1: Backend APIs

- [x] 1.1 创建文件浏览 API View 基础结构
- [x] 1.2 实现目录树查询 endpoint (`GET /api/workspaces/:id/tree/`)
- [x] 1.3 实现文件内容查询 endpoint (`GET /api/workspaces/:id/files/<path>`)
- [x] 1.4 实现二进制流 endpoint (`GET /api/workspaces/:id/files/<path>?raw=1`)
- [x] 1.5 实现路径安全验证
- [x] 1.6 实现文件类型/大小判断逻辑

## Phase 2: Frontend基础结构

- [x] 2.1 安装 Monaco Editor 依赖 (`@guolao/vue-monaco-editor`)
- [x] 2.2 添加 file types 定义
- [x] 2.3 创建 useFileBrowser composable
- [x] 2.4 修改 WorkspaceDetailView 添加 Tab 切换

## Phase 3: FileTree 组件

- [x] 3.1 创建 FileTree.vue 组件
- [x] 3.2 实现懒加载展开
- [x] 3.3 实现文件选中
- [x] 3.4 样式与暗色主题适配

## Phase 4: FileContent 组件

- [x] 4.1 创建 FileContent.vue 组件
- [x] 4.2 实现 Monaco Editor 文本展示
- [x] 4.3 实现图片展示
- [x] 4.4 实现大文件提示
- [x] 4.5 实现二进制提示 + 下载按钮

## Phase 5: CodeView 组合与状态

- [x] 5.1 创建 CodeView.vue 组合 FileTree 和 FileContent
- [x] 5.2 实现Tab切换状态保持
- [x] 5.3 集成测试