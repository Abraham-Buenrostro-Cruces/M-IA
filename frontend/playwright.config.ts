// Pruebas en navegador real (F3-5): accesibilidad con axe-core (incluido el contraste, que
// jsdom no puede medir), recorrido sólo con teclado y uso sin red con el service worker.
//
// Requisitos: PostGIS arriba (docker compose up -d) con el GTFS, el inventario DEMO y el
// escenario flujo1 cargados (ver CLAUDE.md, "Datos"). Se prueba el build de producción
// (`vite preview`) porque el service worker sólo se registra ahí.
import { defineConfig, devices } from '@playwright/test'

const windows = process.platform === 'win32'
const uvicorn = windows ? '.venv\\Scripts\\uvicorn' : '.venv/bin/uvicorn'

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/preparacion.ts',
  timeout: 30_000,
  fullyParallel: false, // un solo backend y una sola base: evita interferencias
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    locale: 'es-MX',
    timezoneId: 'America/Mexico_City',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'escritorio', use: { ...devices['Desktop Chrome'] } },
    { name: 'celular', use: { ...devices['Pixel 7'] } },
  ],
  webServer: [
    {
      command: `${uvicorn} app.main:app --host 127.0.0.1 --port 8000`,
      cwd: '../backend',
      url: 'http://127.0.0.1:8000/salud',
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 4173 --strictPort',
      url: 'http://127.0.0.1:4173',
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
})
