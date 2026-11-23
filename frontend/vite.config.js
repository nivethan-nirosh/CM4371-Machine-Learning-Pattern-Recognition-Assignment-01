import { defineConfig } from 'vite';
export default defineConfig({
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
  build: {
    rolldownOptions: {
      output: {
        manualChunks(id) {
          if (/node_modules\/(react|react-dom|scheduler)\//.test(id)) return 'react';
          if (/node_modules\/(recharts|d3-|victory|@reduxjs|react-redux|reselect|immer|use-sync-external-store)/.test(id)) return 'charts';
        }
      }
    }
  }
});
