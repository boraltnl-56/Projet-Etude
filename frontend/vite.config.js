import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// UrbanFlow — Configuration Vite
// Proxy API : redirige /api/v1/* vers FastAPI (localhost:8000)
// Évite les erreurs CORS en développement
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path,
      },
    },
  },
})
