import { defineStore } from 'pinia'
import { ref, nextTick } from 'vue'
import type { Session, Message } from '@/types'
import { useNotificationStore } from '@/stores/notification'

// File operation tool names that should trigger file tree refresh
const FILE_OPERATION_TOOLS = [
  'Read', 'Write', 'Edit', 'Bash', 'Glob', 'Grep',
  'NotebookEdit', 'mcp__*', // MCP tools might involve file operations
]

// Callback for file operation events
let fileOperationCallback: (() => void) | null = null

export function onFileOperation(callback: () => void) {
  fileOperationCallback = callback
}

export function offFileOperation() {
  fileOperationCallback = null
}

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

    // Send message and receive SSE stream in single POST request
    const sessionId = currentSession.value.id
    const url = `/api/sessions/${sessionId}/messages/`
    console.log('[Session] Sending POST with SSE stream:', url)

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ content }),
      })

      console.log('[Session] POST response:', response.status)

      // Check content type
      const contentType = response.headers.get('content-type')
      console.log('[Session] Content-Type:', contentType)

      if (!response.ok) {
        const notificationStore = useNotificationStore()
        notificationStore.showError('Failed to send message')
        agentMessage.status = 'error'
        agentMessage.content = 'Failed to send message'
        closeStream()
        return
      }

      // Process SSE stream from POST response
      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      // Helper to update message properties
      const updateMessage = (updates: Partial<Message>) => {
        const msg = messages.value.find((m: Message) => m.id === agentMessage.id)
        if (msg) {
          Object.assign(msg, updates)
          nextTick()
        }
      }

      const processLine = (line: string) => {
        console.log('[SSE] Received line:', line)
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            console.log('[SSE] Parsed data:', data)

            if (data.type === 'text') {
              const msg = messages.value.find((m: Message) => m.id === agentMessage.id)
              if (msg) {
                msg.content += data.content
                nextTick()
              }
            } else if (data.type === 'tool_use') {
              console.log('Tool use:', data.tool_name, data.tool_input)
              const isFileOperation = FILE_OPERATION_TOOLS.some(tool => {
                if (tool.endsWith('*')) {
                  return data.tool_name.startsWith(tool.slice(0, -1))
                }
                return data.tool_name === tool
              })
              if (isFileOperation && fileOperationCallback) {
                setTimeout(() => fileOperationCallback!(), 500)
              }
            } else if (data.type === 'done') {
              updateMessage({ status: 'complete', content: data.response || agentMessage.content })
              closeStream()
            } else if (data.type === 'error') {
              updateMessage({ status: 'error', content: data.error || data.error_message || 'An error occurred' })
              closeStream()
            } else if (data.type === 'interrupted') {
              updateMessage({ status: 'interrupted' })
              closeStream()
            } else if (data.type === 'connected') {
              console.log('[SSE] Connected')
            }
          } catch (e) {
            console.error('[SSE] Parse error:', e)
          }
        }
      }

      // Read stream chunks
      const readChunk = async () => {
        while (true) {
          const { done, value } = await reader.read()
          if (done) {
            console.log('[SSE] Stream done')
            if (buffer.trim()) {
              buffer.split('\n\n').forEach(block => {
                block.split('\n').forEach(line => {
                  if (line.trim()) processLine(line)
                })
              })
            }
            if (agentMessage.status === 'streaming') {
              updateMessage({ status: 'complete' })
            }
            closeStream()
            break
          }

          buffer += decoder.decode(value, { stream: true })

          // Process complete SSE blocks
          const blocks = buffer.split('\n\n')
          buffer = blocks.pop() || ''

          blocks.forEach(block => {
            block.split('\n').forEach(line => {
              if (line.trim()) processLine(line)
            })
          })
        }
      }

      await readChunk()

    } catch (err) {
      console.error('[Session] POST error:', err)
      const notificationStore = useNotificationStore()
      notificationStore.showError('Failed to send message')
      agentMessage.status = 'error'
      agentMessage.content = 'Failed to send message'
      closeStream()
    }
  }

  async function resumeSession(historySessionId: string, content: string): Promise<boolean> {
    if (!currentSession.value || isStreaming.value) {
      return false
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

    const sessionId = currentSession.value.id
    const url = `/api/sessions/${sessionId}/resume/`
    console.log('[Session] Sending resume POST with SSE stream:', url)

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          history_session_id: historySessionId,
          content,
        }),
      })

      if (!response.ok) {
        const notificationStore = useNotificationStore()
        notificationStore.showError('Failed to resume session')
        agentMessage.status = 'error'
        agentMessage.content = 'Failed to resume session'
        closeStream()
        return false
      }

      // Process SSE stream from POST response
      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      const updateMessage = (updates: Partial<Message>) => {
        const msg = messages.value.find((m: Message) => m.id === agentMessage.id)
        if (msg) {
          Object.assign(msg, updates)
          nextTick()
        }
      }

      const processLine = (line: string) => {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'text') {
              const msg = messages.value.find((m: Message) => m.id === agentMessage.id)
              if (msg) {
                msg.content += data.content
                nextTick()
              }
            } else if (data.type === 'done') {
              updateMessage({ status: 'complete' })
              closeStream()
            } else if (data.type === 'error') {
              updateMessage({ status: 'error', content: data.error || 'An error occurred' })
              closeStream()
            }
          } catch (e) {
            console.error('[SSE] Parse error:', e)
          }
        }
      }

      const readChunk = async () => {
        while (true) {
          const { done, value } = await reader.read()
          if (done) {
            if (buffer.trim()) {
              buffer.split('\n\n').forEach(block => {
                block.split('\n').forEach(line => {
                  if (line.trim()) processLine(line)
                })
              })
            }
            if (agentMessage.status === 'streaming') {
              updateMessage({ status: 'complete' })
            }
            closeStream()
            break
          }

          buffer += decoder.decode(value, { stream: true })
          const blocks = buffer.split('\n\n')
          buffer = blocks.pop() || ''
          blocks.forEach(block => {
            block.split('\n').forEach(line => {
              if (line.trim()) processLine(line)
            })
          })
        }
      }

      await readChunk()
      return true

    } catch {
      const notificationStore = useNotificationStore()
      notificationStore.showError('Failed to resume session')
      agentMessage.status = 'error'
      agentMessage.content = 'Failed to resume session'
      closeStream()
      return false
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
    resumeSession,
    interrupt,
    closeStream,
    clearSession,
  }
})