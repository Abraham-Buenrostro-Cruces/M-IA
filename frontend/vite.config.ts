/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      // 'prompt' en lugar de 'autoUpdate': recargar la app sola a mitad de un
      // viaje podría hacer perder la ruta en pantalla. Se pedirá confirmación (F3-6).
      registerType: 'prompt',
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'RutaAccesible',
        short_name: 'RutaAccesible',
        description:
          'Rutas accesibles en Metro, Metrobús y Tren Ligero de la Ciudad de México.',
        lang: 'es-MX',
        dir: 'ltr',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'any', // sin bloquear orientación: algunas personas fijan el teléfono a la silla
        background_color: '#ffffff',
        theme_color: '#0b4f8a',
        icons: [
          { src: 'icono-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icono-512.png', sizes: '512x512', type: 'image/png' },
          {
            src: 'icono-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
      },
    }),
  ],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/pruebas/configuracion.ts'],
    css: false,
  },
})
