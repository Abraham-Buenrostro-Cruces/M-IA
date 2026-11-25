// Cliente de api-core. Los tipos salen de esquema.d.ts, generado desde el OpenAPI de
// FastAPI con `npm run api:tipos`: si el backend cambia un contrato, `tsc` lo detecta aquí.
import type { components } from './esquema'

type Esquemas = components['schemas']
export type Alternativa = Esquemas['AlternativaSalida']
export type CatalogoEstaciones = Esquemas['CatalogoEstaciones']
export type EquipoCritico = Esquemas['EquipoCritico']
export type EquipoEstado = Esquemas['EquipoEstado']
export type Estacion = Esquemas['EstacionSalida']
export type EstadoEstacion = Esquemas['EstadoEstacionSalida']
export type Lugar = Esquemas['LugarSalida']
export type OtraOpcion = Esquemas['OtraOpcionSalida']
export type PerfilEntrada = Esquemas['PerfilEntrada']
export type PerfilPredefinido = Esquemas['PerfilPredefinido']
export type PeticionPlan = Esquemas['PeticionPlan']
export type RespuestaPlan = Esquemas['RespuestaPlan']
export type TipoMovilidad = PerfilEntrada['tipo_movilidad']
export type Accesibilidad = Estacion['accesibilidad']
export type ReporteEntrada = Esquemas['ReporteEntrada']
export type Reporte = Esquemas['ReporteSalida']
export type ReporteModeracion = Esquemas['ReporteModeracion']
export type TipoProblema = ReporteEntrada['tipo_problema']
export type Yo = Esquemas['YoSalida']
export type Linea = Esquemas['LineaSalida']
export type Red = Esquemas['RedSalida']
type Subida = Esquemas['SubidaSalida']
type Token = Esquemas['TokenSalida']

export const BASE_API = '/api'

export class ErrorApi extends Error {
  readonly estado: number

  constructor(estado: number, mensaje: string) {
    super(mensaje)
    this.estado = estado
  }
}

async function solicitarCruda(ruta: string, init?: RequestInit): Promise<Response> {
  let respuesta: Response
  try {
    respuesta = await fetch(ruta.startsWith(BASE_API) ? ruta : `${BASE_API}${ruta}`, init)
  } catch {
    throw new ErrorApi(0, 'No hay conexión con el servidor. Revisa tu señal e intenta de nuevo.')
  }
  if (!respuesta.ok) {
    let detalle = `Error ${respuesta.status}`
    try {
      const cuerpo = await respuesta.json()
      if (typeof cuerpo?.detail === 'string') detalle = cuerpo.detail
    } catch {
      // cuerpo no JSON: se queda el mensaje genérico
    }
    throw new ErrorApi(respuesta.status, detalle)
  }
  return respuesta
}

async function solicitar<T>(ruta: string, init?: RequestInit): Promise<T> {
  const r = await solicitarCruda(ruta, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  return (r.status === 204 ? undefined : await r.json()) as T
}

// --------------------------------------------------------------------------- identidad (D-23)
// Usuario anónimo por dispositivo: se crea la primera vez que hace falta. No pide datos
// personales; sólo permite distinguir personas (corroboración) y llevar la reputación.

const CLAVE_TOKEN = 'ra.token'
export const CLAVE_TOKEN_MODERACION = 'ra.token-moderacion'
let creando: Promise<string> | null = null

async function tokenAnonimo(renovar = false): Promise<string> {
  if (renovar) localStorage.removeItem(CLAVE_TOKEN)
  const guardado = localStorage.getItem(CLAVE_TOKEN)
  if (guardado) return guardado
  creando ??= solicitar<Token>('/usuarios/anonimo', { method: 'POST' })
    .then((t) => {
      localStorage.setItem(CLAVE_TOKEN, t.token)
      return t.token
    })
    .finally(() => {
      creando = null
    })
  return creando
}

/** Petición con identidad. Si el token ya no es válido (p. ej. se reinició la base), se
 *  crea uno nuevo y se reintenta una vez. */
async function conIdentidad<T>(ruta: string, init: RequestInit = {}, crudo = false): Promise<T> {
  const intentar = async (token: string) => {
    const headers = { ...init.headers, Authorization: `Bearer ${token}` }
    return crudo
      ? ((await solicitarCruda(ruta, { ...init, headers })) as T)
      : solicitar<T>(ruta, { ...init, headers })
  }
  try {
    return await intentar(await tokenAnonimo())
  } catch (e) {
    if (e instanceof ErrorApi && e.estado === 401) return intentar(await tokenAnonimo(true))
    throw e
  }
}

function conModeracion<T>(ruta: string, init: RequestInit = {}, crudo = false): Promise<T> {
  const token = localStorage.getItem(CLAVE_TOKEN_MODERACION) ?? ''
  const headers = { ...init.headers, Authorization: `Bearer ${token}` }
  return crudo
    ? (solicitarCruda(ruta, { ...init, headers }) as Promise<T>)
    : solicitar<T>(ruta, { ...init, headers })
}

const json = (datos: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(datos) })

export const api = {
  perfiles: () => solicitar<PerfilPredefinido[]>('/perfiles'),
  lugares: (q: string, signal?: AbortSignal) =>
    solicitar<Lugar[]>(`/lugares?q=${encodeURIComponent(q)}`, { signal }),
  estaciones: () => solicitar<CatalogoEstaciones>('/estaciones'),
  red: () => solicitar<Red>('/red'),
  estadoEstacion: (clave: string) =>
    solicitar<EstadoEstacion>(`/estaciones/${encodeURIComponent(clave)}/estado`),
  planear: (peticion: PeticionPlan) => solicitar<RespuestaPlan>('/rutas/plan', json(peticion)),

  // Reportes (F4-1, F4-2)
  /** Sube la foto con la URL de un solo uso y devuelve el id de la subida. */
  subirFoto: async (foto: File) => {
    const subida = await conIdentidad<Subida>('/reportes/subidas', { method: 'POST' })
    if (!subida.tipos_permitidos.includes(foto.type))
      throw new ErrorApi(415, 'La foto debe ser JPEG, PNG o WEBP.')
    if (foto.size > subida.tamano_maximo_bytes) throw new ErrorApi(413, 'La foto supera 10 MB.')
    await solicitarCruda(subida.url_subida, {
      method: subida.metodo,
      body: foto,
      headers: { 'Content-Type': foto.type },
    })
    return subida.id_subida
  },
  crearReporte: (r: ReporteEntrada) => conIdentidad<Reporte>('/reportes', json(r)),
  misReportes: () => conIdentidad<Reporte[]>('/reportes/mios'),
  reporte: (id: string) => conIdentidad<Reporte>(`/reportes/${id}`),
  /** Foto saneada (sin EXIF, rostros difuminados) como URL de objeto local. */
  evidencia: async (id: string, moderacion = false) => {
    const r = moderacion
      ? await conModeracion<Response>(`/evidencias/${id}`, {}, true)
      : await conIdentidad<Response>(`/evidencias/${id}`, {}, true)
    return URL.createObjectURL(await r.blob())
  },

  // Corroboración (F4-7). El código de equipo lleva "/": va tal cual en la ruta.
  corroborar: (codigo: string, voto: 'CONFIRMA' | 'NIEGA') =>
    conIdentidad<unknown>(`/equipos/${codigo}/corroboraciones`, json({ voto })),

  // Moderación (F4-6)
  yoModerador: () => conModeracion<Yo>('/usuarios/yo'),
  colaModeracion: () => conModeracion<ReporteModeracion[]>('/moderacion/reportes'),
  decidir: (id: string, decision: 'CONFIRMAR' | 'RECHAZAR') =>
    conModeracion<Reporte>(`/moderacion/reportes/${id}/decision`, json({ decision })),
}
