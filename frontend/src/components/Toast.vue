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
  border-radius: 10px;
  min-width: 280px;
  max-width: 400px;
  background: #fff;
  color: #1d1d1f;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  animation: slide-in 0.3s ease-out;
  border: 1px solid #e5e5ea;
}

.toast-error {
  border-left: 4px solid #dc2626;
}

.toast-error .toast-icon {
  color: #dc2626;
}

.toast-success {
  border-left: 4px solid #059669;
}

.toast-success .toast-icon {
  color: #059669;
}

.toast-warning {
  border-left: 4px solid #d97706;
}

.toast-warning .toast-icon {
  color: #d97706;
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
  color: #86868b;
  cursor: pointer;
  padding: 4px;
  font-size: 14px;
  line-height: 1;
  border-radius: 4px;
}

.toast-close:hover {
  color: #1d1d1f;
  background: #f5f5f7;
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