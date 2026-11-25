import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { createElement } from 'react'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'
import { peticiones, servidor, simulacion } from './api-simulada'

// Leaflet necesita medir el DOM y descargar mosaicos: en jsdom se sustituye por un doble
// que muestra el mismo contenido como texto. El mapa real se prueba con Playwright.
vi.mock('../componentes/Mapas', () => ({
  MapaRuta: ({ alternativas }: { alternativas: { orden: number }[] }) =>
    createElement('div', { 'data-testid': 'mapa-ruta' }, `Mapa con ${alternativas.length} ${alternativas.length === 1 ? 'alternativa' : 'alternativas'}`),
  MapaEstaciones: ({ lineas, estaciones, accesibilidad }: { lineas: unknown[]; estaciones: unknown[]; accesibilidad: boolean }) =>
    createElement(
      'div',
      { 'data-testid': 'mapa-estaciones' },
      `Mapa con ${lineas.length} líneas y ${estaciones.length} estaciones${accesibilidad ? ' con accesibilidad' : ''}`,
    ),
}))

// Con todos los archivos de prueba en paralelo, en una laptop de 8 GB una respuesta simulada
// puede tardar más de 1 s (el valor por defecto de findBy*).
configure({ asyncUtilTimeout: 3000 })

// jsdom no implementa URL.createObjectURL (fotos y vista previa).
URL.createObjectURL ??= () => 'blob:prueba'
URL.revokeObjectURL ??= () => {}

// MSW 3: toda petición sin manejador hace fallar la prueba.
beforeAll(() => servidor.listen({ onUnhandledFrame: 'error' }))
afterEach(() => {
  cleanup()
  servidor.resetHandlers()
  peticiones.length = 0
  simulacion.consultas = 0
  simulacion.decisiones.length = 0
  localStorage.clear()
  sessionStorage.clear()
})
afterAll(() => servidor.close())
