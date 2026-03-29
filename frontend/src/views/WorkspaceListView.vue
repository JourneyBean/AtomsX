<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notification'
import type { Workspace } from '@/types'

const router = useRouter()
const authStore = useAuthStore()
const notificationStore = useNotificationStore()
const workspaces = ref<Workspace[]>([])
const isLoading = ref(false)
const newWorkspaceName = ref('')
const isCreating = ref(false)
const isComposing = ref(false) // IME composition state
const creatingIds = ref<Set<string>>(new Set())
const recreatingIds = ref<Set<string>>(new Set())
const deletingIds = ref<Set<string>>(new Set())

onMounted(async () => {
  await fetchWorkspaces()
})

async function fetchWorkspaces() {
  isLoading.value = true
  try {
    const response = await fetch('/api/workspaces/', {
      credentials: 'include',
    })
    if (response.ok) {
      workspaces.value = await response.json()
    } else {
      notificationStore.showError('Failed to load workspaces')
    }
  } catch {
    notificationStore.showError('Failed to load workspaces')
  } finally {
    isLoading.value = false
  }
}

async function createWorkspace() {
  if (!newWorkspaceName.value.trim()) return
  isCreating.value = true
  try {
    const response = await fetch('/api/workspaces/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ name: newWorkspaceName.value }),
    })
    if (response.ok) {
      const workspace = await response.json()
      workspaces.value.unshift(workspace)
      newWorkspaceName.value = ''
      // Poll for creation completion
      if (workspace.status === 'creating') {
        creatingIds.value.add(workspace.id)
        pollCreationStatus(workspace.id)
      }
    } else {
      const data = await response.json().catch(() => ({ error: 'Failed to create workspace' }))
      notificationStore.showError(data.error || 'Failed to create workspace')
    }
  } catch {
    notificationStore.showError('Failed to create workspace')
  } finally {
    isCreating.value = false
  }
}

async function pollCreationStatus(workspaceId: string) {
  const maxAttempts = 90 // 90 * 2s = 3 minutes max
  let attempts = 0

  const poll = async () => {
    attempts++
    try {
      const response = await fetch(`/api/workspaces/${workspaceId}/`, {
        credentials: 'include',
      })
      if (response.ok) {
        const workspace = await response.json()
        if (workspace.status !== 'creating') {
          // Update workspace in list
          const index = workspaces.value.findIndex(w => w.id === workspaceId)
          if (index !== -1) {
            workspaces.value[index] = workspace
          }
          creatingIds.value.delete(workspaceId)
          if (workspace.status === 'running') {
            notificationStore.showSuccess('Workspace created successfully')
          } else if (workspace.status === 'error') {
            notificationStore.showError('Workspace creation failed')
          }
          return
        }
      }
    } catch {
      // Continue polling on error
    }

    if (attempts < maxAttempts) {
      setTimeout(poll, 2000)
    } else {
      creatingIds.value.delete(workspaceId)
      notificationStore.showError('Workspace creation timed out')
    }
  }

  poll()
}

async function deleteWorkspace(id: string) {
  deletingIds.value.add(id)
  try {
    const response = await fetch(`/api/workspaces/${id}/`, {
      method: 'DELETE',
      credentials: 'include',
    })
    if (response.ok) {
      workspaces.value = workspaces.value.filter(w => w.id !== id)
      deletingIds.value.delete(id)
      notificationStore.showSuccess('Workspace deleted')
    } else {
      notificationStore.showError('Failed to delete workspace')
      deletingIds.value.delete(id)
    }
  } catch {
    notificationStore.showError('Failed to delete workspace')
    deletingIds.value.delete(id)
  }
}

async function recreateWorkspace(workspace: Workspace) {
  recreatingIds.value.add(workspace.id)
  try {
    const response = await fetch(`/api/workspaces/${workspace.id}/recreate/`, {
      method: 'POST',
      credentials: 'include',
    })
    if (response.ok) {
      const updated = await response.json()
      // Update workspace in list
      const index = workspaces.value.findIndex(w => w.id === workspace.id)
      if (index !== -1) {
        workspaces.value[index] = updated
      }
      // Poll for completion if recreating
      if (updated.status === 'recreating') {
        pollRecreateStatus(workspace.id)
      }
    } else {
      const data = await response.json().catch(() => ({ error: 'Failed to recreate workspace' }))
      notificationStore.showError(data.error || 'Failed to recreate workspace')
      recreatingIds.value.delete(workspace.id)
    }
  } catch {
    notificationStore.showError('Failed to recreate workspace')
    recreatingIds.value.delete(workspace.id)
  }
}

async function pollRecreateStatus(workspaceId: string) {
  const maxAttempts = 60 // 60 * 2s = 2 minutes max
  let attempts = 0

  const poll = async () => {
    attempts++
    try {
      const response = await fetch(`/api/workspaces/${workspaceId}/`, {
        credentials: 'include',
      })
      if (response.ok) {
        const workspace = await response.json()
        if (workspace.status !== 'recreating') {
          // Update workspace in list
          const index = workspaces.value.findIndex(w => w.id === workspaceId)
          if (index !== -1) {
            workspaces.value[index] = workspace
          }
          recreatingIds.value.delete(workspaceId)
          if (workspace.status === 'running') {
            notificationStore.showSuccess('Workspace recreated successfully')
          } else if (workspace.status === 'error') {
            notificationStore.showError('Workspace recreate failed')
          }
          return
        }
      }
    } catch {
      // Continue polling on error
    }

    if (attempts < maxAttempts) {
      setTimeout(poll, 2000)
    } else {
      recreatingIds.value.delete(workspaceId)
      notificationStore.showError('Workspace recreate timed out')
    }
  }

  poll()
}

function openWorkspace(id: string) {
  router.push({ name: 'workspace-detail', params: { id } })
}

function handleLogout() {
  authStore.logout()
}

function handleKeyDown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !isComposing.value) {
    createWorkspace()
  }
}

function canRecreate(status: string): boolean {
  return status === 'running' || status === 'stopped' || status === 'error'
}

function isPending(workspace: Workspace): boolean {
  return creatingIds.value.has(workspace.id) || recreatingIds.value.has(workspace.id) || deletingIds.value.has(workspace.id)
}

function getStatusText(workspace: Workspace): string {
  if (creatingIds.value.has(workspace.id)) {
    return 'Creating...'
  }
  if (recreatingIds.value.has(workspace.id)) {
    return 'Recreating...'
  }
  if (deletingIds.value.has(workspace.id)) {
    return 'Deleting...'
  }
  return workspace.status
}
</script>

<template>
  <div class="workspace-list-view">
    <header class="header">
      <h1>AtomsX</h1>
      <div class="user-info">
        <img
          v-if="authStore.user?.avatar_url"
          :src="authStore.user.avatar_url"
          :alt="authStore.user.display_name"
          class="avatar"
        />
        <div v-else class="avatar-placeholder">{{ authStore.user?.display_name?.charAt(0)?.toUpperCase() }}</div>
        <span>{{ authStore.user?.display_name }}</span>
        <button @click="handleLogout" class="logout-btn">Logout</button>
      </div>
    </header>

    <main class="main">
      <div class="create-section">
        <input
          v-model="newWorkspaceName"
          placeholder="New workspace name"
          class="input"
          @keydown="handleKeyDown"
          @compositionstart="isComposing = true"
          @compositionend="isComposing = false"
        />
        <button @click="createWorkspace" :disabled="isCreating" class="create-btn">
          {{ isCreating ? 'Creating...' : 'Create' }}
        </button>
      </div>

      <div v-if="isLoading" class="loading">Loading...</div>

      <div v-else class="workspace-list">
        <div
          v-for="workspace in workspaces"
          :key="workspace.id"
          class="workspace-card"
          :class="{ 'workspace-card-pending': isPending(workspace) }"
          @click="!isPending(workspace) && openWorkspace(workspace.id)"
        >
          <div class="workspace-info">
            <h3>{{ workspace.name }}</h3>
            <span class="status" :class="{ 'status-pending': isPending(workspace) }">
              {{ getStatusText(workspace) }}
            </span>
          </div>
          <div class="workspace-actions">
            <button
              v-if="canRecreate(workspace.status)"
              @click.stop="recreateWorkspace(workspace)"
              :disabled="recreatingIds.has(workspace.id)"
              class="recreate-btn"
            >
              {{ recreatingIds.has(workspace.id) ? 'Recreating...' : 'Recreate' }}
            </button>
            <button
              @click.stop="deleteWorkspace(workspace.id)"
              :disabled="isPending(workspace)"
              class="delete-btn"
            >
              {{ deletingIds.has(workspace.id) ? 'Deleting...' : 'Delete' }}
            </button>
          </div>
        </div>

        <div v-if="workspaces.length === 0" class="empty">
          No workspaces yet. Create one above.
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.workspace-list-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f5f7;
  color: #1d1d1f;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.header h1 {
  font-size: 1.5rem;
  font-weight: 600;
  color: #1d1d1f;
}

.user-info {
  display: flex;
  gap: 12px;
  align-items: center;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
}

.avatar-placeholder {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #4f46e5;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
}

.user-info span {
  color: #1d1d1f;
  font-weight: 500;
}

.logout-btn {
  background: transparent;
  border: 1px solid #d2d2d7;
  color: #1d1d1f;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.logout-btn:hover {
  background: #f5f5f7;
  border-color: #86868b;
}

.main {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
}

.create-section {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  background: #fff;
  padding: 16px;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.input {
  flex: 1;
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid #d2d2d7;
  background: #f5f5f7;
  color: #1d1d1f;
  font-size: 1rem;
  transition: all 0.15s;
}

.input:focus {
  outline: none;
  border-color: #4f46e5;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.create-btn {
  background: #4f46e5;
  color: white;
  padding: 12px 24px;
  border-radius: 10px;
  border: none;
  cursor: pointer;
  font-weight: 500;
  transition: background 0.15s;
}

.create-btn:hover:not(:disabled) {
  background: #4338ca;
}

.create-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.workspace-list {
  display: grid;
  gap: 12px;
}

.workspace-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.workspace-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  transform: translateY(-1px);
}

.workspace-info h3 {
  margin: 0 0 4px 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: #1d1d1f;
}

.status {
  color: #86868b;
  font-size: 0.85rem;
}

.status-pending {
  color: #4f46e5;
}

.workspace-card-pending {
  opacity: 0.7;
  cursor: wait !important;
}

.workspace-card-pending:hover {
  transform: none;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.workspace-actions {
  display: flex;
  gap: 8px;
}

.recreate-btn {
  background: transparent;
  border: 1px solid #c7d2fe;
  color: #4f46e5;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.recreate-btn:hover:not(:disabled) {
  background: #eef2ff;
  border-color: #a5b4fc;
}

.recreate-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.delete-btn {
  background: transparent;
  border: 1px solid #fecaca;
  color: #dc2626;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.delete-btn:hover:not(:disabled) {
  background: #fee2e2;
  border-color: #f87171;
}

.delete-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.empty {
  text-align: center;
  color: #86868b;
  padding: 48px;
  background: #fff;
  border-radius: 12px;
}

.loading {
  text-align: center;
  color: #86868b;
  padding: 48px;
}
</style>