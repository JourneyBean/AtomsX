<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { useNotificationStore } from '@/stores/notification'
import CodeView from '@/components/CodeView.vue'
import type { Workspace } from '@/types'

const route = useRoute()
const router = useRouter()
const sessionStore = useSessionStore()
const notificationStore = useNotificationStore()

const workspace = ref<Workspace | null>(null)
const newMessage = ref('')
const currentTaskId = ref<string | undefined>()
const workspaceId = route.params.id as string

// Tab state: 'preview' or 'code'
const activeTab = ref<'preview' | 'code'>('preview')

// Preview availability state
const previewReady = ref<boolean | null>(null) // null = not checked yet
const previewError = ref<string>('')
const checkingPreview = ref(false)

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

onMounted(async () => {
  await fetchWorkspace()
  await sessionStore.startSession(workspaceId)
  // Check preview availability if workspace is running and preview tab is active
  if (workspace.value?.status === 'running' && activeTab.value === 'preview') {
    checkPreviewAvailability()
  }
})

onUnmounted(() => {
  sessionStore.clearSession()
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

  await sessionStore.sendMessage(content)
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
</script>

<template>
  <div class="workspace-detail-view">
    <header class="header">
      <button @click="goBack" class="back-btn">← Back</button>
      <h1>{{ workspace?.name || 'Loading...' }}</h1>
      <span class="status" :class="workspace?.status">{{ workspace?.status }}</span>
    </header>

    <div class="content">
      <!-- Left panel: Chat -->
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
            @keyup.enter="sendMessage"
            :disabled="sessionStore.isStreaming"
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
            :disabled="!newMessage.trim()"
          >
            Send
          </button>
        </div>
      </div>

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
            <CodeView v-else :workspace-id="workspaceId" />
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
  background: #1a1a2e;
  color: #fff;
}

.header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 24px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.back-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: #fff;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
}

.header h1 {
  font-size: 1.25rem;
  flex: 1;
}

.status {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 0.85rem;
}

.status.running {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

.status.creating {
  background: rgba(234, 179, 8, 0.2);
  color: #eab308;
}

.status.error {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.content {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  overflow: hidden;
}

.chat-panel {
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(255, 255, 255, 0.1);
  overflow: hidden;
}

.messages {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  min-height: 0;
}

.message {
  margin-bottom: 16px;
  padding: 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.1);
}

.message.user {
  background: rgba(79, 70, 229, 0.2);
  margin-left: 48px;
}

.message.agent {
  margin-right: 48px;
}

.message-header {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 0.85rem;
}

.role {
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
}

.message-header .status {
  color: #f59e0b;
  background: transparent;
  padding: 0;
}

.message-content {
  white-space: pre-wrap;
  line-height: 1.5;
}

.empty-messages {
  text-align: center;
  color: rgba(255, 255, 255, 0.5);
  padding: 48px;
}

.input-section {
  display: flex;
  gap: 12px;
  padding: 16px 24px;
  background: rgba(255, 255, 255, 0.05);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.message-input {
  flex: 1;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  font-size: 1rem;
}

.message-input:focus {
  outline: none;
  border-color: rgba(79, 70, 229, 0.5);
}

.send-btn, .interrupt-btn {
  padding: 12px 24px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  font-weight: 500;
}

.send-btn {
  background: #4f46e5;
  color: white;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.interrupt-btn {
  background: #dc2626;
  color: white;
}

/* Right panel with tabs */
.right-panel {
  display: flex;
  flex-direction: column;
  background: #0f0f1a;
}

.tab-header {
  display: flex;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.tab-btn {
  padding: 8px 16px;
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.9rem;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.15s;
}

.tab-btn:hover {
  color: rgba(255, 255, 255, 0.9);
}

.tab-btn.active {
  color: #fff;
  background: rgba(79, 70, 229, 0.3);
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
  color: rgba(255, 255, 255, 0.5);
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
  color: #f59e0b;
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 8px;
}

.error-message {
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 12px;
}

.error-hint {
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.85rem;
  margin-bottom: 16px;
}

.retry-btn {
  padding: 10px 20px;
  background: #4f46e5;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  transition: background 0.15s;
}

.retry-btn:hover {
  background: #4338ca;
}
</style>