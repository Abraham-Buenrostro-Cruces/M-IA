// Cliente de api-core. Los tipos salen de esquema.d.ts, generado desde el OpenAPI de
// FastAPI con `npm run api:tipos`: si el backend cambia un contrato, `tsc` lo detecta aquí.
import type { components } from './esquema'

type Esquemas = components['schemas']
export type Alternativa = Esquemas['AlternativaSalida']
export type CatalogoEstaciones = Esquemas['CatalogoEstaciones']
export type EquipoCritico = Esquemas['EquipoCritico']
export type Estacion = Esquemas['EstacionSalida']
export type EstadoEstacion = Esquemas['EstadoEstacionSalida']
export type Lugar = Esquemas['LugarSalida']
export type PerfilEntrada = Esquemas['PerfilEntrada']
export type PerfilPredefinido = Esquemas['PerfilPredefinido']
export type PeticionPlan = Esquemas['PeticionPlan']
export type RespuestaPlan = Esquemas['RespuestaPlan']
export type TipoMovilidad = PerfilEntrada['tipo_movilidad']
export type Accesibilidad = Estacion['accesibilidad']

export const BASE_API = '/api'

export class ErrorApi extends Error {
  readonly estado: number

  constructor(estado: number, mensaje: string) {
    super(mensaje)
    this.estado = estado
  }
}

async function solicitar<T>(ruta: string, init?: RequestInit): Promise<T> {
  let respuesta: Response
  try {
    respuesta = await fetch(`${BASE_API}${ruta}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
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
  return (await respuesta.json()) as T
}

export const api = {
  perfiles: () => solicitar<PerfilPredefinido[]>('/perfiles'),
  lugares: (q: string, signal?: AbortSignal) =>
    solicitar<Lugar[]>(`/lugares?q=${encodeURIComponent(q)}`, { signal }),
  estaciones: () => solicitar<CatalogoEstaciones>('/estaciones'),
  estadoEstacion: (clave: string) =>
    solicitar<EstadoEstacion>(`/estaciones/${encodeURIComponent(clave)}/estado`),
  planear: (peticion: PeticionPlan) =>
    solicitar<RespuestaPlan>('/rutas/plan', { method: 'POST', body: JSON.stringify(peticion) }),
}
