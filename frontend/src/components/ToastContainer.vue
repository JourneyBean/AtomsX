<script setup lang="ts">
import { computed } from 'vue'
import { useNotificationStore } from '@/stores/notification'
import Toast from '@/components/Toast.vue'

const notificationStore = useNotificationStore()

// Show newest notifications on top
const sortedNotifications = computed(() => {
  return [...notificationStore.notifications].reverse()
})
</script>

<template>
  <div class="toast-container">
    <TransitionGroup name="toast">
      <Toast
        v-for="notification in sortedNotifications"
        :key="notification.id"
        :notification="notification"
        @close="notificationStore.remove"
      />
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-container {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Transition animations */
.toast-enter-active {
  animation: slide-in 0.3s ease-out;
}

.toast-leave-active {
  animation: slide-out 0.3s ease-in;
}

.toast-move {
  transition: transform 0.3s ease;
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

@keyframes slide-out {
  from {
    opacity: 1;
    transform: translateX(0);
  }
  to {
    opacity: 0;
    transform: translateX(20px);
  }
}
</style>