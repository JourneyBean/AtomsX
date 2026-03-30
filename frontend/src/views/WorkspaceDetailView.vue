<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { onFileOperation, offFileOperation } from '@/stores/session'
import { useNotificationStore } from '@/stores/notification'
import CodeView from '@/components/CodeView.vue'
import type { Workspace, HistorySession } from '@/types'
import { marked } from 'marked'

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
const previewToken = ref<string>('')
const previewTokenExpiry = ref<Date | null>(null)
const previewDomain = ref<string>('') // For cookie domain

// History state
const historySessions = ref<HistorySession[]>([])
const loadingHistory = ref(false)
const historyError = ref<string>('')
const isOffline = ref(false)
const isComposing = ref(false) // IME composition state
const currentHistorySessionId = ref<string | undefined>() // Track resumed session for sending new messages
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const messagesRef = ref<HTMLDivElement | null>(null) // Reference to messages container for auto-scroll

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
  // Disable pointer events on right panel to prevent iframe capturing mouse events
  const rightPanel = document.querySelector('.right-panel')
  if (rightPanel) {
    rightPanel.style.setProperty('pointer-events', 'none')
  }
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
  // Restore pointer events on right panel
  const rightPanel = document.querySelector('.right-panel')
  if (rightPanel) {
    rightPanel.style.setProperty('pointer-events', 'auto')
  }
}

const previewUrl = computed(() => {
  const baseUrl = workspace.value?.preview_url || ''
  if (!baseUrl) return ''

  // Build URL - authentication is handled via cookie set in generatePreviewToken()
  // Cookie is set on .preview.localhost domain, so iframe can access it
  let url = baseUrl

  // Upgrade HTTP to HTTPS if main page is HTTPS (avoid mixed-content blocking)
  if (window.location.protocol === 'https:' && url.startsWith('http://')) {
    url = url.replace('http://', 'https://')
  }

  // Append current page's port if not standard (80/443)
  const port = window.location.port
  if (port && port !== '80' && port !== '443') {
    // Insert port before the path (baseUrl is like http://xxx.preview.localhost)
    url = url.replace(/^http(s?):\/\/([^\/]+)(\/.*)?$/, `http$1://$2:${port}$3`)
  }

  return url
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

async function generatePreviewToken(): Promise<boolean> {
  if (!workspaceId) return false

  try {
    const response = await fetch(`/api/workspaces/${workspaceId}/preview-token/`, {
      method: 'POST',
      credentials: 'include',
    })

    if (response.ok) {
      const data = await response.json()
      previewToken.value = data.token
      previewTokenExpiry.value = new Date(data.expires_at)
      previewDomain.value = data.preview_domain || 'preview.localhost'

      // Set cookie for preview subdomain sharing
      // Domain: .preview.localhost allows workspace-id.preview.localhost to access
      const maxAge = Math.floor((data.expires_at_unix || 600))
      document.cookie = `preview_token=${data.token}; Path=/; Domain=.${previewDomain.value}; Max-Age=${maxAge}; SameSite=Lax`
      console.log('[Preview] Cookie set:', `preview_token=${data.token}; Path=/; Domain=.${previewDomain.value}; Max-Age=${maxAge}; SameSite=Lax`)

      return true
    } else if (response.status === 403) {
      previewError.value = 'Access denied to this workspace'
      return false
    } else {
      previewError.value = 'Failed to generate preview token'
      return false
    }
  } catch {
    previewError.value = 'Failed to generate preview token'
    return false
  }
}

async function checkPreviewAvailability() {
  if (!previewUrl.value) {
    previewReady.value = false
    previewError.value = 'Preview URL not available'
    return
  }

  checkingPreview.value = true

  // Generate a preview token first
  const tokenGenerated = await generatePreviewToken()
  if (!tokenGenerated) {
    previewReady.value = false
    checkingPreview.value = false
    return
  }

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

  // Scroll to bottom before sending (user should see their new message)
  scrollToBottom()

  const content = newMessage.value
  newMessage.value = ''

  // Reset textarea height after clearing
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto'
  }

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
    // Only check preview if not already ready or not yet checked
    if (previewReady.value !== true) {
      previewReady.value = null
      previewError.value = ''
      checkPreviewAvailability()
    }
  }
}

// Retry checking preview availability
function retryPreview() {
  previewReady.value = null
  previewError.value = ''
  previewToken.value = '' // Clear old token
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

  // Backend returns UTC time without 'Z' suffix, need to append it
  // so JS parses it as UTC instead of local time (8 hour difference for CN)
  let normalizedTimestamp = timestamp
  if (!timestamp.endsWith('Z') && !timestamp.includes('+') && !/-\d{2}:\d{2}$/.test(timestamp)) {
    normalizedTimestamp = timestamp + 'Z'
  }

  const date = new Date(normalizedTimestamp)
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
    // Send message on Enter, allow Shift+Enter for new line
    if (!event.shiftKey) {
      event.preventDefault()
      sendMessage()
    }
  }
}

function adjustTextareaHeight() {
  const textarea = textareaRef.value
  if (!textarea) return

  // Reset height to auto to get the correct scrollHeight
  textarea.style.height = 'auto'

  // Calculate line height (approximate, using 20px as base)
  const lineHeight = 20
  const maxHeight = lineHeight * 6 + 24 // 6 lines + padding

  // Set height based on content, capped at max height
  const newHeight = Math.min(textarea.scrollHeight, maxHeight)
  textarea.style.height = newHeight + 'px'
}

// Scroll to bottom immediately (used when sending new message)
function scrollToBottom() {
  const container = messagesRef.value
  if (!container) return
  container.scrollTop = container.scrollHeight
}

// Smart scroll: only scroll to bottom if user is near the bottom
function scrollToBottomIfNearBottom() {
  const container = messagesRef.value
  if (!container) return

  // Check if user is near the bottom (within 100px threshold)
  const threshold = 100
  const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < threshold

  if (isNearBottom) {
    // Scroll to bottom
    container.scrollTop = container.scrollHeight
  }
}

function renderMarkdown(content: string): string {
  if (!content) return ''
  return marked.parse(content, { breaks: true }) as string
}

// Watch messages for changes and auto-scroll
watch(
  () => ({ length: sessionStore.messages.length, content: sessionStore.messages.map(m => m.content).join('') }),
  (newVal, oldVal) => {
    nextTick(() => {
      // If new message added, force scroll to bottom
      if (newVal.length > oldVal?.length) {
        scrollToBottom()
      } else {
        // Otherwise only scroll if user is near bottom
        scrollToBottomIfNearBottom()
      }
    })
  }
)
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
          <div class="messages" ref="messagesRef">
            <div
              v-for="(msg, idx) in sessionStore.messages"
              :key="idx"
              :class="['message', msg.role]"
            >
              <div class="message-header">
                <span class="role">{{ msg.role === 'user' ? 'You' : 'Agent' }}</span>
                <span class="status" v-if="msg.status !== 'complete'">{{ msg.status }}</span>
              </div>
              <div class="message-content" v-if="msg.role === 'user'">{{ msg.content }}</div>
              <div class="message-content markdown-body" v-else v-html="renderMarkdown(msg.content)"></div>
            </div>

            <div v-if="sessionStore.messages.length === 0" class="empty-messages">
              Start a conversation with the Agent...
            </div>
          </div>

          <div class="input-section">
            <textarea
              v-model="newMessage"
              placeholder="Type a message..."
              class="message-input"
              rows="1"
              @keydown="handleKeyDown"
              @compositionstart="isComposing = true"
              @compositionend="isComposing = false"
              @input="adjustTextareaHeight"
              ref="textareaRef"
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
          <button
            v-if="activeTab === 'preview' && previewToken"
            @click="retryPreview"
            class="refresh-token-btn"
            title="Refresh preview token"
          >
            ⟳
          </button>
        </div>

        <!-- Tab content -->
        <div class="tab-content">
          <!-- Preview Tab - use v-show to preserve iframe state -->
          <div v-show="activeTab === 'preview'" class="preview-container">
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
          <div v-show="activeTab === 'code'" class="code-container">
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
  box-sizing: border-box;
  overflow: hidden;
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
  margin-right: 0;
  background: transparent;
  padding: 0;
  border-radius: 0;
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

.message-content.markdown-body {
  white-space: normal;
}

.message-content.markdown-body p {
  margin: 0 0 12px 0;
}

.message-content.markdown-body p:last-child {
  margin-bottom: 0;
}

.message-content.markdown-body code {
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.9em;
}

.message-content.markdown-body pre {
  background: #282c34;
  color: #abb2bf;
  padding: 12px 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 12px 0;
}

.message-content.markdown-body pre code {
  background: transparent;
  padding: 0;
  color: inherit;
}

.message-content.markdown-body ul,
.message-content.markdown-body ol {
  margin: 8px 0;
  padding-left: 24px;
}

.message-content.markdown-body li {
  margin: 4px 0;
}

.message-content.markdown-body strong {
  font-weight: 600;
}

.message-content.markdown-body a {
  color: #4f46e5;
  text-decoration: none;
}

.message-content.markdown-body a:hover {
  text-decoration: underline;
}

.empty-messages {
  text-align: center;
  color: #86868b;
  padding: 48px;
}

.input-section {
  display: flex;
  align-items: flex-end;
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
  line-height: 1.4;
  transition: all 0.15s;
  resize: none;
  min-height: 44px;
  max-height: 144px;
  overflow-y: auto;
  font-family: inherit;
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

.refresh-token-btn {
  margin-left: auto;
  padding: 6px 12px;
  background: #f5f5f7;
  border: 1px solid #d2d2d7;
  border-radius: 6px;
  cursor: pointer;
  font-size: 1rem;
  color: #1d1d1f;
  transition: all 0.15s;
}

.refresh-token-btn:hover {
  background: #e8e8ed;
  border-color: #86868b;
}

.tab-content {
  flex: 1;
  overflow: hidden;
  position: relative;
}

.preview-container,
.code-container {
  position: absolute;
  inset: 0;
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