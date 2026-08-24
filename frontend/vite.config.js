import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Vite config for the PhishGuard dashboard.
 *
 * Why a dev proxy instead of calling http://localhost:8000 directly:
 * every request from the dev server goes to the SAME origin the page was
 * served from (http://localhost:5173), so the browser never treats an API
 * call as cross-origin. That means the app uses one relative base URL
 * ("/api") in BOTH dev and production. In production FastAPI serves the
 * built files itself, so "/api" is already same-origin there.
 *
 * The backend also allows CORS from :5173 as a belt-and-braces fallback,
 * but the proxy is what keeps the code path identical between the two
 * environments.
 */
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // FastAPI mounts <repo>/frontend/dist/assets at /assets and serves
    // dist/index.html at /. These are Vite's defaults; kept explicit so a
    // future change here is an obvious, deliberate break of that contract.
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    rollupOptions: {
      output: {
        // Recharts pulls in d3-scale/-shape/-array and is far larger than
        // the app itself. Splitting it out means editing a component
        // invalidates a ~30kB chunk instead of a ~600kB one, so the
        // browser re-downloads almost nothing between rebuilds.
        manualChunks: {
          recharts: ['recharts'],
        },
      },
    },
  },
})
