# File Browser Capability Spec

## Overview

代码文件浏览能力，允许用户在工作空间中浏览目录结构和查看文件内容。

## User Stories

### US-1: 浏览目录结构

**角色：** Workspace 用户
**需求：** 查看工作空间的文件目录结构
**验收标准：**
- 显示树形目录视图
- 目录可展开/折叠
- 展开时懒加载子目录内容
- 显示文件和文件夹图标
- 显示文件大小信息

### US-2: 查看代码文件

**角色：** Workspace 用户
**需求：** 查看源代码文件内容
**验收标准：**
- 点击文件显示内容
- 使用 Monaco Editor 展示代码
- 自动识别语言并高亮
- 只读模式，不可编辑
- 保持暗色主题风格

### US-3: 查看图片文件

**角色：** Workspace 用户
**需求：** 查看工作空间中的图片文件
**验收标准：**
- 图片文件直接显示图片内容
- 支持常见图片格式（png, jpg, gif, webp, svg）
- 图片可缩放查看

### US-4: 处理大文件

**角色：** Workspace 用户
**需求：** 当文件过大时得到明确提示
**验收标准：**
- 超过 2MB 的文件不展示内容
- 显示"文件过大，无法展示"提示
- 显示文件大小信息

### US-5: 处理二进制文件

**角色：** Workspace 用户
**需求：** 无法直接查看的文件提供下载选项
**验收标准：**
- 二进制文件显示"无法打开此文件类型"提示
- 提供下载按钮
- 下载使用原始文件名

### US-6: Tab 状态保持

**角色：** Workspace 用户
**需求：** 在 Preview 和 Code Tab间切换时保持状态
**验收标准：**
- 切换到 Code Tab 后再切回 Preview，再切回 Code 时
- 之前选中的文件仍然选中
- 展开的目录状态保持

## API Specification

### Get Directory Tree

```
GET /api/workspaces/:id/tree/?path=<relative_path>

Query Parameters:
  - path: 相对路径，可选，默认为根目录

Response 200:
{
  "nodes": [
    {
      "name": "src",
      "type": "directory",
      "path": "src",
      "has_children": true
    },
    {
      "name": "App.vue",
      "type": "file",
      "path": "src/App.vue",
      "size": 2048,
      "language": "vue"
    }
  ]
}

Response 403: 无权限访问此workspace
Response 404: 目录不存在
Response 400: 无效路径
```

### Get File Content

```
GET /api/workspaces/:id/files/<path>

Response 200 (文本文件):
{
  "type": "text",
  "content": "文件内容...",
  "language": "vue",
  "size": 2048
}

Response 200 (图片文件):
{
  "type": "image",
  "mime_type": "image/png",
  "size": 51200
}

Response 200 (大文件):
{
  "type": "too_large",
  "size": 5000000,
  "message": "文件过大，无法展示"
}

Response 200 (二进制文件):
{
  "type": "binary",
  "size": 1024,
  "message": "无法打开此文件类型"
}

Response 403: 无权限访问此workspace
Response 404: 文件不存在
Response 400: 无效路径
```

### Get Raw File (Binary Stream)

```
GET /api/workspaces/:id/files/<path>?raw=1

Response 200:
  Content-Type: <mime_type>
  Body: 二进制流

Response 403: 无权限访问此workspace
Response 404: 文件不存在
Response 400: 无效路径
```

## Security Requirements

- 路径验证：禁止 ".."、禁止绝对路径、禁止跳出 workspace 目录
- 权限验证：只能访问用户拥有的 workspace
- 二进制响应：设置正确的 Content-Type，不返回HTML 以防 XSS

## Performance Requirements

- 目录树响应时间 < 500ms
- 文件内容响应时间 < 1s（对于小于 2MB 的文件）
- 大文件只返回元信息，不尝试读取内容