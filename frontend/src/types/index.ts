export interface User {
  id: string
  email: string
  display_name: string
  oidc_sub: string
  created_at: string
}

export interface Workspace {
  id: string
  name: string
  status: 'creating' | 'running' | 'stopped' | 'error' | 'deleting'
  container_id: string | null
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