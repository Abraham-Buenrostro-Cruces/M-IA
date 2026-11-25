// Fase 4 en la PWA: reportar (F4-1), seguimiento, corroboración (F4-7) y moderación (F4-6).
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { datos, peticiones, servidor, simulacion, TOKEN_MODERADOR } from './pruebas/api-simulada'
import { renderizarApp } from './pruebas/renderizar'

async function elegirEstacion(texto: string, opcion: RegExp) {
  const campo = screen.getByRole('combobox', { name: 'Estación' })
  await userEvent.type(campo, texto)
  await userEvent.click(await screen.findByRole('option', { name: opcion }))
}

describe('Reportar (F4-1)', () => {
  it('flujo completo con foto: subida firmada, reporte y seguimiento hasta validarse', async () => {
    renderizarApp('/reportar')
    expect(screen.getByRole('button', { name: 'Enviar reporte' })).toBeDisabled()
    await elegirEstacion('tasque', /^Tasqueña.*Metro/)

    await userEvent.click(await screen.findByRole('radio', { name: /elevador salida Plaza de la Constitución/i }))
    await userEvent.click(await screen.findByRole('radio', { name: 'Fuera de servicio' }))
    const foto = new File([new Uint8Array([0xff, 0xd8, 0xff])], 'foto.jpg', { type: 'image/jpeg' })
    await userEvent.upload(screen.getByLabelText(/Una foto permite verificar/), foto)
    expect(screen.getByRole('img', { name: /Vista previa/ })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Enviar reporte' }))

    // Seguimiento: primero "En verificación", luego el resultado del trabajador.
    expect(await screen.findByText('En verificación')).toBeInTheDocument()
    expect(await screen.findByText('Esperando confirmación', {}, { timeout: 4000 })).toBeInTheDocument()
    expect(screen.getByText('72 de 100')).toBeInTheDocument()
    expect(screen.getByText('Posible falla')).toBeInTheDocument()

    // Orden de las peticiones: identidad anónima, URL de subida, PUT de la foto, reporte.
    const rutas = peticiones.map((p) => `${p.metodo} ${new URL(p.url).pathname}`)
    const i = (r: string) => rutas.indexOf(r)
    expect(i('POST /api/usuarios/anonimo')).toBeGreaterThanOrEqual(0)
    expect(i('POST /api/reportes/subidas')).toBeLessThan(i('PUT /api/evidencias/subidas/tok'))
    expect(i('PUT /api/evidencias/subidas/tok')).toBeLessThan(i('POST /api/reportes'))
    const cuerpo = JSON.parse(peticiones.find((p) => p.url.endsWith('/api/reportes'))!.cuerpo)
    expect(cuerpo).toMatchObject({ clave_estacion: 'METRO-TASQUENA', tipo_problema: 'fuera_de_servicio', id_subida: 's1' })
    expect(localStorage.getItem('ra.token')).toBe('token-anonimo')
  })

  it('elegir un lugar que no es estación pide una estación', async () => {
    renderizarApp('/reportar')
    const campo = screen.getByRole('combobox', { name: 'Estación' })
    await userEvent.type(campo, 'museo')
    await userEvent.click(await screen.findByRole('option', { name: /Museo de la Ciudad de México/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Elige una estación')
  })

  it('sin foto también se puede reportar', async () => {
    renderizarApp('/reportar')
    await elegirEstacion('tasque', /^Tasqueña.*Metro/)
    await userEvent.click(await screen.findByRole('radio', { name: 'Otro problema / no sé cuál' }))
    await userEvent.click(await screen.findByRole('radio', { name: 'Ya funciona' }))
    await userEvent.click(screen.getByRole('button', { name: 'Enviar reporte' }))
    await screen.findByRole('heading', { name: 'Tu reporte' })
    expect(peticiones.some((p) => p.url.includes('/reportes/subidas'))).toBe(false)
    const cuerpo = JSON.parse(peticiones.find((p) => p.url.endsWith('/api/reportes'))!.cuerpo)
    expect(cuerpo).toMatchObject({ codigo_equipo: null, tipo_problema: 'funciona', id_subida: null })
  })

  it('si el token anónimo ya no es válido se renueva y se reintenta', async () => {
    localStorage.setItem('ra.token', 'token-viejo')
    let rechazos = 0
    servidor.use(
      http.post('*/api/reportes', ({ request }) => {
        if (request.headers.get('Authorization') === 'Bearer token-viejo') {
          rechazos += 1
          return HttpResponse.json({ detail: 'Token inválido' }, { status: 401 })
        }
        return HttpResponse.json({ id_reporte: 'r1', estado_validacion: 'PENDIENTE', motivos: [], tipo_problema: 'funciona',
          clave_estacion: 'METRO-TASQUENA', codigo_equipo: null, con_foto: false, id_evidencia: null,
          puntaje_confianza: null, creado_en: '2026-11-24T12:00:00Z' }, { status: 202 })
      }),
    )
    renderizarApp('/reportar')
    await elegirEstacion('tasque', /^Tasqueña.*Metro/)
    await userEvent.click(await screen.findByRole('radio', { name: 'Otro problema / no sé cuál' }))
    await userEvent.click(await screen.findByRole('radio', { name: 'Ya funciona' }))
    await userEvent.click(screen.getByRole('button', { name: 'Enviar reporte' }))
    await screen.findByRole('heading', { name: 'Tu reporte' })
    expect(rechazos).toBe(1)
    expect(localStorage.getItem('ra.token')).toBe('token-anonimo')
  })

  it('mis reportes lista lo enviado', async () => {
    renderizarApp('/reportes')
    expect(await screen.findByRole('link', { name: /Fuera de servicio.*ZOCALO/i })).toBeInTheDocument()
  })
})

describe('Corroboración (F4-7)', () => {
  function rutaConFallaProbable() {
    const alt = structuredClone(datos.planFlujo1.alternativas[0])
    alt.equipos_criticos[3].estado = 'FALLA_PROBABLE'
    sessionStorage.setItem('ra.busqueda', JSON.stringify({
      origen: { nombre: 'Tasqueña', lat: 0, lon: 0 },
      destino: { nombre: 'Museo', lat: 0, lon: 0 },
      respuesta: { ...datos.planFlujo1, alternativas: [alt] },
    }))
    return alt.equipos_criticos[3]
  }

  it('pregunta por el equipo con posible falla y registra la respuesta', async () => {
    const equipo = rutaConFallaProbable()
    renderizarApp('/ruta/1')
    const pregunta = screen.getByRole('region', { name: /Sigue fuera de servicio/ })
    expect(pregunta).toHaveTextContent(equipo.referencia)
    await userEvent.click(within(pregunta).getByRole('button', { name: 'Sí, sigue fuera de servicio' }))
    expect(await within(pregunta).findByRole('status')).toHaveTextContent('¡Gracias!')
    const voto = peticiones.find((p) => p.url.includes('/corroboraciones'))!
    expect(new URL(voto.url).pathname).toBe(`/api/equipos/${equipo.codigo}/corroboraciones`)
    expect(JSON.parse(voto.cuerpo)).toEqual({ voto: 'CONFIRMA' })
  })

  it('si ya había respondido, lo dice', async () => {
    servidor.use(http.post('*/api/equipos/*', () => HttpResponse.json({ detail: 'x' }, { status: 409 })))
    rutaConFallaProbable()
    renderizarApp('/ruta/1')
    await userEvent.click(screen.getByRole('button', { name: 'No, ya funciona' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Ya habías respondido')
  })

  it('no pregunta si ningún equipo tiene posible falla', () => {
    sessionStorage.setItem('ra.busqueda', JSON.stringify({
      origen: { nombre: 'A', lat: 0, lon: 0 }, destino: { nombre: 'B', lat: 0, lon: 0 }, respuesta: datos.planFlujo1,
    }))
    renderizarApp('/ruta/1')
    expect(screen.queryByRole('region', { name: /Sigue fuera de servicio/ })).not.toBeInTheDocument()
  })
})

describe('Moderación (F4-6)', () => {
  it('pide el token y rechaza uno sin rol', async () => {
    renderizarApp('/moderacion')
    await userEvent.type(screen.getByLabelText('Token de moderación'), 'token-anonimo')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('no tiene rol de moderación')
  })

  it('muestra la cola con desglose y permite confirmar', async () => {
    localStorage.setItem('ra.token-moderacion', TOKEN_MODERADOR)
    renderizarApp('/moderacion')
    const tarjeta = await screen.findByRole('article', { name: /Fuera de servicio · Zócalo/ })
    expect(within(tarjeta).getByText('“Tiene cinta amarilla”')).toBeInTheDocument()
    expect(within(tarjeta).getByText('0.72')).toBeInTheDocument()
    expect(within(tarjeta).getByText(/1 confirman/)).toBeInTheDocument()
    await userEvent.click(within(tarjeta).getByRole('button', { name: /Confirmar/ }))
    expect(await screen.findByText('No hay reportes por revisar.')).toBeInTheDocument()
    expect(simulacion.decisiones).toEqual(['CONFIRMAR'])
  })
})
