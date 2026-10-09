import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// npm run dev: dashboard on http://localhost:5173, API calls go to the Python server.
// npm run build: writes frontend/dist, which the Python server serves at http://127.0.0.1:8000/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Charts make the bundle ~220 kB gzipped; fine for a dashboard served from the local server.
  build: { chunkSizeWarningLimit: 900 },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})
