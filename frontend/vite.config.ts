import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        // Use Docker service name 'backend' instead of localhost
        // localhost would resolve to the container itself, not the backend service
        target: 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
})