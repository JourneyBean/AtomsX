## Context

用户在与 AI Agent 协作时，需要能够实时查看 Agent 生成的代码文件。当前 Workspace Detail View右侧只有 Preview iframe，无法直接浏览源代码。

需要实现一个代码浏览器，包含：
- Tab切换：Preview / Code
- 树形文件目录（懒加载）
- 文件内容展示（Monaco Editor / 图片 / 提示信息）

## Goals / Non-Goals

**Goals:**
- 实现 Backend 文件 API：目录树查询、文件内容查询、二进制流下载
- 实现 Frontend CodeView 组件：Tab 切换、FileTree、FileContent
- 支持文本文件展示（Monaco Editor 只读）
- 支持图片文件展示
- 大文件 (>2MB) 提示无法展示
- 二进制文件提示无法打开并提供下载
- Tab 切换时记住选中文件状态

**Non-Goals:**
- 文件编辑功能
- 文件上传功能
- 文件搜索功能
- 文件变更实时同步
- 非 UTF-8 编码支持

## Decisions

### 1. 文件数据来源

**决策：Backend API 读取宿主机文件**

**理由：**
- Backend 已有 `data_dir_path` 字段，可直接读取宿主机 bind mount 的文件
- 无需修改容器镜像
- 权限控制集中，安全性好
- 文件内容与 Agent 操作的一致（bind mount 同步）

**备选方案：**
- 从 Workspace Container 读取：需要修改镜像添加文件服务，增加复杂度

### 2. Monaco Editor 选型

**决策：@guolao/vue-monaco-editor**

**理由：**
- Vue 3 原生组件封装
- 支持 TypeScript 配置
- 按需加载语言支持
- 社区活跃，维护良好

### 3. File Tree 实现

**决策：自定义 Vue 组件**

**理由：**
- 当前项目无额外 UI 库，保持轻量
- 懒加载需求简单，无需复杂库
- 样式与现有暗色主题一致

### 4. 文件大小限制

**决策：2MB**

**理由：**
- 大文件影响加载性能和内存占用
- Monaco Editor 对大文件支持有限
- 2MB 覆盖绝大多数代码文件

### 5. Tab状态持久化

**决策：组件内部状态保持**

**理由：**
- 不需要跨页面持久化
- Vue reactive 状态自然保持
- 实现简单

### 6. 图片展示方式

**决策：通过 raw endpoint URL 展示**

**理由：**
- 大图片无需 base64 编码开销
- 浏览器可缓存
- 实现简洁

## Architecture

### 组件结构

```
WorkspaceDetailView.vue
├── Tab切换: preview | code
├── Preview Tab: <iframe> (现有)
└── Code Tab: <CodeView />
    ├── FileTree.vue (左侧)
    │   ├── 懒加载目录
    │   └── emit('select', path)
    │   └── emit('expand', path)
    │
    └── FileContent.vue (右侧)
        ├── 文本: <MonacoEditor />
        ├── 图片: <img src="?raw=1" />
        ├── 大文件: 提示信息
        └── 二进制: 提示 + 下载按钮
```

### API 设计

```
GET /api/workspaces/:id/tree/?path=<relative_path>
Response:
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

GET /api/workspaces/:id/files/<path>
Response (文本, size <= 2MB):
{
  "type": "text",
  "content": "...",
  "language": "vue",
  "size": 2048
}

Response (图片):
{
  "type": "image",
  "mime_type": "image/png",
  "size": 51200
}

Response (大文件, size > 2MB):
{
  "type": "too_large",
  "size": 5000000,
  "message": "文件过大，无法展示"
}

Response (二进制):
{
  "type": "binary",
  "size": 1024,
  "message": "无法打开此文件类型"
}

GET /api/workspaces/:id/files/<path>?raw=1
Response: 二进制流 (Content-Type: mime_type)
用于图片展示和文件下载
```

### 数据流

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Frontend                                   │
│                                                                     │
│  CodeView.vue                                                       │
│  │                                                                  │
│  ├── selectedPath: string                                           │
│  ├── expandedPaths: Set<string>                                     │
│  │                                                                  │
│  └── FileTree ──GET /api/.../tree──▶ nodes[]                        │
│       │                                                             │
│       └── 点击文件 → selectedPath = path                            │
│       └── 点击目录 → expandedPaths.add(path), fetch children       │
│                                                                     │
│  FileContent ──GET /api/.../files/<path>──▶ content                 │
│       │                                                             │
│       └── type == 'text' → MonacoEditor                            │
│       └── type == 'image' → <img src="?raw=1">                     │
│       └── type == 'too_large' → 提示                               │
│       └── type == 'binary' → 提示 + 下载按钮                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                            Backend                                   │
│                                                                     │
│  WorkspaceFileView                                                  │
│  │                                                                  │
│  ├── GET tree: os.listdir(data_dir_path/workspace/<path>)          │
│  ├── GET files: open(data_dir_path/workspace/<path>).read()        │
│  │                                                                  │
│  ├── 安全验证:                                                      │
│  │   - 禁止 ".." 跳出目录                                           │
│  │   - 禁止绝对路径                                                 │
│  │   - 验证所有权                                                   │
│  │                                                                  │
│  ├── 类型判断:                                                      │
│  │   - 图片扩展名 → 'image'                                         │
│  │   - UTF-8解码成功 → 'text'                                       │
│  │   - 其他 → 'binary'                                              │
│  │                                                                  │
│  └── 大小限制: size > 2MB → 'too_large'                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 文件类型判断

```python
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.ico'}

def get_file_type(path: str, size: int) -> str:
    ext = Path(path).suffix.lower()

    if ext in IMAGE_EXTENSIONS:
        return 'image'

    if size > 2 * 1024 * 1024:  # 2MB
        return 'too_large'

    # 尝试 UTF-8 解码
    try:
        content = file.read()
        content.encode('utf-8')  # 验证编码
        return 'text'
    except:
        return 'binary'

def get_language(path: str) -> str:
    EXT_TO_LANG = {
        '.js': 'javascript',
        '.ts': 'typescript',
        '.vue': 'vue',
        '.py': 'python',
        '.json': 'json',
        '.html': 'html',
        '.css': 'css',
        '.scss': 'scss',
        '.md': 'markdown',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.sh': 'shell',
        '.sql': 'sql',
        '.xml': 'xml',
        '.txt': 'plaintext',
    }
    return EXT_TO_LANG.get(Path(path).suffix.lower(), 'plaintext')
```

### 前端组件状态

```typescript
// CodeView.vue state
const activeTab = ref<'preview' | 'code'>('preview')
const selectedPath = ref<string | null>(null)
const expandedPaths = ref<Set<string>>(new Set())
const fileContent = ref<FileContent | null>(null)
const treeCache = ref<Map<string, FileNode[]>>(new Map())

// 切换 Tab时保持状态
watch(activeTab, (newTab) => {
  if (newTab === 'code' && selectedPath.value) {
    // 恢复之前的选中状态
    fetchFileContent(selectedPath.value)
  }
})
```

## Risks / Trade-offs

### Risk 1: 文件路径安全

**风险：** 恶意路径可能访问workspace外的文件

**缓解：**
- 禁止 ".." 在路径中
- 禁止绝对路径（以 "/" 开头）
- 验证最终路径在 `data_dir_path/workspace/` 内

### Risk 2: 大文件内存占用

**风险：** 大文件加载占用过多内存

**缓解：**
- 2MB 限制
- 不展示时只返回元信息

### Risk 3: 二进制文件 XSS

**风险：** 通过 raw endpoint 可能返回恶意内容

**缓解：**
- raw endpoint 只用于已知图片类型和下载
- 前端根据 type 字段决定如何处理

## Open Questions

1. **是否需要刷新按钮？**
   - 当前设计：每次点击目录都重新请求
   - 可以考虑添加手动刷新按钮

2. **是否需要面包屑导航？**
   - 当前设计：只有树形视图
   - 可以后续添加面包屑辅助定位