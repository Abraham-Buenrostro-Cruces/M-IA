import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { createElement } from 'react'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'
import { peticiones, servidor } from './api-simulada'

// Leaflet necesita medir el DOM y descargar mosaicos: en jsdom se sustituye por un doble
// que muestra el mismo contenido como texto. El mapa real se prueba con Playwright.
vi.mock('../componentes/Mapas', () => ({
  MapaRuta: ({ alternativas }: { alternativas: { orden: number }[] }) =>
    createElement('div', { 'data-testid': 'mapa-ruta' }, `Mapa con ${alternativas.length} alternativas`),
  MapaEstaciones: ({ estaciones }: { estaciones: unknown[] }) =>
    createElement('div', { 'data-testid': 'mapa-estaciones' }, `Mapa con ${estaciones.length} estaciones`),
}))

beforeAll(() => servidor.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  servidor.resetHandlers()
  peticiones.length = 0
  localStorage.clear()
  sessionStorage.clear()
})
afterAll(() => servidor.close())
