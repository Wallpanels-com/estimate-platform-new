import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  envDir: "../..",
  server: {
    host: "127.0.0.1",
    port: 5190,
    strictPort: true,
    proxy: Object.fromEntries(
      ["/api", "/storage", "/health"].map((path) => [
        path,
        {
          target: process.env.BACKEND_URL || "http://127.0.0.1:8010",
          changeOrigin: true,
        },
      ]),
    ),
  },
});
