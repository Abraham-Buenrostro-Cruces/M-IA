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
import red from './datos/red.json'

export const datos = { red, estaciones, estadoZocalo, lugaresMuseo, lugaresTasquena, perfiles, planFlujo1, planSinRuta }

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
  http.get('*/api/red', () => HttpResponse.json(red)),
  http.get('*/api/estaciones/:clave/estado', () => HttpResponse.json(estadoZocalo)),
  http.post('*/api/rutas/plan', async ({ request }) => {
    const cuerpo = (await request.json()) as { destino: { clave_estacion?: string } }
    return HttpResponse.json(cuerpo.destino.clave_estacion === 'TREN_SUBURBANO-LECHERIA' ? planSinRuta : planFlujo1)
  }),
]

// --------------------------------------------------------------------------- Fase 4
export const TOKEN_MODERADOR = 'token-moderador'

export const reporteBase = {
  id_reporte: 'r1',
  estado_validacion: 'PENDIENTE',
  puntaje_confianza: null as number | null,
  motivos: [] as string[],
  tipo_problema: 'fuera_de_servicio',
  clave_estacion: 'METRO-ZOCALO',
  codigo_equipo: 'METRO-ZOCALO/SAL-PLAZA_DE_LA_CONSTITUCION/ELV',
  con_foto: true,
  id_evidencia: 'e1',
  creado_en: '2026-11-24T12:00:00Z',
  estado_equipo: 'OPERATIVO' as string | null,
}

/** Estado mutable de la API simulada de reportes (se reinicia en cada prueba). */
export const simulacion = { consultas: 0, decisiones: [] as string[] }

const enModeracion = (r: Request) => r.headers.get('Authorization') === `Bearer ${TOKEN_MODERADOR}`

export const manejadoresReportes = [
  http.post('*/api/usuarios/anonimo', () =>
    HttpResponse.json({ token: 'token-anonimo', id_usuario: 'u1', rol: 'usuario' }, { status: 201 }),
  ),
  http.get('*/api/usuarios/yo', ({ request }) =>
    HttpResponse.json({
      id_usuario: 'm1', rol: enModeracion(request) ? 'moderador' : 'usuario', reputacion: 0.5,
      reportes_confirmados: 0, reportes_rechazados: 0,
    }),
  ),
  http.post('*/api/reportes/subidas', () =>
    HttpResponse.json({
      id_subida: 's1', url_subida: '/api/evidencias/subidas/tok', metodo: 'PUT',
      tipos_permitidos: ['image/jpeg', 'image/png', 'image/webp'], tamano_maximo_bytes: 10485760, vence_en_s: 300,
    }, { status: 201 }),
  ),
  http.put('*/api/evidencias/subidas/:token', () => new HttpResponse(null, { status: 204 })),
  http.post('*/api/reportes', () => HttpResponse.json(reporteBase, { status: 202 })),
  http.get('*/api/reportes/mios', () => HttpResponse.json([{ ...reporteBase, estado_validacion: 'VERIFICADO_AUTO' }])),
  http.get('*/api/reportes/:id', () => {
    // Primera consulta: en verificación; después, ya validado (simula al trabajador).
    simulacion.consultas += 1
    return HttpResponse.json(
      simulacion.consultas === 1
        ? reporteBase
        : { ...reporteBase, estado_validacion: 'PENDIENTE_CORROBORACION', puntaje_confianza: 0.72,
            motivos: [], estado_equipo: 'FALLA_PROBABLE' },
    )
  }),
  http.get('*/api/evidencias/:id', () => new HttpResponse(new Uint8Array([0xff, 0xd8, 0xff]), { headers: { 'Content-Type': 'image/jpeg' } })),
  http.post('*/api/equipos/*', () => HttpResponse.json({ id_reporte: 'r1', voto: 'CONFIRMA' }, { status: 201 })),
  http.get('*/api/moderacion/reportes', ({ request }) => {
    if (!enModeracion(request)) return HttpResponse.json({ detail: 'Se requiere rol de moderador.' }, { status: 403 })
    if (simulacion.decisiones.length) return HttpResponse.json([])
    return HttpResponse.json([{
      ...reporteBase, estado_validacion: 'PENDIENTE_CORROBORACION', puntaje_confianza: 0.72,
      descripcion: 'Tiene cinta amarilla', votos_confirma: 1, votos_niega: 0, nombre_estacion: 'Zócalo',
      referencia_equipo: 'elevador salida Plaza de la Constitución',
      desglose: { visual: 0.88, geo: 1, reputacion: 0.5, corroboracion: 0, penalizaciones: 0, s: 0.721 },
    }])
  }),
  http.post('*/api/moderacion/reportes/:id/decision', async ({ request }) => {
    const { decision } = (await request.json()) as { decision: string }
    simulacion.decisiones.push(decision)
    return HttpResponse.json({ ...reporteBase, estado_validacion: decision === 'CONFIRMAR' ? 'CONFIRMADO_MODERADOR' : 'RECHAZADO' })
  }),
]

export const servidor = setupServer(...manejadores, ...manejadoresReportes)

servidor.events.on('request:start', async ({ request }) => {
  const cuerpo = request.method === 'GET' ? '' : await request.clone().text()
  peticiones.push({ metodo: request.method, url: request.url, cuerpo })
})
