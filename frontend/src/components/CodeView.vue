<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import FileTree from '@/components/FileTree.vue'
import FileContent from '@/components/FileContent.vue'
import { useFileBrowser } from '@/composables/useFileBrowser'

const props = defineProps<{
  workspaceId: string
  refreshTrigger?: number
}>()

// File browser state
const {
  selectedPath,
  fileContent,
  loading,
  selectFile,
} = useFileBrowser(props.workspaceId)

// Handle file selection
async function handleFileSelect(path: string) {
  await selectFile(path)
}

// Resizable file tree
const treeWidth = ref(240)
const isDragging = ref(false)

function startDrag(e: MouseEvent) {
  isDragging.value = true
  e.preventDefault()
}

function handleMouseMove(e: MouseEvent) {
  if (!isDragging.value) return
  const container = document.querySelector('.code-view')
  if (!container) return
  const rect = container.getBoundingClientRect()
  const newWidth = e.clientX - rect.left
  treeWidth.value = Math.max(150, Math.min(500, newWidth))
}

function handleMouseUp() {
  isDragging.value = false
}

onMounted(() => {
  window.addEventListener('mousemove', handleMouseMove)
  window.addEventListener('mouseup', handleMouseUp)
})

onUnmounted(() => {
  window.removeEventListener('mousemove', handleMouseMove)
  window.removeEventListener('mouseup', handleMouseUp)
})
</script>

<template>
  <div class="code-view">
    <!-- Left panel: File Tree -->
    <div class="tree-panel" :style="{ width: treeWidth + 'px' }">
      <FileTree
        :workspace-id="workspaceId"
        :refresh-trigger="refreshTrigger"
        @select="handleFileSelect"
      />
    </div>

    <!-- Resizer -->
    <div class="resizer" @mousedown="startDrag"></div>

    <!-- Right panel: File Content -->
    <div class="content-panel">
      <FileContent
        :workspace-id="workspaceId"
        :file-path="selectedPath"
        :content="fileContent"
        :loading="loading"
      />
    </div>
  </div>
</template>

<style scoped>
.code-view {
  display: flex;
  height: 100%;
  overflow: hidden;
  background: #fff;
}

.resizer {
  width: 4px;
  background: transparent;
  cursor: col-resize;
  flex-shrink: 0;
  transition: background 0.15s;
}

.resizer:hover {
  background: #4f46e5;
}

.tree-panel {
  border-right: none;
  overflow: auto;
  flex-shrink: 0;
}

.content-panel {
  overflow: hidden;
  flex: 1;
  min-width: 0;
  background: #fafafa;
}
</style>