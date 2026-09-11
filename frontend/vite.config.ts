import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /api to the FastAPI backend so the browser only ever
// talks to one origin (works behind the sandbox preview proxy too).
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // The sandbox previews the app through a proxied *.e2b.app host; allow it.
    allowedHosts: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
