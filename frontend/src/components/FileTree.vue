<script setup lang="ts">
import { ref, onMounted, watch, provide } from 'vue'
import type { FileNode } from '@/types/file'
import { useFileBrowser } from '@/composables/useFileBrowser'
import TreeNode from '@/components/TreeNode.vue'

const props = defineProps<{
  workspaceId: string
  refreshTrigger?: number
}>()

const emit = defineEmits<{
  select: [path: string]
}>()

const {
  expandedPaths,
  treeCache,
  loading,
  error,
  fetchTree,
  toggleDirectory,
} = useFileBrowser(props.workspaceId)

// Provide context for recursive TreeNode
provide('expandedPaths', expandedPaths)
provide('treeCache', treeCache)
provide('toggleDirectory', toggleDirectory)
provide('workspaceId', props.workspaceId)

// Root nodes
const rootNodes = ref<FileNode[]>([])

// Load root tree on mount
onMounted(async () => {
  await refreshTree()
})

// Watch refreshTrigger prop to auto-refresh
watch(() => props.refreshTrigger, async (newVal, oldVal) => {
  if (newVal !== oldVal && newVal !== undefined) {
    await refreshTree()
  }
})

// Refresh tree (clear cache and reload)
async function refreshTree() {
  treeCache.clear()
  rootNodes.value = await fetchTree()
}

// Handle node click from child component
function handleSelect(path: string) {
  emit('select', path)
}
</script>

<template>
  <div class="file-tree">
    <!-- Header with refresh button -->
    <div class="tree-header">
      <span class="header-title">Files</span>
      <button @click="refreshTree" class="refresh-btn" :disabled="loading" title="Refresh">
        ↻
      </button>
    </div>

    <!-- Loading indicator -->
    <div v-if="loading && rootNodes.length === 0" class="loading">
      Loading...
    </div>

    <!-- Error message -->
    <div v-if="error" class="error">
      {{ error }}
    </div>

    <!-- Tree nodes -->
    <div class="tree-content">
      <!-- Empty state -->
      <div v-if="!loading && rootNodes.length === 0" class="empty-tree">
        No files
      </div>

      <TreeNode
        v-for="node in rootNodes"
        :key="node.path"
        :node="node"
        @select="handleSelect"
      />
    </div>
  </div>
</template>

<style scoped>
.file-tree {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fafafa;
  color: #1d1d1f;
  overflow: auto;
}

.tree-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #e5e5ea;
  background: #fff;
}

.header-title {
  font-size: 12px;
  font-weight: 600;
  color: #86868b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.refresh-btn {
  background: transparent;
  border: 1px solid #d2d2d7;
  color: #86868b;
  cursor: pointer;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 6px;
  transition: all 0.15s;
}

.refresh-btn:hover:not(:disabled) {
  color: #1d1d1f;
  background: #f5f5f7;
  border-color: #86868b;
}

.refresh-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.loading,
.error,
.empty-tree {
  padding: 16px;
  text-align: center;
  color: #86868b;
}

.error {
  color: #dc2626;
}

.tree-content {
  padding: 8px;
}
</style>