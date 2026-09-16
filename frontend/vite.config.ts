import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["lume-mark.svg"],
      manifest: {
        name: "Lume Personal Finance",
        short_name: "Lume",
        description: "See where your money goes and stay within your budget.",
        theme_color: "#102c26",
        background_color: "#f5f3eb",
        display: "standalone",
        start_url: "/app",
        icons: [
          { src: "/lume-mark.svg", sizes: "any", type: "image/svg+xml", purpose: "any maskable" },
        ],
      },
      workbox: {
        navigateFallback: "/index.html",
        runtimeCaching: [],
        navigateFallbackDenylist: [/^\/api\//],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://api:8000", changeOrigin: false },
      "/healthz": { target: "http://api:8000" },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
  },
});
