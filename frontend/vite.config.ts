import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const proxyTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";
  return {
    plugins: [react()],
    server: {
      host: "127.0.0.1",
      port: 3010,
      strictPort: true,
      proxy: {
        "/api": proxyTarget,
        "/sso": proxyTarget,
      },
    },
    preview: {
      host: "127.0.0.1",
      port: 3010,
      strictPort: true,
    },
  };
});
