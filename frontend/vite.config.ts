/// <reference types="vitest" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    // Tailwind v4 is CSS-first: no tailwind.config.js, no PostCSS config.
    // See docs/adr/0003-tailwind-v4-frontend-styling.md.
    tailwindcss(),
    react(),
    VitePWA({
      // "prompt", not "autoUpdate". UpdatePrompt.tsx is built on the
      // needRefresh signal, which only fires in prompt mode; under
      // autoUpdate the new worker activates silently and that toast is
      // unreachable dead code. Prompt mode also means the user decides when
      // to take a new version, which is the right default for an app that
      // gives health guidance.
      registerType: "prompt",
      includeAssets: ["favicon.svg", "apple-touch-icon.png"],
      manifest: {
        id: "/",
        name: "Allergy Companion",
        short_name: "Allergy Companion",
        description:
          "Chat-first allergy risk companion: pollen, air quality, and triage guidance.",
        start_url: "/",
        scope: "/",
        display: "standalone",
        // Fall back to minimal-ui on browsers that do not do standalone.
        display_override: ["standalone", "minimal-ui"],
        orientation: "portrait",
        categories: ["health", "medical", "lifestyle"],
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
        // Long-press the installed icon. Each target is a real route, so
        // these land on a working screen rather than the generic start_url.
        shortcuts: [
          {
            name: "Today's risk",
            short_name: "Today",
            description: "Pollen, air quality and your risk score for today.",
            url: "/today",
            icons: [
              { src: "pwa-192x192.png", sizes: "192x192", type: "image/png" },
            ],
          },
          {
            name: "Chat",
            short_name: "Chat",
            description: "Describe your symptoms and get a triage level.",
            url: "/chat",
            icons: [
              { src: "pwa-192x192.png", sizes: "192x192", type: "image/png" },
            ],
          },
          {
            name: "Alerts",
            short_name: "Alerts",
            description: "Your stored pollen and air quality alerts.",
            url: "/alerts",
            icons: [
              { src: "pwa-192x192.png", sizes: "192x192", type: "image/png" },
            ],
          },
        ],
      },
      workbox: {
        // woff2 matters: the fonts are self-hosted in public/fonts, and
        // without it they are the one asset an installed PWA cannot render
        // offline, so the app falls back to a system face.
        globPatterns: ["**/*.{js,css,html,svg,png,ico,woff2}"],
        // Serve the SPA shell for navigations so client-side routes
        // (/today, /chat, ...) still work with no network.
        navigateFallback: "index.html",
        // Never cache API calls — data must stay live.
        navigateFallbackDenylist: [/^\/api\//],
      },
    }),
  ],
});
