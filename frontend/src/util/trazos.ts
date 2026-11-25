// Recorte del trazo oficial de una línea (GTFS) entre dos estaciones, para que el mapa de una
// ruta pinte sólo el tramo que se usa y no la línea completa ni la red entera.
export type Punto = [number, number] // (lat, lon)

// Si la estación queda a más de esto del trazo más cercano, el trazo no le corresponde
// (p. ej. otro ramal) y se usa el respaldo del backend (centros de estación en línea recta).
const TOLERANCIA_M = 400

/** Distancia aproximada en metros (equirectangular: a escala de ciudad el error es mínimo). */
export function distanciaM(a: Punto, b: Punto): number {
  const r = 6_371_000
  const lat = ((a[0] + b[0]) / 2) * (Math.PI / 180)
  const dx = (b[1] - a[1]) * (Math.PI / 180) * Math.cos(lat)
  const dy = (b[0] - a[0]) * (Math.PI / 180)
  return r * Math.hypot(dx, dy)
}

function masCercano(trazo: Punto[], p: Punto): { i: number; d: number } {
  let mejor = { i: 0, d: Infinity }
  trazo.forEach((q, i) => {
    const d = distanciaM(p, q)
    if (d < mejor.d) mejor = { i, d }
  })
  return mejor
}

/**
 * Parte de ``trazos`` (una línea puede tener varios: ramales) que va de ``desde`` a ``hasta``,
 * en ese sentido. Se elige el trazo que pasa más cerca de ambas estaciones y se corta entre
 * sus vértices más cercanos. Devuelve ``null`` si ningún trazo pasa por las dos.
 */
export function recortarTrazo(trazos: Punto[][], desde: Punto, hasta: Punto): Punto[] | null {
  let elegido: { trazo: Punto[]; a: number; b: number; error: number } | null = null
  for (const trazo of trazos) {
    if (trazo.length < 2) continue
    const a = masCercano(trazo, desde)
    const b = masCercano(trazo, hasta)
    if (a.d > TOLERANCIA_M || b.d > TOLERANCIA_M) continue
    const error = a.d + b.d
    if (!elegido || error < elegido.error) elegido = { trazo, a: a.i, b: b.i, error }
  }
  if (!elegido || elegido.a === elegido.b) return null
  const { trazo, a, b } = elegido
  const parte = a < b ? trazo.slice(a, b + 1) : trazo.slice(b, a + 1).reverse()
  // Los extremos exactos de las estaciones, para que el tramo empiece y acabe en ellas.
  return [desde, ...parte, hasta]
}
