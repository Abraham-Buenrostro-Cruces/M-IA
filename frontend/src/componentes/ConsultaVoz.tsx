// Consulta por voz (F5-1, F5-3, D-24). Graba una frase corta, la manda a /voz/consulta y,
// si falta algo, muestra (y lee) la pregunta de aclaración con sus opciones. Cuando todo está
// claro, entrega origen, destino y restricciones a Planear, que pide la ruta con el perfil
// del dispositivo: el perfil nunca va en la consulta de voz (regla 6).
//
// Accesibilidad: botón grande que se usa con teclado o lector de pantalla; el estado
// ("Escuchando…", "Procesando…") se anuncia en una región viva; quien no puede o no quiere
// hablar puede escribir la misma frase.
import { useEffect, useRef, useState } from 'react'
import { Button, Input, Label, TextField } from 'react-aria-components'
import { api, type ContextoVoz, type ConsultaVoz as Consulta, type Lugar, type RespuestaVoz } from '../api/cliente'
import { base64De, callar, formatoDe, hablar } from '../util/voz'

const DURACION_MAX_MS = 15_000 // una frase; más largo casi siempre es ruido de fondo

const boton =
  'inline-flex min-h-11 items-center justify-center rounded px-4 font-semibold outline-none data-[focus-visible]:outline-3 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-[var(--color-foco)] data-[disabled]:opacity-60'

export type ResultadoVoz = {
  origen: Lugar | null // null: usar la ubicación del teléfono
  destino: Lugar
  max_transbordos: number | null
  caminar_poco: boolean
}

type Estado = 'inactivo' | 'escuchando' | 'procesando'

function nombreOpcion(o: Lugar): string {
  return o.detalle ? `${o.nombre} (${o.detalle})` : o.nombre
}

export function ConsultaVoz({ alListo }: { alListo: (r: ResultadoVoz) => void }) {
  const [estado, setEstado] = useState<Estado>('inactivo')
  const [respuesta, setRespuesta] = useState<RespuestaVoz | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [texto, setTexto] = useState('')
  const grabadora = useRef<MediaRecorder | null>(null)
  const tope = useRef<number | undefined>(undefined)
  const contexto = respuesta?.estado === 'aclaracion' ? respuesta.contexto : undefined
  const puedeGrabar = typeof window !== 'undefined' && 'MediaRecorder' in window && !!navigator.mediaDevices

  useEffect(() => () => {
    window.clearTimeout(tope.current)
    grabadora.current?.stream.getTracks().forEach((t) => t.stop())
    callar()
  }, [])

  async function consultar(c: Consulta) {
    setEstado('procesando')
    setError(null)
    try {
      const r = await api.voz(c)
      setRespuesta(r)
      hablar(r.mensaje)
      if (r.estado === 'listo' && r.contexto.destino) {
        alListo({
          origen: r.contexto.usar_ubicacion_origen ? null : (r.contexto.origen ?? null),
          destino: r.contexto.destino,
          max_transbordos: r.contexto.restricciones?.max_transbordos ?? null,
          caminar_poco: r.contexto.restricciones?.caminar_poco ?? false,
        })
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No pudimos procesar la consulta.')
    } finally {
      setEstado('inactivo')
    }
  }

  async function empezar() {
    setError(null)
    callar() // que la app no se oiga a sí misma
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const g = new MediaRecorder(stream)
      const partes: Blob[] = []
      g.ondataavailable = (e) => e.data.size && partes.push(e.data)
      g.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        window.clearTimeout(tope.current)
        const audio = new Blob(partes, { type: g.mimeType })
        if (!audio.size) {
          setEstado('inactivo')
          setError('No se grabó nada. Intenta de nuevo.')
          return
        }
        await consultar({ audio_b64: await base64De(audio), formato: formatoDe(g.mimeType), contexto })
      }
      grabadora.current = g
      g.start()
      setEstado('escuchando')
      tope.current = window.setTimeout(() => g.state === 'recording' && g.stop(), DURACION_MAX_MS)
    } catch {
      setEstado('inactivo')
      setError('No pudimos usar el micrófono. Revisa el permiso o escribe tu consulta.')
    }
  }

  function terminar() {
    if (grabadora.current?.state === 'recording') grabadora.current.stop()
  }

  function elegir(campo: 'origen' | 'destino', lugar: Lugar | null) {
    if (!contexto) return
    const nuevo: ContextoVoz = { ...contexto, campo: null, pendiente: null }
    if (campo === 'destino' && lugar) nuevo.destino = lugar
    if (campo === 'origen') {
      nuevo.origen = lugar
      nuevo.usar_ubicacion_origen = lugar === null
    }
    void consultar({ contexto: nuevo })
  }

  const aviso =
    estado === 'escuchando'
      ? 'Escuchando… di tu origen y tu destino. Pulsa «Terminar» cuando acabes.'
      : estado === 'procesando'
        ? 'Procesando…'
        : ''
  const aclaracion = respuesta?.estado === 'aclaracion' ? respuesta.aclaracion : null

  return (
    <section aria-labelledby="titulo-voz" className="mt-6 rounded border border-gray-300 p-4">
      <h2 id="titulo-voz" className="text-xl font-bold">
        Pídela con tu voz
      </h2>
      <p className="mt-1 text-sm text-texto-suave">
        Por ejemplo: «De Tasqueña al Museo de la Ciudad, sin transbordos». Tu perfil no se envía con la voz.
      </p>

      {puedeGrabar && (
        <Button
          onPress={estado === 'escuchando' ? terminar : empezar}
          isDisabled={estado === 'procesando'}
          className={`${boton} mt-3 w-full text-lg ${estado === 'escuchando' ? 'bg-[#b42318] text-white' : 'bg-marca text-white'}`}
        >
          <span aria-hidden="true">{estado === 'escuchando' ? '■ ' : '🎤 '}</span>
          {estado === 'escuchando' ? 'Terminar' : aclaracion ? 'Responder con tu voz' : 'Hablar'}
        </Button>
      )}
      <p role="status" aria-live="polite" className="mt-2 min-h-6 font-semibold">
        {aviso}
      </p>

      <form
        className="mt-1 flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (texto.trim()) void consultar({ texto: texto.trim(), contexto })
          setTexto('')
        }}
      >
        <TextField value={texto} onChange={setTexto} className="flex min-w-48 flex-1 flex-col">
          <Label className="text-sm font-semibold">
            {puedeGrabar ? 'O escríbelo como lo dirías' : 'Escribe lo que dirías'}
          </Label>
          <Input className="mt-1 min-h-11 rounded border border-gray-500 px-3" maxLength={300} />
        </TextField>
        <Button type="submit" isDisabled={estado !== 'inactivo' || !texto.trim()} className={`${boton} border border-marca text-marca`}>
          Enviar
        </Button>
      </form>

      {respuesta && respuesta.transcripcion && (
        <p className="mt-3">
          Entendí: «{respuesta.transcripcion}»
          {respuesta.transcripcion_simulada && (
            <span className="ml-1 rounded bg-amber-50 px-1 text-sm">
              Transcripción simulada (modo local, sin reconocimiento de voz real)
            </span>
          )}
        </p>
      )}
      {respuesta && respuesta.estado !== 'aclaracion' && <p className="mt-2 font-semibold">{respuesta.mensaje}</p>}

      {aclaracion && (
        <div role="group" aria-labelledby="pregunta-voz" className="mt-3 rounded border-l-4 border-marca bg-blue-50 p-3">
          <p id="pregunta-voz" className="font-semibold">
            {aclaracion.pregunta}
          </p>
          {(aclaracion.opciones.length > 0 || aclaracion.permite_ubicacion) && (
            <ul className="mt-2 flex flex-wrap gap-2">
              {aclaracion.opciones.map((o) => (
                <li key={`${o.clave_estacion ?? o.nombre}`}>
                  <Button onPress={() => elegir(aclaracion.campo, o)} className={`${boton} border border-marca bg-white text-marca`}>
                    {nombreOpcion(o)}
                  </Button>
                </li>
              ))}
              {aclaracion.permite_ubicacion && (
                <li>
                  <Button onPress={() => elegir('origen', null)} className={`${boton} border border-marca bg-white text-marca`}>
                    <span aria-hidden="true">⌖ </span>Desde mi ubicación
                  </Button>
                </li>
              )}
            </ul>
          )}
        </div>
      )}

      {error && (
        <p role="alert" className="mt-2 rounded bg-red-50 p-2 text-[#b42318]">
          {error}
        </p>
      )}
    </section>
  )
}
