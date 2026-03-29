<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { onFileOperation, offFileOperation } from '@/stores/session'
import { useNotificationStore } from '@/stores/notification'
import CodeView from '@/components/CodeView.vue'
import type { Workspace, HistorySession } from '@/types'

const route = useRoute()
const router = useRouter()
const sessionStore = useSessionStore()
const notificationStore = useNotificationStore()

const workspace = ref<Workspace | null>(null)
const newMessage = ref('')
const currentTaskId = ref<string | undefined>()
const workspaceId = route.params.id as string

// Tab state: 'preview' or 'code'
const activeTab = ref<'preview' | 'code'>('code')

// Preview availability state
const previewReady = ref<boolean | null>(null) // null = not checked yet
const previewError = ref<string>('')
const checkingPreview = ref(false)

// History state
const historySessions = ref<HistorySession[]>([])
const loadingHistory = ref(false)
const historyError = ref<string>('')
const isOffline = ref(false)
const isComposing = ref(false) // IME composition state
const currentHistorySessionId = ref<string | undefined>() // Track resumed session for sending new messages

// File tree refresh trigger
const fileRefreshTrigger = ref(0)

// Panel widths for resizable layout
const leftPanelWidth = ref(600)
const historyWidth = ref(180)
const isDraggingLeftPanel = ref(false)
const isDraggingHistory = ref(false)

// Resize handlers
function startDragLeftPanel(e: MouseEvent) {
  isDraggingLeftPanel.value = true
  e.preventDefault()
}

function startDragHistory(e: MouseEvent) {
  isDraggingHistory.value = true
  e.preventDefault()
}

function handleMouseMove(e: MouseEvent) {
  const container = document.querySelector('.content')
  if (!container) return
  const rect = container.getBoundingClientRect()

  if (isDraggingLeftPanel.value) {
    const newWidth = e.clientX - rect.left
    leftPanelWidth.value = Math.max(400, Math.min(1000, newWidth))
  }

  if (isDraggingHistory.value) {
    const leftPanel = document.querySelector('.left-panel')
    if (!leftPanel) return
    const leftRect = leftPanel.getBoundingClientRect()
    const newWidth = e.clientX - leftRect.left
    historyWidth.value = Math.max(120, Math.min(350, newWidth))
  }
}

function handleMouseUp() {
  isDraggingLeftPanel.value = false
  isDraggingHistory.value = false
}

const previewUrl = computed(() => {
  const baseUrl = workspace.value?.preview_url || ''
  if (!baseUrl) return ''
  // Append current page's port if not standard (80/443)
  const port = window.location.port
  if (port && port !== '80' && port !== '443') {
    // Insert port before the path (baseUrl is like http://xxx.preview.localhost)
    return baseUrl.replace(/^http(s?):\/\/([^\/]+)(\/.*)?$/, `http$1://$2:${port}$3`)
  }
  return baseUrl
})

// Computed status display
const displayStatus = computed(() => {
  if (isOffline.value) return 'offline'
  return workspace.value?.status || 'loading'
})

onMounted(async () => {
  await fetchWorkspace()
  await sessionStore.startSession(workspaceId)
  await fetchHistoryList()
  // Preview availability is checked when user switches to preview tab

  // Set up file operation callback for auto-refresh
  onFileOperation(() => {
    fileRefreshTrigger.value++
  })

  // Add resize event listeners
  window.addEventListener('mousemove', handleMouseMove)
  window.addEventListener('mouseup', handleMouseUp)
})

onUnmounted(() => {
  sessionStore.clearSession()
  offFileOperation()

  // Remove resize event listeners
  window.removeEventListener('mousemove', handleMouseMove)
  window.removeEventListener('mouseup', handleMouseUp)
})

async function checkPreviewAvailability() {
  if (!previewUrl.value) {
    previewReady.value = false
    previewError.value = 'Preview URL not available'
    return
  }

  checkingPreview.value = true

  // Try normal fetch - if CORS allows, we can read the status code
  try {
    const response = await fetch(previewUrl.value, {
      method: 'GET',
    })
    // Successfully read response - check status
    if (response.status === 503) {
      previewReady.value = false
      previewError.value = 'Preview service is starting up. Please wait a moment and try again.'
    } else if (!response.ok) {
      previewReady.value = false
      previewError.value = `Preview unavailable (status: ${response.status})`
    } else {
      previewReady.value = true
      previewError.value = ''
    }
  } catch {
    // Fetch threw an error - could be CORS blocked or network unreachable
    // We can't determine the actual status, so let iframe try loading
    // The iframe will show browser's error page if it fails
    previewReady.value = true
    previewError.value = ''
  } finally {
    checkingPreview.value = false
  }
}

async function fetchWorkspace() {
  try {
    const response = await fetch(`/api/workspaces/${workspaceId}/`, {
      credentials: 'include',
    })
    if (response.ok) {
      workspace.value = await response.json()
    } else {
      notificationStore.showError('Failed to load workspace')
      router.push({ name: 'workspaces' })
    }
  } catch {
    notificationStore.showError('Failed to load workspace')
    router.push({ name: 'workspaces' })
  }
}

async function sendMessage() {
  if (!newMessage.value.trim() || sessionStore.isStreaming) return

  const content = newMessage.value
  newMessage.value = ''

  // Check if we're in a resumed session
  if (currentHistorySessionId.value) {
    // Save current history messages before starting session
    const historyMessages = [...sessionStore.messages]

    // Need to start a session first if not already started
    if (!sessionStore.currentSession) {
      await sessionStore.startSession(workspaceId)
      // Restore history messages after session started
      sessionStore.messages = historyMessages
    }

    // Resume the session with the new message
    await sessionStore.resumeSession(currentHistorySessionId.value, content)
    currentHistorySessionId.value = undefined // Clear after sending
    // Refresh history list after message sent
    await fetchHistoryList()
  } else {
    // Normal new session message
    await sessionStore.sendMessage(content)
    // Refresh history list after message sent
    await fetchHistoryList()
  }
}

async function handleInterrupt() {
  await sessionStore.interrupt(currentTaskId.value)
}

function goBack() {
  router.push({ name: 'workspaces' })
}

function switchTab(tab: 'preview' | 'code') {
  activeTab.value = tab
  if (tab === 'preview' && workspace.value?.status === 'running') {
    // Reset and check preview availability when switching to preview tab
    previewReady.value = null
    previewError.value = ''
    checkPreviewAvailability()
  }
}

// Retry checking preview availability
function retryPreview() {
  previewReady.value = null
  previewError.value = ''
  checkPreviewAvailability()
}

// Handle iframe load errors
function onIframeError() {
  previewReady.value = false
  previewError.value = 'Preview failed to load. The workspace preview server may not be ready.'
}

// History functions
async function fetchHistoryList() {
  if (workspace.value?.status !== 'running') return

  loadingHistory.value = true
  historyError.value = ''

  try {
    const response = await fetch(`/api/workspaces/${workspaceId}/history/`, {
      credentials: 'include',
    })

    if (response.ok) {
      const data = await response.json()
      historySessions.value = data.sessions || []
      isOffline.value = false
    } else if (response.status === 503) {
      isOffline.value = true
      historyError.value = 'Workspace client offline'
    } else {
      historyError.value = 'Failed to load history'
    }
  } catch {
    historyError.value = 'Failed to load history'
  } finally {
    loadingHistory.value = false
  }
}

async function startNewConversation() {
  // Clear current session and history session ID, start fresh
  currentHistorySessionId.value = undefined
  sessionStore.clearSession()
  await sessionStore.startSession(workspaceId)
}

async function resumeHistory(historySession: HistorySession) {
  if (sessionStore.isStreaming) return

  // Clear current messages first
  sessionStore.clearSession()

  // Track the history session ID for sending new messages later
  currentHistorySessionId.value = historySession.history_session_id

  // Fetch messages from this history session (NOT calling Claude SDK)
  try {
    const response = await fetch(
      `/api/workspaces/${workspaceId}/history/${historySession.history_session_id}/`,
      { credentials: 'include' }
    )

    if (response.ok) {
      const data = await response.json()
      // Display the messages in chat panel
      sessionStore.messages = data.messages || []
      isOffline.value = false
    } else if (response.status === 503) {
      isOffline.value = true
      notificationStore.showError('Workspace client offline')
    } else {
      notificationStore.showError('Failed to load history messages')
    }
  } catch {
    notificationStore.showError('Failed to load history messages')
  }
}

function formatRelativeTime(timestamp: string): string {
  if (!timestamp) return ''

  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 1) return '刚刚'
  if (diffMins < 60) return `${diffMins}分钟前`
  if (diffHours < 24) return `${diffHours}小时前`
  if (diffDays < 7) return `${diffDays}天前`

  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function handleKeyDown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !isComposing.value) {
    sendMessage()
  }
}
</script>

<template>
  <div class="workspace-detail-view">
    <header class="header">
      <button @click="goBack" class="back-btn">← Back</button>
      <h1>{{ workspace?.name || 'Loading...' }}</h1>
      <span class="status" :class="displayStatus">{{ displayStatus }}</span>
    </header>

    <div class="content">
      <!-- Left panel: History + Chat combined -->
      <div class="left-panel" :style="{ width: leftPanelWidth + 'px' }">
        <!-- History sidebar -->
        <div class="history-sidebar" :style="{ width: historyWidth + 'px' }">
          <button @click="startNewConversation" class="new-chat-btn">
            + 新对话
          </button>

          <div class="history-list">
            <div v-if="loadingHistory" class="history-loading">
              加载中...
            </div>
            <div v-else-if="isOffline" class="history-error">
              <span>离线状态</span>
              <button @click="fetchHistoryList" class="retry-history-btn">重试</button>
            </div>
            <div v-else-if="historyError" class="history-error">
              {{ historyError }}
            </div>
            <div v-else-if="historySessions.length === 0" class="history-empty">
              暂无历史对话
            </div>
            <div
              v-else
              v-for="session in historySessions"
              :key="session.history_session_id"
              class="history-item"
              @click="resumeHistory(session)"
            >
              <div class="history-title">{{ session.first_message || '无标题' }}</div>
              <div class="history-time">{{ formatRelativeTime(session.last_activity) }}</div>
            </div>
          </div>

          <!-- Internal resizer for history -->
          <div class="history-resizer" @mousedown="startDragHistory"></div>
        </div>

        <!-- Chat panel -->
        <div class="chat-panel">
          <div class="messages">
            <div
              v-for="(msg, idx) in sessionStore.messages"
              :key="idx"
              :class="['message', msg.role]"
            >
              <div class="message-header">
                <span class="role">{{ msg.role === 'user' ? 'You' : 'Agent' }}</span>
                <span class="status" v-if="msg.status !== 'complete'">{{ msg.status }}</span>
              </div>
              <div class="message-content">{{ msg.content }}</div>
            </div>

            <div v-if="sessionStore.messages.length === 0" class="empty-messages">
              Start a conversation with the Agent...
            </div>
          </div>

          <div class="input-section">
            <input
              v-model="newMessage"
              placeholder="Type a message..."
              class="message-input"
              @keydown="handleKeyDown"
              @compositionstart="isComposing = true"
              @compositionend="isComposing = false"
              :disabled="sessionStore.isStreaming || isOffline"
            />
            <button
              v-if="sessionStore.isStreaming"
              @click="handleInterrupt"
              class="interrupt-btn"
            >
              Stop
            </button>
            <button
              v-else
              @click="sendMessage"
              class="send-btn"
              :disabled="!newMessage.trim() || isOffline"
            >
              Send
            </button>
          </div>
        </div>
      </div>

      <!-- Resizer between left panel and right panel -->
      <div class="resizer" @mousedown="startDragLeftPanel"></div>

      <!-- Right panel: Preview/Code with Tabs -->
      <div class="right-panel">
        <!-- Tab header -->
        <div class="tab-header">
          <button
            :class="['tab-btn', { active: activeTab === 'preview' }]"
            @click="switchTab('preview')"
          >
            Preview
          </button>
          <button
            :class="['tab-btn', { active: activeTab === 'code' }]"
            @click="switchTab('code')"
          >
            Code
          </button>
        </div>

        <!-- Tab content -->
        <div class="tab-content">
          <!-- Preview Tab -->
          <div v-if="activeTab === 'preview'" class="preview-container">
            <div v-if="workspace?.status !== 'running'" class="preview-placeholder">
              <p>Workspace is {{ workspace?.status }}...</p>
            </div>
            <div v-else-if="checkingPreview" class="preview-placeholder">
              <p>Checking preview availability...</p>
            </div>
            <div v-else-if="previewReady === false" class="preview-placeholder preview-error">
              <div class="error-content">
                <p class="error-title">Preview Not Ready</p>
                <p class="error-message">{{ previewError || 'The workspace preview is starting up. This usually takes a few seconds.' }}</p>
                <p class="error-hint">Tip: If you just created this workspace, wait a moment and try again.</p>
                <button @click="retryPreview" class="retry-btn">Retry</button>
              </div>
            </div>
            <iframe
              v-else-if="previewReady === true"
              :src="previewUrl"
              class="preview-frame"
              sandbox="allow-scripts allow-same-origin allow-forms"
              @error="onIframeError"
            />
            <!-- Default state when workspace is running but not yet checked -->
            <div v-else class="preview-placeholder">
              <p>Loading preview...</p>
            </div>
          </div>

          <!-- Code Tab -->
          <div v-if="activeTab === 'code'" class="code-container">
            <div v-if="workspace?.status !== 'running'" class="code-placeholder">
              <p>Workspace is {{ workspace?.status }}...</p>
            </div>
            <CodeView v-else :workspace-id="workspaceId" :refresh-trigger="fileRefreshTrigger" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.workspace-detail-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f5f7;
  color: #1d1d1f;
  padding: 12px;
  gap: 12px;
}

.header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 20px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.back-btn {
  background: transparent;
  border: 1px solid #d2d2d7;
  color: #1d1d1f;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.back-btn:hover {
  background: #f5f5f7;
  border-color: #86868b;
}

.header h1 {
  font-size: 1.15rem;
  font-weight: 600;
  flex: 1;
}

.status {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 500;
}

.status.running {
  background: #d1fae5;
  color: #059669;
}

.status.creating {
  background: #fef3c7;
  color: #d97706;
}

.status.error {
  background: #fee2e2;
  color: #dc2626;
}

.status.offline {
  background: #f3f4f6;
  color: #6b7280;
}

.content {
  flex: 1;
  display: flex;
  overflow: hidden;
  gap: 0;
}

/* Left panel: History + Chat combined */
.left-panel {
  display: flex;
  flex-shrink: 0;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

/* Main resizer between left and right panels */
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

/* History Sidebar (inside left panel) */
.history-sidebar {
  display: flex;
  flex-direction: column;
  background: #fafafa;
  overflow: hidden;
  flex-shrink: 0;
  position: relative;
}

.history-resizer {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  cursor: col-resize;
  background: transparent;
  transition: background 0.15s;
}

.history-resizer:hover {
  background: #4f46e5;
}

.new-chat-btn {
  margin: 12px;
  padding: 10px 16px;
  background: #4f46e5;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
  font-size: 0.9rem;
  transition: background 0.15s;
}

.new-chat-btn:hover {
  background: #4338ca;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.history-loading,
.history-error,
.history-empty {
  text-align: center;
  padding: 24px 12px;
  color: #86868b;
  font-size: 0.85rem;
}

.history-error {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.retry-history-btn {
  padding: 6px 12px;
  background: #f5f5f7;
  color: #1d1d1f;
  border: 1px solid #d2d2d7;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
}

.retry-history-btn:hover {
  background: #e8e8ed;
}

.history-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
  margin-bottom: 4px;
}

.history-item:hover {
  background: #f5f5f7;
}

.history-title {
  font-size: 0.85rem;
  color: #1d1d1f;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.history-time {
  font-size: 0.75rem;
  color: #86868b;
}

/* Chat panel (inside left panel) */
.chat-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex: 1;
  min-width: 0;
}

.messages {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  min-height: 0;
}

.message {
  margin-bottom: 16px;
  padding: 12px 16px;
  border-radius: 12px;
  background: #f5f5f7;
}

.message.user {
  background: #eef2ff;
  margin-left: 48px;
}

.message.agent {
  margin-right: 48px;
  background: #f5f5f7;
}

.message-header {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 0.85rem;
}

.role {
  color: #86868b;
  font-weight: 500;
}

.message-header .status {
  color: #d97706;
  background: transparent;
  padding: 0;
  font-size: 0.8rem;
}

.message-content {
  white-space: pre-wrap;
  line-height: 1.5;
  color: #1d1d1f;
}

.empty-messages {
  text-align: center;
  color: #86868b;
  padding: 48px;
}

.input-section {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  background: #fff;
  border-top: 1px solid #e5e5ea;
  border-radius: 0 0 12px 12px;
}

.message-input {
  flex: 1;
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid #d2d2d7;
  background: #f5f5f7;
  color: #1d1d1f;
  font-size: 1rem;
  transition: all 0.15s;
}

.message-input:focus {
  outline: none;
  border-color: #4f46e5;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.send-btn, .interrupt-btn {
  padding: 12px 24px;
  border-radius: 10px;
  border: none;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.15s;
}

.send-btn {
  background: #4f46e5;
  color: white;
}

.send-btn:hover:not(:disabled) {
  background: #4338ca;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.interrupt-btn {
  background: #fee2e2;
  color: #dc2626;
}

.interrupt-btn:hover {
  background: #fecaca;
}

/* Right panel with tabs */
.right-panel {
  display: flex;
  flex-direction: column;
  background: #fff;
  flex: 1;
  min-width: 0;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.tab-header {
  display: flex;
  padding: 8px 12px;
  background: #fff;
  border-bottom: 1px solid #e5e5ea;
  gap: 4px;
}

.tab-btn {
  padding: 8px 16px;
  background: transparent;
  border: none;
  color: #86868b;
  font-size: 0.9rem;
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.15s;
}

.tab-btn:hover {
  color: #1d1d1f;
  background: #f5f5f7;
}

.tab-btn.active {
  color: #4f46e5;
  background: #eef2ff;
  font-weight: 500;
}

.tab-content {
  flex: 1;
  overflow: hidden;
}

.preview-container,
.code-container {
  height: 100%;
}

.preview-placeholder,
.code-placeholder {
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  color: #86868b;
  background: #fafafa;
}

.preview-frame {
  width: 100%;
  height: 100%;
  border: none;
  background: #fff;
}

.preview-error {
  flex-direction: column;
  gap: 16px;
}

.error-content {
  text-align: center;
  padding: 24px;
  max-width: 400px;
}

.error-title {
  color: #d97706;
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 8px;
}

.error-message {
  color: #515154;
  margin-bottom: 12px;
}

.error-hint {
  color: #86868b;
  font-size: 0.85rem;
  margin-bottom: 16px;
}

.retry-btn {
  padding: 10px 20px;
  background: #4f46e5;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
  transition: background 0.15s;
}

.retry-btn:hover {
  background: #4338ca;
}
</style>