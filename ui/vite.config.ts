import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// The dev server proxies /api to the Python bridge so `npm run dev` can
// run against any running server.py (default port 8420) without CORS.
// Override with BRIDGE_PORT for a bridge started on another port (the
// isolated test bridges this project runs constantly use one).
const bridgePort = process.env.BRIDGE_PORT || '8420'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': `http://127.0.0.1:${bridgePort}`,
    },
  },
  build: {
    outDir: 'dist',
  },
})
