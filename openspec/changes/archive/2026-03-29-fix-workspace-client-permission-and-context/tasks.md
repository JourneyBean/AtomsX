## 1. 环境上下文常量

- [x] 1.1 在 `agent.py` 文件顶部添加 `ENV_CONTEXT` 常量，包含工作目录、用户数据目录和路径使用指南

## 2. 修改 start_session 方法

- [x] 2.1 在 `start_session()` 方法的 `options_kwargs` 中添加 `permission_mode: "bypassPermissions"`
- [x] 2.2 在 `start_session()` 方法的 `options_kwargs` 中添加 `system_prompt` 配置，使用 preset + append 模式

## 3. 修改 resume_session 方法

- [x] 3.1 在 `resume_session()` 方法的 `options_kwargs` 中添加 `permission_mode: "bypassPermissions"`
- [x] 3.2 在 `resume_session()` 方法的 `options_kwargs` 中添加 `system_prompt` 配置，使用 preset + append 模式

## 4. 测试验证

- [x] 4.1 重新构建 workspace-client 并测试工具调用是否自动执行
- [x] 4.2 验证 Claude 是否使用正确的容器内路径（而非幻觉路径）
- [x] 4.3 测试文件创建、编辑、删除操作是否正常工作