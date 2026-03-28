<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

onMounted(async () => {
  // Handle OIDC callback - the backend will exchange the code
  // and redirect here with session established
  await authStore.fetchUser()
  if (authStore.isAuthenticated) {
    router.push({ name: 'workspaces' })
  } else {
    router.push({ name: 'login' })
  }
})
</script>

<template>
  <div class="callback-view">
    <p>Completing authentication...</p>
  </div>
</template>

<style scoped>
.callback-view {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  color: #fff;
}
</style>