/** Distancia de gran círculo (haversine) en metros. */
export function distanciaM(a: { lat: number; lon: number }, b: { lat: number; lon: number }): number {
  const r = 6_371_000
  const rad = (g: number) => (g * Math.PI) / 180
  const dp = rad(b.lat - a.lat)
  const dl = rad(b.lon - a.lon)
  const h = Math.sin(dp / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dl / 2) ** 2
  return 2 * r * Math.asin(Math.sqrt(h))
}
