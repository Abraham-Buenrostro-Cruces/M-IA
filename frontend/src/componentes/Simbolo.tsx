import { svgSimbolo, type Simbologia } from './simbologia'

export { SIMBOLO_EQUIPO, SIMBOLO_ESTACION, SIMBOLO_IAR } from './simbologia'

export function Simbolo({ s, tam = 20 }: { s: Simbologia; tam?: number }) {
  return (
    <span
      aria-hidden="true"
      className="inline-block shrink-0 align-middle"
      // SVG generado sólo a partir de las constantes de simbologia.ts (sin datos externos).
      dangerouslySetInnerHTML={{ __html: svgSimbolo(s, tam) }}
    />
  )
}

/** Símbolo + texto visible. Es la forma por defecto de mostrar un estado. */
export function Estado({ s, className = '' }: { s: Simbologia; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 font-medium ${className}`} style={{ color: s.color }}>
      <Simbolo s={s} />
      <span>{s.texto}</span>
    </span>
  )
}
