<script setup lang="ts">
import { ref, onMounted, provide } from 'vue'
import type { FileNode } from '@/types/file'
import { useFileBrowser } from '@/composables/useFileBrowser'

const props = defineProps<{
  workspaceId: string
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
  rootNodes.value = await fetchTree()
})

// Handle node click from child component
function handleSelect(path: string) {
  emit('select', path)
}
</script>

<template>
  <div class="file-tree">
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
  background: #1a1a2e;
  color: #fff;
  overflow: auto;
}

.loading,
.error,
.empty-tree {
  padding: 16px;
  text-align: center;
  color: rgba(255, 255, 255, 0.5);
}

.error {
  color: #ef4444;
}

.tree-content {
  padding: 8px;
}
</style>