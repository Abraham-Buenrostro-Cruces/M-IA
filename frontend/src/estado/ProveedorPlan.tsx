import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { CLAVE_BUSQUEDA, ContextoPlan, type Busqueda } from './plan'

function leerSesion(): Busqueda | null {
  try {
    const t = sessionStorage.getItem(CLAVE_BUSQUEDA)
    return t ? (JSON.parse(t) as Busqueda) : null
  } catch {
    return null
  }
}

export function ProveedorPlan({ children }: { children: ReactNode }) {
  const [busqueda, setBusqueda] = useState<Busqueda | null>(leerSesion)
  const guardar = useCallback((b: Busqueda | null) => {
    setBusqueda(b)
    if (b) sessionStorage.setItem(CLAVE_BUSQUEDA, JSON.stringify(b))
    else sessionStorage.removeItem(CLAVE_BUSQUEDA)
  }, [])
  const valor = useMemo(() => ({ busqueda, guardar }), [busqueda, guardar])
  return <ContextoPlan.Provider value={valor}>{children}</ContextoPlan.Provider>
}

