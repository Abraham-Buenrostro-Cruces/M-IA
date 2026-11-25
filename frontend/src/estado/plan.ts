// Búsqueda en curso (origen, destino y respuesta), compartida entre Planear, Resultados y
// Detalle. Se copia a sessionStorage para que recargar /resultados no pierda la respuesta;
// no se guarda entre sesiones porque los estados de los equipos caducan.
import { createContext, useContext } from 'react'
import type { Lugar, RespuestaPlan } from '../api/cliente'

export type PuntoElegido = {
  nombre: string
  detalle?: string
  lat: number
  lon: number
  clave_estacion?: string | null
}

export type Busqueda = {
  origen: PuntoElegido
  destino: PuntoElegido
  respuesta: RespuestaPlan
  /** La búsqueda se pidió por voz: Resultados lee la recomendación en voz alta (F5-4). */
  porVoz?: boolean
}

export const CLAVE_BUSQUEDA = 'ra.busqueda'

export type ValorContexto = {
  busqueda: Busqueda | null
  guardar: (b: Busqueda | null) => void
}

export const ContextoPlan = createContext<ValorContexto | null>(null)

export function useBusqueda() {
  const v = useContext(ContextoPlan)
  if (!v) throw new Error('useBusqueda requiere <ProveedorPlan>')
  return v
}

export function puntoDesdeLugar(l: Lugar): PuntoElegido {
  return { nombre: l.nombre, detalle: l.detalle, lat: l.lat, lon: l.lon, clave_estacion: l.clave_estacion }
}

/** Ubicación para la API: estación por clave (más precisa en el grafo) o coordenadas. */
export function ubicacionApi(p: PuntoElegido) {
  return p.clave_estacion ? { clave_estacion: p.clave_estacion } : { lat: p.lat, lon: p.lon }
}
