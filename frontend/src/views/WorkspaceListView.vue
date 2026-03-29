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

async function deleteWorkspace(id: string) {
  try {
    const response = await fetch(`/api/workspaces/${id}/`, {
      method: 'DELETE',
      credentials: 'include',
    })
    if (response.ok) {
      workspaces.value = workspaces.value.filter(w => w.id !== id)
    } else {
      notificationStore.showError('Failed to delete workspace')
    }
  } catch {
    notificationStore.showError('Failed to delete workspace')
  }
}

function openWorkspace(id: string) {
  router.push({ name: 'workspace-detail', params: { id } })
}

function handleLogout() {
  authStore.logout()
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
          @keyup.enter="createWorkspace"
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
          @click="openWorkspace(workspace.id)"
        >
          <div class="workspace-info">
            <h3>{{ workspace.name }}</h3>
            <span class="status">{{ workspace.status }}</span>
          </div>
          <button @click.stop="deleteWorkspace(workspace.id)" class="delete-btn">
            Delete
          </button>
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
  background: #1a1a2e;
  color: #fff;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: rgba(255, 255, 255, 0.05);
}

.header h1 {
  font-size: 1.5rem;
}

.user-info {
  display: flex;
  gap: 16px;
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

.logout-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: #fff;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
}

.main {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.create-section {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.input {
  flex: 1;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.create-btn {
  background: #4f46e5;
  color: white;
  padding: 12px 24px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
}

.create-btn:disabled {
  opacity: 0.5;
}

.workspace-list {
  display: grid;
  gap: 16px;
}

.workspace-card {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: background 0.2s;
}

.workspace-card:hover {
  background: rgba(255, 255, 255, 0.15);
}

.workspace-info h3 {
  margin: 0;
  font-size: 1.1rem;
}

.status {
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.85rem;
}

.delete-btn {
  background: transparent;
  border: 1px solid rgba(255, 100, 100, 0.5);
  color: rgba(255, 100, 100, 1);
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
}

.empty {
  text-align: center;
  color: rgba(255, 255, 255, 0.5);
  padding: 48px;
}
</style>