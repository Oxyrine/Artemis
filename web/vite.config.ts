import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// The API (FastAPI) serves /api; in development Vite proxies to it so the browser sees one origin.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, './src') } },
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'], css: false },
})
