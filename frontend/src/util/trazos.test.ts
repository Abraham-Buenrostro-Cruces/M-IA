import { describe, expect, it } from 'vitest'
import { recortarTrazo, type Punto } from './trazos'

// Línea recta norte–sur con un vértice cada ~111 m.
const linea: Punto[] = Array.from({ length: 11 }, (_, i) => [19.4 + i * 0.001, -99.13])
// Otro ramal, lejos (~1 km al oriente).
const ramal: Punto[] = Array.from({ length: 5 }, (_, i) => [19.4 + i * 0.001, -99.12])

describe('recortarTrazo', () => {
  it('corta sólo entre las dos estaciones, en el sentido del viaje', () => {
    const desde: Punto = [19.4021, -99.1301]
    const hasta: Punto = [19.4059, -99.1299]
    const r = recortarTrazo([linea], desde, hasta)!
    expect(r[0]).toEqual(desde)
    expect(r.at(-1)).toEqual(hasta)
    // Vértices 2 a 6 de la línea, sin el resto.
    expect(r.slice(1, -1)).toEqual(linea.slice(2, 7))
    // En sentido contrario, el mismo tramo al revés.
    expect(recortarTrazo([linea], hasta, desde)!.slice(1, -1)).toEqual(linea.slice(2, 7).reverse())
  })

  it('elige el trazo que pasa por ambas estaciones', () => {
    const r = recortarTrazo([ramal, linea], [19.401, -99.13], [19.404, -99.13])!
    expect(r.slice(1, -1)).toEqual(linea.slice(1, 5))
  })

  it('sin un trazo que pase cerca de las dos, devuelve null (se usa el respaldo)', () => {
    expect(recortarTrazo([linea], [19.401, -99.13], [19.401, -99.10])).toBeNull()
    expect(recortarTrazo([], [19.401, -99.13], [19.404, -99.13])).toBeNull()
  })
})
