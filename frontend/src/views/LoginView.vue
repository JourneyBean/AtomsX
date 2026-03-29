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
  background: linear-gradient(135deg, #f5f5f7 0%, #e8e8ed 100%);
}

.login-card {
  background: #fff;
  border-radius: 16px;
  padding: 48px;
  text-align: center;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
}

.login-card h1 {
  color: #1d1d1f;
  font-size: 2.5rem;
  font-weight: 600;
  margin-bottom: 8px;
}

.login-card p {
  color: #86868b;
  margin-bottom: 32px;
  font-size: 1.1rem;
}

.login-btn {
  background: #4f46e5;
  color: white;
  padding: 14px 32px;
  border-radius: 10px;
  font-size: 1rem;
  cursor: pointer;
  border: none;
  transition: background 0.15s;
  font-weight: 500;
}

.login-btn:hover {
  background: #4338ca;
}
</style>