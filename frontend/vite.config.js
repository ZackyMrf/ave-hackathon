import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // SPA fallback: redirect all 404s to index.html
    historyApiFallback: true,
  },
});
