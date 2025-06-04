import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:7071', // Force IPv4 to avoid ::1 issues
        changeOrigin: true,
        // secure: false, // Uncomment if your backend is not using HTTPS locally
        // rewrite: (path) => path.replace(/^\/api/, '') // Use if your Azure Function routes don't include /api
      },
    },
  },
})
