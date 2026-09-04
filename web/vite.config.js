import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The dev server proxies /ml straight to the FastAPI service, so the browser makes
// same-origin requests and no CORS preflight sits between a click and a result.
// Point ML_URL elsewhere if the service is not on the default port.
const ML = process.env.ML_URL || 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/ml': { target: ML, changeOrigin: true } }
  },
  build: { outDir: 'dist', sourcemap: true }
});
