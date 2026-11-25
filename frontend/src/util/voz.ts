// Utilidades de voz (F5): leer en voz alta con la síntesis del navegador (F5-4), preparar
// el audio grabado para la API y el texto que se lee de un resultado. La síntesis es del
// propio navegador: el texto no sale del dispositivo.
import type { RespuestaPlan } from '../api/cliente'

export function puedeHablar(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window
}

/** Lee ``texto`` en voz alta en español (es-MX si hay). Corta lo que se estuviera leyendo. */
export function hablar(texto: string): void {
  if (!puedeHablar() || !texto) return
  const s = window.speechSynthesis
  s.cancel()
  const u = new SpeechSynthesisUtterance(texto)
  u.lang = 'es-MX'
  const voces = s.getVoices()
  u.voice = voces.find((v) => v.lang === 'es-MX') ?? voces.find((v) => v.lang.startsWith('es')) ?? null
  u.rate = 0.95 // un poco más lento: mejor comprensión en la calle y para adultos mayores
  s.speak(u)
}

export function callar(): void {
  if (puedeHablar()) window.speechSynthesis.cancel()
}

/** 'audio/webm;codecs=opus' -> 'webm'. Los formatos que acepta la API. */
export function formatoDe(mime: string): 'webm' | 'ogg' | 'mp4' | 'wav' {
  if (mime.includes('ogg')) return 'ogg'
  if (mime.includes('mp4') || mime.includes('aac')) return 'mp4'
  if (mime.includes('wav')) return 'wav'
  return 'webm'
}

export async function base64De(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer())
  let binario = ''
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binario += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  }
  return btoa(binario)
}

/**
 * Lo que se lee del resultado (F5-4). Con ruta segura: la recomendada con su IAR, sus
 * equipos críticos y que hay plan B (regla 4). Sin ruta segura: eso primero (regla 5) y
 * luego las otras opciones, con dónde se necesita ayuda (D-26).
 */
export function textoDeResultado(r: RespuestaPlan): string {
  const partes: string[] = []
  const mejor = r.alternativas[0]
  if (r.hay_ruta_segura && mejor) {
    partes.push(`Te recomiendo: ${mejor.resumen}.`)
    partes.push(`Índice de accesibilidad ${Math.round(mejor.iar)} de 100, ${mejor.categoria_iar}.`)
    partes.push(`Tiempo estimado: ${Math.round(mejor.tiempo_total_min)} minutos.`)
    const n = mejor.equipos_criticos.length
    if (n) {
      const menos = [...mejor.equipos_criticos].sort((a, b) => a.prob_operativo - b.prob_operativo)[0]
      partes.push(
        `Depende de ${n} ${n === 1 ? 'equipo' : 'equipos'}; el de menor confianza es ${menos.referencia} de ${menos.nombre_estacion}.`,
      )
    } else {
      partes.push('No depende de elevadores ni rampas.')
    }
    if (mejor.planes_b.length) partes.push('Cada equipo tiene un plan B en los pasos.')
    for (const a of mejor.advertencias) partes.push(`Atención: ${a}`)
    if (r.alternativas.length > 1) partes.push(`Hay ${r.alternativas.length - 1} alternativas más en pantalla.`)
    return partes.join(' ')
  }
  partes.push(r.aviso ?? 'No hay ruta segura hasta tu destino.')
  for (const o of r.otras_opciones) {
    partes.push(`Otra opción: ${o.titulo}.`)
    if (o.tipo === 'con_asistencia' && o.puntos_asistencia.length) {
      partes.push(`Necesitas ayuda en: ${o.puntos_asistencia.map((p) => p.descripcion).join('; ')}.`)
    }
  }
  if (!r.otras_opciones.length) partes.push(...r.sugerencias)
  return partes.join(' ')
}
