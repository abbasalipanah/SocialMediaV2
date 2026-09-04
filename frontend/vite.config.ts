import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const proxyTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";
  const devServerPort = Number(env.VITE_DEV_SERVER_PORT || "3010");
  return {
    plugins: [react()],
    server: {
      host: "127.0.0.1",
      port: devServerPort,
      strictPort: true,
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: false,
        },
        "/sso": {
          target: proxyTarget,
          changeOrigin: false,
        },
      },
    },
    preview: {
      host: "127.0.0.1",
      port: devServerPort,
      strictPort: true,
    },
  };
});
