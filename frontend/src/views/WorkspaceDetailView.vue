<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSessionStore } from '@/stores/session'
import type { Workspace } from '@/types'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const sessionStore = useSessionStore()

const workspace = ref<Workspace | null>(null)
const newMessage = ref('')
const currentTaskId = ref<string | undefined>()
const workspaceId = route.params.id as string

const previewUrl = computed(() => {
  if (workspace.value?.status === 'running') {
    return `http://${workspaceId}.preview.local`
  }
  return ''
})

onMounted(async () => {
  await fetchWorkspace()
  await sessionStore.startSession(workspaceId)
})

onUnmounted(() => {
  sessionStore.clearSession()
})

async function fetchWorkspace() {
  const response = await fetch(`/api/workspaces/${workspaceId}/`, {
    credentials: 'include',
  })
  if (response.ok) {
    workspace.value = await response.json()
  } else {
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

      <!-- Right panel: Preview -->
      <div class="preview-panel">
        <div v-if="workspace?.status !== 'running'" class="preview-placeholder">
          <p>Workspace is {{ workspace?.status }}...</p>
        </div>
        <iframe
          v-else
          :src="previewUrl"
          class="preview-frame"
          sandbox="allow-scripts allow-same-origin allow-forms"
        />
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
}

.messages {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
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

.preview-panel {
  display: flex;
  flex-direction: column;
  background: #0f0f1a;
}

.preview-placeholder {
  flex: 1;
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
</style>