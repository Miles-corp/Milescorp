import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Le site est servi par le serveur Python du Companion, à la racine (`/`).
// Les ressources partagées (polices, icônes, images, vidéo) restent dans
// `app/interface/companion/assets/` ; `public/` ne porte que les fichiers
// propres au site : manifeste, service worker et icônes d'application.
export default defineConfig({
  base: "/",
  publicDir: "public",
  plugins: [react()],
  build: {
    outDir: "../dist",
    emptyOutDir: true,
    assetsDir: "app",
    sourcemap: false,
    target: "es2020",
    reportCompressedSize: true,
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8787",
      "/assets": "http://127.0.0.1:8787",
    },
  },
});
