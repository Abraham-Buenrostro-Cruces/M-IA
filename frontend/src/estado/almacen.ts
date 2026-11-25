// Persistencia local (sólo en este dispositivo).
//
// - Perfil de movilidad: dato sensible (D-16). Nunca se envía a terceros; sólo viaja
//   dentro de POST /rutas/plan para calcular la ruta (regla de seguridad 6).
// - Ruta activa: copia de la alternativa elegida, para consultarla sin señal (F3-6).
import { useCallback, useSyncExternalStore } from 'react'
import type { Alternativa, PerfilEntrada, RespuestaPlan } from '../api/cliente'

const CLAVE_PERFIL = 'ra.perfil'
const CLAVE_RUTA_ACTIVA = 'ra.ruta-activa'

export type RutaActiva = {
  alternativa: Alternativa
  origen: string
  destino: string
  guardada_en: string // ISO
  datos_demostracion: boolean
  calculado_en: RespuestaPlan['calculado_en']
}

const oyentes = new Set<() => void>()
function avisar() {
  oyentes.forEach((f) => f())
}
function suscribir(f: () => void) {
  oyentes.add(f)
  const alAlmacenar = (e: StorageEvent) => e.key?.startsWith('ra.') && f()
  window.addEventListener('storage', alAlmacenar)
  return () => {
    oyentes.delete(f)
    window.removeEventListener('storage', alAlmacenar)
  }
}

function leer<T>(clave: string): T | null {
  try {
    const texto = localStorage.getItem(clave)
    return texto ? (JSON.parse(texto) as T) : null
  } catch {
    return null // dato corrupto o almacenamiento no disponible: se trata como vacío
  }
}

// useSyncExternalStore compara por identidad: se cachea el texto leído para devolver el
// mismo objeto mientras no cambie.
const cache = new Map<string, { texto: string | null; valor: unknown }>()
function instantanea<T>(clave: string): T | null {
  const texto = localStorage.getItem(clave)
  const previo = cache.get(clave)
  if (previo && previo.texto === texto) return previo.valor as T | null
  const valor = leer<T>(clave)
  cache.set(clave, { texto, valor })
  return valor
}

function escribir(clave: string, valor: unknown) {
  if (valor === null) localStorage.removeItem(clave)
  else localStorage.setItem(clave, JSON.stringify(valor))
  avisar()
}

export function usePerfil() {
  const perfil = useSyncExternalStore(suscribir, () => instantanea<PerfilEntrada>(CLAVE_PERFIL))
  const guardar = useCallback((p: PerfilEntrada | null) => escribir(CLAVE_PERFIL, p), [])
  return [perfil, guardar] as const
}

export function useRutaActiva() {
  const ruta = useSyncExternalStore(suscribir, () => instantanea<RutaActiva>(CLAVE_RUTA_ACTIVA))
  const guardar = useCallback((r: RutaActiva | null) => escribir(CLAVE_RUTA_ACTIVA, r), [])
  return [ruta, guardar] as const
}
