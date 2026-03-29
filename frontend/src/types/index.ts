export interface User {
  id: string
  email: string
  display_name: string
  avatar_url: string | null
  oidc_sub: string
  created_at: string
}

export interface Workspace {
  id: string
  name: string
  status: 'creating' | 'running' | 'stopped' | 'error' | 'deleting'
  container_id: string | null
  preview_url: string | null
  created_at: string
  updated_at: string
}

export interface Session {
  id: string
  workspace_id: string
  user_id: string
  messages: Message[]
  status: 'active' | 'inactive' | 'error'
  created_at: string
  updated_at: string
}

export interface Message {
  id?: string
  role: 'user' | 'agent'
  content: string
  timestamp: string
  status: 'complete' | 'streaming' | 'interrupted' | 'error'
}

export interface CreateWorkspaceRequest {
  name: string
}

export interface SendMessageRequest {
  content: string
}

export interface Notification {
  id: string
  type: 'success' | 'warning' | 'error'
  message: string
  duration: number
  timestamp: number
}

export interface HistorySession {
  history_session_id: string
  first_message: string
  last_activity: string
}

// File Browser Types
export * from './file'