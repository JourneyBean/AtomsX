import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const isLoading = ref(false)

  const isAuthenticated = computed(() => user.value !== null)

  async function fetchUser() {
    isLoading.value = true
    try {
      const response = await fetch('/api/auth/me/', {
        credentials: 'include',
      })
      if (response.ok) {
        user.value = await response.json()
      } else {
        user.value = null
      }
    } catch {
      user.value = null
    } finally {
      isLoading.value = false
    }
  }

  async function login() {
    window.location.href = '/api/auth/login/'
  }

  async function logout() {
    await fetch('/api/auth/logout/', {
      method: 'POST',
      credentials: 'include',
    })
    user.value = null
    window.location.href = '/login'
  }

  function setUser(userData: User) {
    user.value = userData
  }

  return {
    user,
    isLoading,
    isAuthenticated,
    fetchUser,
    login,
    logout,
    setUser,
  }
})