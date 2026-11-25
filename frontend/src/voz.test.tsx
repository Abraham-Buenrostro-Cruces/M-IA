// Consulta por voz en la PWA (F5-1, F5-3, F5-4). La API simulada responde con salidas reales
// de POST /voz/consulta (src/pruebas/datos/voz-*.json).
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { datos, peticiones } from './pruebas/api-simulada'
import { violacionesGraves } from './pruebas/accesibilidad'
import { renderizarApp } from './pruebas/renderizar'
import type { RespuestaPlan } from './api/cliente'
import { textoDeResultado } from './util/voz'

const planFlujo1 = datos.planFlujo1 as unknown as RespuestaPlan
const planSinRuta = datos.planSinRuta as unknown as RespuestaPlan

const PERFIL_SILLA = JSON.stringify({ tipo_movilidad: 'silla_manual' })
const leido = vi.fn()

// jsdom no trae síntesis de voz ni grabación: se simulan.
class Locucion {
  lang = ''
  voice = null
  rate = 1
  text: string
  constructor(text: string) {
    this.text = text
  }
}
class GrabadoraFalsa {
  static ultima: GrabadoraFalsa | null = null
  state = 'inactive'
  mimeType = 'audio/webm;codecs=opus'
  ondataavailable: ((e: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  stream = { getTracks: () => [{ stop: () => {} }] }
  constructor() {
    GrabadoraFalsa.ultima = this
  }
  start() {
    this.state = 'recording'
  }
  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['audio de prueba'], { type: this.mimeType }) })
    this.onstop?.()
  }
}

beforeEach(() => {
  leido.mockReset()
  vi.stubGlobal('speechSynthesis', { speak: (u: Locucion) => leido(u.text), cancel: () => {}, getVoices: () => [] })
  vi.stubGlobal('SpeechSynthesisUtterance', Locucion)
  vi.stubGlobal('MediaRecorder', GrabadoraFalsa)
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia: vi.fn(async () => ({ getTracks: () => [{ stop: () => {} }] })) },
  })
  localStorage.setItem('ra.perfil', PERFIL_SILLA)
})
afterEach(() => vi.unstubAllGlobals())

const cuerpos = (ruta: string) =>
  peticiones.filter((p) => new URL(p.url).pathname === ruta).map((p) => JSON.parse(p.cuerpo))

describe('Consulta por voz (F5)', () => {
  it('escrita como se diría: busca la ruta con lo entendido y la lee en voz alta', async () => {
    renderizarApp()
    await userEvent.type(screen.getByLabelText('O escríbelo como lo dirías'), 'de Tasqueña al Museo de la Ciudad sin transbordos')
    await userEvent.click(screen.getByRole('button', { name: 'Enviar' }))

    expect(await screen.findByRole('heading', { level: 1, name: /Rutas de Tasqueña a Museo/ })).toBeInTheDocument()
    // La consulta de voz no lleva el perfil (regla 6); la ruta sí, con "sin transbordos".
    const [voz] = cuerpos('/api/voz/consulta')
    expect(voz).toEqual({ texto: 'de Tasqueña al Museo de la Ciudad sin transbordos' })
    const [plan] = cuerpos('/api/rutas/plan')
    expect(plan).toMatchObject({ origen: { clave_estacion: 'METRO-TASQUENA' }, max_transbordos: 0, perfil: { tipo_movilidad: 'silla_manual' } })
    // Se leyó lo entendido y, ya en Resultados, la recomendación (F5-4).
    expect(leido).toHaveBeenCalledWith(datos.vozListo.mensaje)
    await waitFor(() => expect(leido).toHaveBeenCalledWith(expect.stringMatching(/^Te recomiendo: /)))
  })

  it('grabando con el micrófono: anuncia el estado y manda el audio', async () => {
    renderizarApp()
    await userEvent.click(screen.getByRole('button', { name: 'Hablar' }))
    expect(screen.getByRole('status')).toHaveTextContent(/Escuchando/)
    await userEvent.click(screen.getByRole('button', { name: 'Terminar' }))
    await screen.findByRole('heading', { level: 1, name: /Rutas de Tasqueña/ })
    const [voz] = cuerpos('/api/voz/consulta')
    expect(voz.formato).toBe('webm')
    expect(atob(voz.audio_b64)).toBe('audio de prueba')
    expect(voz).not.toHaveProperty('perfil')
  })

  it('una aclaración se lee, ofrece opciones y luego pregunta el origen (F5-3)', async () => {
    renderizarApp()
    await userEvent.type(screen.getByLabelText('O escríbelo como lo dirías'), 'quiero ir a Viaducto')
    await userEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    const grupo = await screen.findByRole('group', { name: datos.vozAclaracion.aclaracion!.pregunta })
    expect(leido).toHaveBeenCalledWith(datos.vozAclaracion.mensaje)
    expect(await violacionesGraves(document.body)).toEqual([])

    await userEvent.click(within(grupo).getAllByRole('button')[0])
    const pregunta = await screen.findByRole('group', { name: /Desde dónde sales/ })
    // Elegir en pantalla manda sólo el contexto, con el destino elegido.
    const [, eleccion] = cuerpos('/api/voz/consulta')
    expect(eleccion.texto).toBeUndefined()
    expect(eleccion.contexto.destino.clave_estacion).toBe(datos.vozAclaracion.aclaracion!.opciones[0].clave_estacion)
    expect(within(pregunta).getByRole('button', { name: /Desde mi ubicación/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Responder con tu voz' })).toBeInTheDocument()
  })

  it('sin micrófono, queda la opción de escribir', async () => {
    vi.stubGlobal('MediaRecorder', undefined)
    // @ts-expect-error se quita la API para simular un navegador sin grabación
    delete window.MediaRecorder
    renderizarApp()
    expect(await screen.findByLabelText('Escribe lo que dirías')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Hablar' })).not.toBeInTheDocument()
  })
})

describe('Respuesta hablada (F5-4)', () => {
  it('con ruta segura lee la recomendada con IAR, equipos y plan B (regla 4)', () => {
    const t = textoDeResultado(planFlujo1)
    const mejor = planFlujo1.alternativas[0]
    expect(t).toMatch(new RegExp(`^Te recomiendo: ${mejor.resumen}`))
    expect(t).toContain(`Índice de accesibilidad ${Math.round(mejor.iar)} de 100`)
    expect(t).toContain('plan B')
  })

  it('sin ruta segura lo dice primero y nombra las otras opciones (regla 5, D-26)', () => {
    const t = textoDeResultado(planSinRuta)
    expect(t.startsWith('No hay ruta segura hasta tu destino')).toBe(true)
    expect(t).toContain('Otra opción: Ruta completa con asistencia del personal.')
    expect(t).toContain('Necesitas ayuda en: Lechería: escalera con 20 escalones')
  })
})
