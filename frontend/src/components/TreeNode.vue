<script setup lang="ts">
import { inject, ref, computed } from 'vue'
import type { FileNode } from '@/types/file'

const props = defineProps<{
  node: FileNode
}>()

const emit = defineEmits<{
  select: [path: string]
}>()

// Inject context from parent FileTree
const expandedPaths = inject<Set<string>>('expandedPaths')!
const treeCache = inject<Map<string, FileNode[]>>('treeCache')!
const toggleDirectory = inject<(path: string) => Promise<FileNode[]>>('toggleDirectory')!

// Local children for when not in cache
const localChildren = ref<FileNode[]>([])

// Computed children
const children = computed(() => {
  return treeCache.get(props.node.path) || localChildren.value
})

// Check if expanded
const isExpanded = computed(() => {
  return expandedPaths.has(props.node.path)
})

// Handle click
async function handleClick() {
  if (props.node.type === 'directory') {
    if (props.node.has_children) {
      localChildren.value = await toggleDirectory(props.node.path)
    }
  } else {
    emit('select', props.node.path)
  }
}

// Get icon
function getIcon(): string {
  if (props.node.type === 'directory') {
    return isExpanded.value ? '📂' : '📁'
  }

  const icons: Record<string, string> = {
    'javascript': '📜',
    'typescript': '📜',
    'vue': '💚',
    'python': '🐍',
    'json': '📋',
    'html': '🌐',
    'css': '🎨',
    'markdown': '📝',
    'yaml': '⚙️',
    'plaintext': '📄',
  }

  return icons[props.node.language || 'plaintext'] || '📄'
}

// Format size
function formatSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

// Pass select event up
function handleChildSelect(path: string) {
  emit('select', path)
}
</script>

<template>
  <div class="tree-node">
    <div class="node-row" @click="handleClick">
      <span class="expand-arrow" v-if="node.type === 'directory' && node.has_children">
        {{ isExpanded ? '▼' : '▶' }}
      </span>
      <span class="expand-arrow placeholder" v-else-if="node.type === 'directory'"></span>
      <span class="node-icon">{{ getIcon() }}</span>
      <span class="node-name">{{ node.name }}</span>
      <span class="node-size" v-if="node.type === 'file' && node.size">
        {{ formatSize(node.size) }}
      </span>
    </div>

    <!-- Children (if expanded directory) -->
    <div class="node-children" v-if="node.type === 'directory' && isExpanded && children.length > 0">
      <TreeNode
        v-for="child in children"
        :key="child.path"
        :node="child"
        @select="handleChildSelect"
      />
    </div>
  </div>
</template>

<style scoped>
.tree-node {
  user-select: none;
}

.node-row {
  display: flex;
  align-items: center;
  padding: 6px 8px;
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.15s;
}

.node-row:hover {
  background: #f5f5f7;
}

.expand-arrow {
  width: 16px;
  font-size: 10px;
  color: #86868b;
}

.expand-arrow.placeholder {
  width: 16px;
}

.node-icon {
  margin-right: 8px;
  font-size: 14px;
}

.node-name {
  flex: 1;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #1d1d1f;
}

.node-size {
  font-size: 11px;
  color: #86868b;
  margin-left: 8px;
}

.node-children {
  padding-left: 16px;
}
</style>