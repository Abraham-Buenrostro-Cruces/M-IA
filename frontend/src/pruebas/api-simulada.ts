// API simulada con MSW. Las respuestas son salidas reales de api-core con el escenario de
// demostración flujo1 (capturadas en src/pruebas/datos/), así las pruebas siguen el contrato.
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import estaciones from './datos/estaciones.json'
import estadoZocalo from './datos/estado-zocalo.json'
import lugaresMuseo from './datos/lugares-museo.json'
import lugaresTasquena from './datos/lugares-tasquena.json'
import perfiles from './datos/perfiles.json'
import planFlujo1 from './datos/plan-flujo1.json'
import planSinRuta from './datos/plan-sin-ruta.json'

export const datos = { estaciones, estadoZocalo, lugaresMuseo, lugaresTasquena, perfiles, planFlujo1, planSinRuta }

/** Peticiones recibidas, para verificar qué sale del dispositivo (regla 6). */
export const peticiones: { metodo: string; url: string; cuerpo: string }[] = []

export const manejadores = [
  http.get('*/api/perfiles', () => HttpResponse.json(perfiles)),
  http.get('*/api/lugares', ({ request }) => {
    const q = new URL(request.url).searchParams.get('q')?.toLowerCase() ?? ''
    if (q.startsWith('tas')) return HttpResponse.json(lugaresTasquena)
    if (q.startsWith('mus')) return HttpResponse.json(lugaresMuseo)
    return HttpResponse.json([])
  }),
  http.get('*/api/estaciones', () => HttpResponse.json(estaciones)),
  http.get('*/api/estaciones/:clave/estado', () => HttpResponse.json(estadoZocalo)),
  http.post('*/api/rutas/plan', async ({ request }) => {
    const cuerpo = (await request.json()) as { destino: { clave_estacion?: string } }
    return HttpResponse.json(cuerpo.destino.clave_estacion === 'METRO-COPILCO' ? planSinRuta : planFlujo1)
  }),
]

export const servidor = setupServer(...manejadores)

servidor.events.on('request:start', async ({ request }) => {
  const cuerpo = request.method === 'GET' ? '' : await request.clone().text()
  peticiones.push({ metodo: request.method, url: request.url, cuerpo })
})
