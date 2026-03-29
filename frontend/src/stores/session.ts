import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Session, Message } from '@/types'
import { useNotificationStore } from '@/stores/notification'

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
        messages.value = currentSession.value?.messages || []
        return currentSession.value
      } else {
        const notificationStore = useNotificationStore()
        notificationStore.showError('Failed to start session')
      }
    } catch {
      const notificationStore = useNotificationStore()
      notificationStore.showError('Failed to start session')
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
        messages.value = currentSession.value?.messages || []
        return currentSession.value
      } else {
        const notificationStore = useNotificationStore()
        notificationStore.showError('Failed to load session')
      }
    } catch {
      const notificationStore = useNotificationStore()
      notificationStore.showError('Failed to load session')
    }
    return null
  }

  async function sendMessage(content: string): Promise<void> {
    console.log('[Session] sendMessage called:', content)
    if (!currentSession.value || isStreaming.value) {
      console.log('[Session] Early return: no session or already streaming')
      return
    }

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
      console.log('[Session] Sending POST to messages endpoint...')
      const response = await fetch(`/api/sessions/${currentSession.value.id}/messages/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ content }),
      })
      console.log('[Session] POST response:', response.status)
      if (response.ok) {
        const data = await response.json()
        console.log('[Session] POST data:', data)
        taskId = data.task_id
      } else {
        const notificationStore = useNotificationStore()
        notificationStore.showError('Failed to send message')
        agentMessage.status = 'error'
        agentMessage.content = 'Failed to send message'
        closeStream()
        return
      }
    } catch (err) {
      console.error('[Session] POST error:', err)
      const notificationStore = useNotificationStore()
      notificationStore.showError('Failed to send message')
      agentMessage.status = 'error'
      agentMessage.content = 'Failed to send message'
      closeStream()
      return
    }

    // Connect to SSE stream
    const sessionId = currentSession.value.id
    console.log('[Session] Calling connectToStream for session:', sessionId)
    connectToStream(sessionId, agentMessage, taskId)
  }

  function connectToStream(sessionId: string, agentMessage: Message, _taskId?: string) {
    // Close existing connection
    if (eventSource.value) {
      eventSource.value.close()
    }

    // EventSource doesn't support credentials option, so we need to use fetch
    // with ReadableStream for SSE with authentication
    const url = `/api/sessions/${sessionId}/stream/`
    console.log('[SSE] Connecting to:', url)
    console.log('[SSE] About to fetch...')

    fetch(url, {
      credentials: 'include',  // Include cookies for authentication
    }).then(response => {
      console.log('[SSE] Response status:', response.status)
      console.log('[SSE] Response headers:', Object.fromEntries(response.headers.entries()))
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      const processLine = (line: string) => {
        console.log('[SSE] Received line:', line)
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6))
          console.log('[SSE] Parsed data:', data)

          if (data.type === 'text') {
            agentMessage.content += data.content
          } else if (data.type === 'tool_use') {
            console.log('Tool use:', data.tool_name, data.tool_input)
          } else if (data.type === 'done') {
            agentMessage.status = 'complete'
            if (data.response) {
              agentMessage.content = data.response
            }
            closeStream()
          } else if (data.type === 'error') {
            agentMessage.status = 'error'
            agentMessage.content = data.error || data.error_message || 'An error occurred'
            closeStream()
          } else if (data.type === 'interrupted') {
            agentMessage.status = 'interrupted'
            closeStream()
          } else if (data.type === 'connected') {
            console.log('SSE connected:', data.session_id)
          }
        }
      }

      const readChunk = (): Promise<void> | undefined => {
        return reader.read().then(({ done, value }) => {
          if (done) {
            console.log('[SSE] Stream done')
            // Process any remaining buffer
            if (buffer.trim()) {
              buffer.split('\n\n').forEach(block => {
                block.split('\n').forEach(line => {
                  if (line.trim()) processLine(line)
                })
              })
            }
            if (agentMessage.status === 'streaming') {
              agentMessage.status = 'complete'
            }
            closeStream()
            return
          }

          buffer += decoder.decode(value, { stream: true })

          // Process complete SSE blocks (ended with \n\n)
          const blocks = buffer.split('\n\n')
          buffer = blocks.pop() || ''  // Keep incomplete block in buffer

          blocks.forEach(block => {
            block.split('\n').forEach(line => {
              if (line.trim()) processLine(line)
            })
          })

          return readChunk()
        })
      }

      return readChunk()
    }).catch(err => {
      console.error('[SSE] Error:', err)
      if (agentMessage.status === 'streaming') {
        agentMessage.status = 'error'
        agentMessage.content = 'Connection failed'
      }
      closeStream()
    })

    console.log('[SSE] Fetch initiated')
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