import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg", "apple-touch-icon.png"],
      manifest: {
        name: "Allergy Companion",
        short_name: "Allergy Companion",
        description: "Chat-first allergy risk companion: pollen, air quality, and triage guidance.",
        start_url: "/",
        scope: "/",
        display: "standalone",
        background_color: "#e7ece7",
        theme_color: "#2f7d57",
        icons: [
          { src: "pwa-192x192.png", sizes: "192x192", type: "image/png" },
          { src: "pwa-512x512.png", sizes: "512x512", type: "image/png" },
          {
            src: "pwa-maskable-512x512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,png,ico}"],
        // Never cache API calls — data must stay live.
        navigateFallbackDenylist: [/^\/api\//],
      },
    }),
  ],
});
