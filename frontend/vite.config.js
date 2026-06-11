import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Proxy API calls to Flask in local dev
    proxy: {
      '/auth':   'http://localhost:5000',
      '/tasks':  'http://localhost:5000',
      '/health': 'http://localhost:5000',
    },
  },
})
