import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Session, Message } from '@/types'

export const useSessionStore = defineStore('session', () => {
  const currentSession = ref<Session | null>(null)
  const messages = ref<Message[]>([])
  const isStreaming = ref(false)
  const eventSource = ref<EventSource | null>(null)

  async function startSession(workspaceId: string): Promise<Session | null> {
    try {
      const response = await fetch(`/api/sessions/?workspace_id=${workspaceId}`, {
        method: 'POST',
        credentials: 'include',
      })
      if (response.ok) {
        currentSession.value = await response.json()
        messages.value = currentSession.value.messages || []
        return currentSession.value
      }
    } catch (error) {
      console.error('Failed to start session:', error)
    }
    return null
  }

  async function loadSession(sessionId: string): Promise<Session | null> {
    try {
      const response = await fetch(`/api/sessions/${sessionId}/`, {
        credentials: 'include',
      })
      if (response.ok) {
        currentSession.value = await response.json()
        messages.value = currentSession.value.messages || []
        return currentSession.value
      }
    } catch (error) {
      console.error('Failed to load session:', error)
    }
    return null
  }

  async function sendMessage(content: string): Promise<void> {
    if (!currentSession.value || isStreaming.value) return

    // Add user message locally
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
      status: 'complete',
    }
    messages.value.push(userMessage)

    // Create placeholder for agent response
    const agentMessage: Message = {
      id: crypto.randomUUID(),
      role: 'agent',
      content: '',
      timestamp: new Date().toISOString(),
      status: 'streaming',
    }
    messages.value.push(agentMessage)

    isStreaming.value = true

    // Send message to backend
    let taskId: string | undefined
    try {
      const response = await fetch(`/api/sessions/${currentSession.value.id}/messages/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ content }),
      })
      if (response.ok) {
        const data = await response.json()
        taskId = data.task_id
      }
    } catch (error) {
      console.error('Failed to send message:', error)
    }

    // Connect to SSE stream
    const sessionId = currentSession.value.id
    connectToStream(sessionId, agentMessage, taskId)
  }

  function connectToStream(sessionId: string, agentMessage: Message, taskId?: string) {
    // Close existing connection
    if (eventSource.value) {
      eventSource.value.close()
    }

    const url = `/api/sessions/${sessionId}/stream/`
    eventSource.value = new EventSource(url)

    eventSource.value.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'content') {
        agentMessage.content += data.content
      } else if (data.type === 'done') {
        agentMessage.status = 'complete'
        closeStream()
      } else if (data.type === 'error') {
        agentMessage.status = 'error'
        agentMessage.content = data.error || 'An error occurred'
        closeStream()
      } else if (data.type === 'interrupted') {
        agentMessage.status = 'interrupted'
        closeStream()
      }
    }

    eventSource.value.onerror = () => {
      if (agentMessage.status === 'streaming') {
        agentMessage.status = 'error'
        agentMessage.content = 'Connection lost'
      }
      closeStream()
    }
  }

  async function interrupt(taskId?: string): Promise<void> {
    if (!currentSession.value || !taskId) return

    try {
      await fetch(`/api/sessions/${currentSession.value.id}/interrupt/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ task_id: taskId }),
      })
    } catch (error) {
      console.error('Failed to interrupt:', error)
    }

    closeStream()
  }

  function closeStream() {
    isStreaming.value = false
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }
  }

  function clearSession() {
    currentSession.value = null
    messages.value = []
    closeStream()
  }

  return {
    currentSession,
    messages,
    isStreaming,
    startSession,
    loadSession,
    sendMessage,
    interrupt,
    closeStream,
    clearSession,
  }
})