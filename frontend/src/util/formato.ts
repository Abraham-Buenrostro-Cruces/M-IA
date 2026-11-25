// Formatos en español de México para la interfaz.

export function minutos(min: number): string {
  const m = Math.round(min)
  if (m < 60) return `${m} min`
  const h = Math.floor(m / 60)
  return `${h} h ${m % 60} min`
}

export function metros(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`
}

/** "hace 3 h", "hace 25 min", "hace 2 días". `ahora` se inyecta para poder probarlo. */
export function haceCuanto(iso: string | null | undefined, ahora: Date = new Date()): string {
  if (!iso) return 'sin verificación'
  const seg = Math.max(0, (ahora.getTime() - new Date(iso).getTime()) / 1000)
  if (seg < 60) return 'hace un momento'
  if (seg < 3600) return `hace ${Math.round(seg / 60)} min`
  // Hasta 48 h se muestra en horas: coincide con las advertencias del motor ("hace 30 h").
  if (seg < 48 * 3600) return `hace ${Math.round(seg / 3600)} h`
  const dias = Math.round(seg / 86400)
  return `hace ${dias} ${dias === 1 ? 'día' : 'días'}`
}

const FECHA = new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' })
export function fechaHora(iso: string | null | undefined): string {
  return iso ? FECHA.format(new Date(iso)) : ''
}

export const NOMBRE_ESTADO_EQUIPO: Record<string, string> = {
  OPERATIVO: 'Operativo',
  FALLA_PROBABLE: 'Posible falla',
  FALLA_CONFIRMADA: 'Falla confirmada',
  DESCONOCIDO: 'Sin información',
  MANTENIMIENTO: 'En mantenimiento',
}

export const NOMBRE_TIPO_EQUIPO: Record<string, string> = {
  ELEVADOR: 'Elevador',
  RAMPA: 'Rampa',
  SALVAESCALERAS: 'Salvaescaleras',
  ESCALERA_ELECTRICA: 'Escalera eléctrica',
  ACCESO_A_NIVEL: 'Acceso a nivel',
}

export const NOMBRE_SISTEMA: Record<string, string> = {
  METRO: 'Metro',
  METROBUS: 'Metrobús',
  TREN_LIGERO: 'Tren Ligero',
}
