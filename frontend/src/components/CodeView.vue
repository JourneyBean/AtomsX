<script setup lang="ts">
import FileTree from '@/components/FileTree.vue'
import FileContent from '@/components/FileContent.vue'
import { useFileBrowser } from '@/composables/useFileBrowser'

const props = defineProps<{
  workspaceId: string
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
</script>

<template>
  <div class="code-view">
    <!-- Left panel: File Tree -->
    <div class="tree-panel">
      <FileTree
        :workspace-id="workspaceId"
        @select="handleFileSelect"
      />
    </div>

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
  display: grid;
  grid-template-columns: 240px 1fr;
  height: 100%;
  overflow: hidden;
}

.tree-panel {
  border-right: 1px solid rgba(255, 255, 255, 0.1);
  overflow: auto;
}

.content-panel {
  overflow: hidden;
}
</style>