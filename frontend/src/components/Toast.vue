<script setup lang="ts">
import type { Notification } from '@/types'

defineProps<{
  notification: Notification
}>()

const emit = defineEmits<{
  close: [id: string]
}>()

function getTypeClass(type: Notification['type']) {
  return `toast-${type}`
}
</script>

<template>
  <div class="toast" :class="getTypeClass(notification.type)">
    <div class="toast-content">
      <span class="toast-icon">
        {{ notification.type === 'error' ? '✕' : notification.type === 'success' ? '✓' : '⚠' }}
      </span>
      <span class="toast-message">{{ notification.message }}</span>
    </div>
    <button class="toast-close" @click="emit('close', notification.id)">
      ✕
    </button>
  </div>
</template>

<style scoped>
.toast {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-radius: 8px;
  min-width: 280px;
  max-width: 400px;
  background: rgba(30, 30, 50, 0.95);
  color: #fff;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  animation: slide-in 0.3s ease-out;
}

.toast-error {
  border-left: 4px solid #ef4444;
}

.toast-error .toast-icon {
  color: #ef4444;
}

.toast-success {
  border-left: 4px solid #22c55e;
}

.toast-success .toast-icon {
  color: #22c55e;
}

.toast-warning {
  border-left: 4px solid #f59e0b;
}

.toast-warning .toast-icon {
  color: #f59e0b;
}

.toast-content {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.toast-icon {
  font-size: 16px;
  font-weight: bold;
}

.toast-message {
  flex: 1;
  font-size: 14px;
  line-height: 1.4;
  word-break: break-word;
}

.toast-close {
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  padding: 4px;
  font-size: 14px;
  line-height: 1;
}

.toast-close:hover {
  color: #fff;
}

@keyframes slide-in {
  from {
    opacity: 0;
    transform: translateX(20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
</style>