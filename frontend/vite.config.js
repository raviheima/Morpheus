import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Relative paths so Electron can load dist/ via file://
  base: "./",
  server: {
    port: 5173,
    proxy: {
      "/auth": "http://localhost:8000",
      "/cases": "http://localhost:8000",
      "/data-sources": "http://localhost:8000",
      "/analysis": "http://localhost:8000",
      "/evidence": "http://localhost:8000",
    },
  },
});
