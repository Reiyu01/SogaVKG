import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Keep VITE_API_BASE_URL empty for local development while forwarding API
  // requests to FastAPI. Production deployments can still set an explicit
  // VITE_API_BASE_URL or serve both apps behind the same reverse proxy.
  server: {
    proxy: {
      '/builder': 'http://127.0.0.1:8000',
      '/query': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})
