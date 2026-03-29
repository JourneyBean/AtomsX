import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Notification } from '@/types'

const MAX_NOTIFICATIONS = 5
const DEFAULT_DURATION = 3000

export const useNotificationStore = defineStore('notification', () => {
  const notifications = ref<Notification[]>([])

  function add(type: Notification['type'], message: string, duration = DEFAULT_DURATION): string {
    const id = crypto.randomUUID()
    const notification: Notification = {
      id,
      type,
      message,
      duration,
      timestamp: Date.now(),
    }

    // Enforce max limit - remove oldest if exceeded
    if (notifications.value.length >= MAX_NOTIFICATIONS) {
      notifications.value.shift()
    }

    notifications.value.push(notification)

    // Auto-dismiss timer
    if (duration > 0) {
      setTimeout(() => {
        remove(id)
      }, duration)
    }

    return id
  }

  function showError(message: string, duration?: number): string {
    return add('error', message, duration)
  }

  function showSuccess(message: string, duration?: number): string {
    return add('success', message, duration)
  }

  function showWarning(message: string, duration?: number): string {
    return add('warning', message, duration)
  }

  function remove(id: string): void {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index !== -1) {
      notifications.value.splice(index, 1)
    }
  }

  function clear(): void {
    notifications.value = []
  }

  return {
    notifications,
    showError,
    showSuccess,
    showWarning,
    remove,
    clear,
  }
})