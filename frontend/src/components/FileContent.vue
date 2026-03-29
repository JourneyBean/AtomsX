<script setup lang="ts">
import { computed, ref } from 'vue'
import { VueMonacoEditor } from '@guolao/vue-monaco-editor'
import type { FileContent } from '@/types/file'

const props = defineProps<{
  workspaceId: string
  filePath: string | null
  content: FileContent | null
  loading: boolean
}>()

// Monaco Editor reference
const editorRef = ref<any>(null)
const monacoRef = ref<any>(null)

// Monaco Editor options
const editorOptions = {
  readOnly: true,
  minimap: { enabled: false },
  scrollBeyondLastLine: false,
  fontSize: 13,
  lineNumbers: 'on',
  theme: 'vs',
  automaticLayout: true,
  wordWrap: 'on',
}

// Compute content for Monaco
const editorContent = computed(() => {
  if (props.content?.type === 'text') {
    return props.content.content
  }
  return ''
})

// Compute language for Monaco
const editorLanguage = computed(() => {
  if (props.content?.type === 'text') {
    return props.content.language
  }
  return 'plaintext'
})

// Raw file URL for images and downloads
function getRawUrl(): string {
  return `/api/workspaces/${props.workspaceId}/files/${encodeURIComponent(props.filePath || '')}?raw=1`
}

// File name for download
function getFileName(): string {
  if (!props.filePath) return 'file'
  const parts = props.filePath.split('/')
  return parts[parts.length - 1]
}

// Format file size
function formatSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

// Handle Monaco Editor mount
function handleEditorMount(editor: any, monaco: any) {
  editorRef.value = editor
  monacoRef.value = monaco
}
</script>

<template>
  <div class="file-content">
    <!-- No file selected -->
    <div v-if="!filePath" class="empty-state">
      <p>Select a file to view its content</p>
    </div>

    <!-- Loading -->
    <div v-else-if="loading" class="loading-state">
      <p>Loading...</p>
    </div>

    <!-- Content based on type -->
    <div v-else-if="content" class="content-area">
      <!-- Text file - Monaco Editor -->
      <div v-if="content.type === 'text'" class="editor-container">
        <VueMonacoEditor
          v-model:value="editorContent"
          :language="editorLanguage"
          :options="editorOptions"
          @mount="handleEditorMount"
          class="monaco-editor"
        />
      </div>

      <!-- Image file -->
      <div v-else-if="content.type === 'image'" class="image-container">
        <img :src="getRawUrl()" :alt="getFileName()" class="preview-image" />
        <div class="image-info">
          <span>{{ content.mime_type }}</span>
          <span>{{ formatSize(content.size) }}</span>
        </div>
      </div>

      <!-- Too large file -->
      <div v-else-if="content.type === 'too_large'" class="message-container">
        <div class="message-icon">📦</div>
        <div class="message-text">
          <p class="message-title">文件过大，无法展示</p>
          <p class="message-detail">{{ formatSize(content.size) }}</p>
        </div>
      </div>

      <!-- Binary file -->
      <div v-else-if="content.type === 'binary'" class="message-container">
        <div class="message-icon">📁</div>
        <div class="message-text">
          <p class="message-title">无法打开此文件类型</p>
          <p class="message-detail">{{ formatSize(content.size) }}</p>
        </div>
        <a :href="getRawUrl()" :download="getFileName()" class="download-btn">
          ⬇️ Download
        </a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.file-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  color: #1d1d1f;
}

.empty-state,
.loading-state {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  color: #86868b;
  background: #fafafa;
}

.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Monaco Editor */
.editor-container {
  flex: 1;
  overflow: hidden;
}

.monaco-editor {
  height: 100%;
}

/* Image display */
.image-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  overflow: auto;
  background: #fafafa;
}

.preview-image {
  max-width: 100%;
  max-height: calc(100% - 40px);
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.image-info {
  display: flex;
  gap: 16px;
  margin-top: 12px;
  font-size: 12px;
  color: #86868b;
}

/* Message containers */
.message-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: #fafafa;
}

.message-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.message-text {
  text-align: center;
}

.message-title {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 8px;
  color: #1d1d1f;
}

.message-detail {
  font-size: 14px;
  color: #86868b;
}

.download-btn {
  margin-top: 16px;
  padding: 12px 24px;
  background: #4f46e5;
  color: white;
  border-radius: 8px;
  text-decoration: none;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}

.download-btn:hover {
  background: #4338ca;
}
</style>