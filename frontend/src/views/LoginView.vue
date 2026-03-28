<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

function handleLogin() {
  authStore.login()
}
</script>

<template>
  <div class="login-view">
    <div class="login-card">
      <h1>AtomsX</h1>
      <p>Visual Coding Platform</p>
      <button @click="handleLogin" class="login-btn">
        Login with OIDC
      </button>
    </div>
  </div>
</template>

<style scoped>
.login-view {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
}

.login-card {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 48px;
  text-align: center;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.login-card h1 {
  color: #fff;
  font-size: 2.5rem;
  margin-bottom: 8px;
}

.login-card p {
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 32px;
}

.login-btn {
  background: #4f46e5;
  color: white;
  padding: 12px 32px;
  border-radius: 8px;
  font-size: 1rem;
  cursor: pointer;
  border: none;
  transition: background 0.2s;
}

.login-btn:hover {
  background: #4338ca;
}
</style>