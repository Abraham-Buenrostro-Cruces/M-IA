// Simbología de estados: color + forma + texto (F3-3). La información nunca depende sólo del
// color (WCAG 1.4.1): cada estado tiene una forma distinta y siempre se acompaña de texto.
// La misma definición se usa en las listas (React) y en los marcadores del mapa (SVG en texto).
import type { Accesibilidad } from '../api/cliente'

export type Forma = 'circulo' | 'triangulo' | 'cuadrado' | 'rombo'

export type Simbologia = { forma: Forma; color: string; glifo: string; texto: string }

// Colores con contraste ≥ 4.5:1 sobre blanco (texto) y ≥ 3:1 como objeto gráfico.
const VERDE = '#1a7f37'
const AMBAR = '#9a6700'
const ROJO = '#b42318'
const GRIS = '#57606a'
const PIZARRA = '#475467'

export const SIMBOLO_ESTACION: Record<Accesibilidad, Simbologia> = {
  ACCESIBLE: { forma: 'circulo', color: VERDE, glifo: '✓', texto: 'Accesible' },
  CON_FALLAS: { forma: 'triangulo', color: AMBAR, glifo: '!', texto: 'Con fallas hoy' },
  NO_ACCESIBLE: { forma: 'cuadrado', color: GRIS, glifo: '✕', texto: 'No accesible' },
  SIN_DATOS: { forma: 'rombo', color: PIZARRA, glifo: '?', texto: 'Sin datos' },
}

export const SIMBOLO_EQUIPO: Record<string, Simbologia> = {
  OPERATIVO: { forma: 'circulo', color: VERDE, glifo: '✓', texto: 'Operativo' },
  FALLA_PROBABLE: { forma: 'triangulo', color: AMBAR, glifo: '!', texto: 'Posible falla' },
  FALLA_CONFIRMADA: { forma: 'cuadrado', color: ROJO, glifo: '✕', texto: 'Falla confirmada' },
  MANTENIMIENTO: { forma: 'cuadrado', color: ROJO, glifo: '✕', texto: 'En mantenimiento' },
  DESCONOCIDO: { forma: 'rombo', color: PIZARRA, glifo: '?', texto: 'Sin información' },
}

export const SIMBOLO_IAR: Record<'alta' | 'media' | 'baja', Simbologia> = {
  alta: { forma: 'circulo', color: VERDE, glifo: '✓', texto: 'Alta' },
  media: { forma: 'triangulo', color: AMBAR, glifo: '!', texto: 'Media' },
  baja: { forma: 'cuadrado', color: ROJO, glifo: '✕', texto: 'Baja' },
}

function figura(forma: Forma, color: string): string {
  switch (forma) {
    case 'circulo':
      return `<circle cx="12" cy="12" r="10" fill="${color}"/>`
    case 'triangulo':
      return `<polygon points="12,2 23,21 1,21" fill="${color}"/>`
    case 'cuadrado':
      return `<rect x="2.5" y="2.5" width="19" height="19" rx="2" fill="${color}"/>`
    case 'rombo':
      return `<polygon points="12,1 23,12 12,23 1,12" fill="${color}"/>`
  }
}

/** SVG en texto para los marcadores de Leaflet (divIcon). */
export function svgSimbolo(s: Simbologia, tam = 24): string {
  const y = s.forma === 'triangulo' ? 17.5 : 16.5
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="${tam}" height="${tam}" viewBox="0 0 24 24" aria-hidden="true">` +
    `${figura(s.forma, s.color)}<text x="12" y="${y}" text-anchor="middle" font-size="12" ` +
    `font-weight="700" fill="#fff" font-family="system-ui, sans-serif">${s.glifo}</text></svg>`
  )
}
