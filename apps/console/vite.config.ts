import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  define: {
    __API_BASE__: JSON.stringify(process.env.VITE_API_BASE ?? "")
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8742"
    }
  }
});
