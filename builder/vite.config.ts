import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      // In real mode (VITE_USE_MOCKS=0), the dev server proxies /api/* to the
      // FastAPI backend, stripping the /api prefix.
      // Usage: fetch('/api/agents') → http://localhost:8000/agents
      // Alternatively, set VITE_API_URL=http://localhost:8000 and call the
      // backend directly (CORS must be enabled on the backend).
      '/api': {
        target: process.env.VITE_API_URL ?? 'http://localhost:8000',
        rewrite: (p) => p.replace(/^\/api/, ''),
        changeOrigin: true,
      },
    },
  },
})
