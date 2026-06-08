import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, all API calls go through /api → stripped and forwarded to FastAPI on :8000.
// In production, FastAPI serves the built SPA and all routes are on the same origin,
// so VITE_API_BASE is empty and api.js calls /auth/..., /stats, etc. directly.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
