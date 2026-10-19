import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  define: { __BUILD__: JSON.stringify(new Date().toISOString().slice(0, 16).replace("T", " ")) }, // shown in the field app so a device's version can be checked
  plugins: [
    react(),
    // Installable, offline-capable: the app shell is precached; the M&E field tool keeps its form, geography
    // and pending reports on the device and syncs when the network is back. API calls are never cached except
    // the small read-only bundles listed below (network first, so a fresh copy wins when online).
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.png", "statsl-logo.png", "census-logo.png"],
      manifest: {
        name: "SLPHC 2026 · Monitoring & Evaluation",
        short_name: "Census M&E",
        description: "Statistics Sierra Leone · 2026 Population and Housing Census · field monitoring, evaluation and KPI tools",
        theme_color: "#1F4E79",
        background_color: "#1F4E79",
        display: "standalone",
        start_url: "/me/kpi",
        scope: "/",
        icons: [
          { src: "/pwa-192.png", sizes: "192x192", type: "image/png" },
          { src: "/pwa-512.png", sizes: "512x512", type: "image/png" },
          { src: "/pwa-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//, /^\/downloads\//],
        globPatterns: ["**/*.{js,css,html,png,svg,woff2}"],
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname === "/api/v1/me/kpi/form" || url.pathname === "/api/v1/me/kpi/geo" || url.pathname === "/api/v1/auth/me",
            handler: "NetworkFirst",
            options: { cacheName: "me-kpi-data", networkTimeoutSeconds: 8, expiration: { maxEntries: 8, maxAgeSeconds: 60 * 60 * 24 * 30 }, cacheableResponse: { statuses: [0, 200] } },
          },
        ],
      },
    }),
  ],
  preview: {
    port: 4173,
    host: true,
    proxy: { "/api": { target: process.env.VITE_API_PROXY || "http://localhost:8000", changeOrigin: true } },
  },
  server: {
    port: 5173,
    host: true, // IPv4 and IPv6: the Android emulator reaches the dev server through adb reverse (127.0.0.1)
    proxy: {
      "/api": { target: process.env.VITE_API_PROXY || "http://localhost:8000", changeOrigin: true },
    },
  },
});
