<script setup>
import { ref } from 'vue'

const count = ref(0)
</script>

<template>
  <div class="container">
    <h1>AtomsX Workspace</h1>
    <p>Welcome to your new workspace!</p>
    <p>Start editing the files to see live changes.</p>

    <div class="counter">
      <button @click="count++">Count: {{ count }}</button>
    </div>

    <div class="hint">
      <p>💡 Ask the AI Agent to help you build something!</p>
    </div>
  </div>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
}

.container {
  background: white;
  border-radius: 16px;
  padding: 48px;
  text-align: center;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  max-width: 500px;
}

h1 {
  color: #333;
  margin-bottom: 16px;
  font-size: 2rem;
}

p {
  color: #666;
  margin-bottom: 12px;
  line-height: 1.6;
}

.counter {
  margin: 24px 0;
}

button {
  background: #667eea;
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 1rem;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

button:active {
  transform: translateY(0);
}

.hint {
  margin-top: 24px;
  padding: 16px;
  background: #f0f4ff;
  border-radius: 8px;
}

.hint p {
  color: #667eea;
  margin: 0;
}
</style>