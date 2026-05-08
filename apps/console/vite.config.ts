import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  define: {
    __API_BASE__: JSON.stringify(process.env.VITE_API_BASE ?? "")
  },
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY ?? "http://localhost:8742",
        changeOrigin: true
      }
    }
  }
});
