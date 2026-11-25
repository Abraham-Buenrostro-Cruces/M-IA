// Mapas con Leaflet sobre un fondo gris claro (estilo de mapa de transporte).
// El mapa es complementario: la misma información está siempre en la vista de lista
// (F3-4), así que una persona que no puede usar el mapa no pierde nada.
import 'leaflet/dist/leaflet.css'
import { useQuery } from '@tanstack/react-query'
import L from 'leaflet'
import { useEffect, useMemo } from 'react'
import { CircleMarker, MapContainer, Marker, Polyline, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet'
import { api, type Alternativa, type Estacion, type Linea } from '../api/cliente'
import type { PuntoElegido } from '../estado/plan'
import { NOMBRE_SISTEMA } from '../util/formato'
import { SIMBOLO_ESTACION, svgSimbolo, type Simbologia } from './simbologia'

const CENTRO_CDMX: [number, number] = [19.4326, -99.1332]
// Fondo: mosaicos de OpenStreetMap pasados a gris claro con un filtro CSS (.fondo-gris en
// index.css), para que las líneas de colores destaquen como en un mapa de transporte.
// Se probó el fondo claro de CARTO, pero desde 2026 exige llave de API (los mosaicos salen
// con marca de agua); así no depende de una llave ni de otro proveedor.
const FONDO = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const ATRIBUCION =
  '&copy; colaboradores de <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
const COLOR_SIN_DATO = '#6b7280'

// Grosor por sistema: el Metro domina visualmente; los trenes van en medio y el Metrobús es más delgado.
const GROSOR: Record<string, { linea: number; borde: number; estacion: number }> = {
  METRO: { linea: 5, borde: 8, estacion: 4.5 },
  TREN_LIGERO: { linea: 4, borde: 7, estacion: 4 },
  TREN_SUBURBANO: { linea: 4, borde: 7, estacion: 4 },
  TREN_INTERURBANO: { linea: 4, borde: 7, estacion: 4 },
  METROBUS: { linea: 3, borde: 5, estacion: 3 },
}

// Cada alternativa: color + patrón de línea distinto (no sólo color).
const ESTILO_ALTERNATIVA = [
  { color: '#0b4f8a', dashArray: undefined, nombre: 'línea continua' },
  { color: '#7a2e8e', dashArray: '10 8', nombre: 'línea discontinua' },
  { color: '#8a4b0b', dashArray: '2 8', nombre: 'línea punteada' },
]

function icono(s: Simbologia, etiqueta: string, tam = 24) {
  return L.divIcon({
    className: 'marcador-ra',
    // El texto oculto hace que el marcador enfocable tenga nombre accesible.
    html: `${svgSimbolo(s, tam)}<span class="sr-only">${etiqueta}</span>`,
    iconSize: [tam, tam],
    iconAnchor: [tam / 2, tam / 2],
  })
}

function Encuadre({ puntos }: { puntos: [number, number][] }) {
  const mapa = useMap()
  useEffect(() => {
    if (puntos.length) mapa.fitBounds(L.latLngBounds(puntos), { padding: [30, 30] })
  }, [mapa, puntos])
  return null
}

function Base({ etiqueta, children }: { etiqueta: string; children: React.ReactNode }) {
  return (
    <section aria-label={etiqueta}>
      <MapContainer center={CENTRO_CDMX} zoom={12} className="h-[65vh] min-h-80 w-full rounded border border-gray-300" keyboard>
        <TileLayer attribution={ATRIBUCION} url={FONDO} maxZoom={19} className="fondo-gris" />
        {children}
      </MapContainer>
    </section>
  )
}

/** Líneas con su trazo real y color oficial. Primero todos los bordes blancos y después
 *  los colores: así, donde dos líneas se cruzan, el borde de una no tapa el color de otra. */
function CapaLineas({ lineas, atenuada = false }: { lineas: Linea[]; atenuada?: boolean }) {
  const trazos = lineas.flatMap((l) =>
    l.trazos.map((t, i) => ({ clave: `${l.route_id}-${i}`, l, puntos: t as [number, number][] })),
  )
  return (
    <>
      {trazos.map(({ clave, l, puntos }) => (
        <Polyline
          key={`borde-${clave}`}
          positions={puntos}
          interactive={false}
          pathOptions={{ color: '#ffffff', weight: GROSOR[l.sistema].borde, opacity: atenuada ? 0.6 : 1, lineCap: 'round', lineJoin: 'round' }}
        />
      ))}
      {trazos.map(({ clave, l, puntos }) => (
        <Polyline
          key={`linea-${clave}`}
          positions={puntos}
          interactive={false}
          className={`linea-red linea-${l.sistema.toLowerCase()}`}
          pathOptions={{ color: l.color ?? COLOR_SIN_DATO, weight: GROSOR[l.sistema].linea, opacity: atenuada ? 0.35 : 1, lineCap: 'round', lineJoin: 'round' }}
        />
      ))}
    </>
  )
}

/** Estaciones como puntos discretos sobre la línea (estilo mapa de transporte). */
function CapaPuntos({ estaciones }: { estaciones: Estacion[] }) {
  return (
    <>
      {estaciones.map((e) => (
        <CircleMarker
          key={e.clave}
          center={[e.lat, e.lon]}
          radius={GROSOR[e.sistema].estacion}
          pathOptions={{ color: '#1f2328', weight: 1.5, fillColor: '#ffffff', fillOpacity: 1 }}
        >
          <Tooltip>
            {e.nombre} · {NOMBRE_SISTEMA[e.sistema]} {e.lineas.join(', ')}
          </Tooltip>
        </CircleMarker>
      ))}
    </>
  )
}

/** Estilo de una alternativa según su número de opción (no su posición en la lista): así
 *  la opción 2 se ve igual en el mapa general y en su mapa individual ("Ver mapa"). */
function estiloDe(a: Alternativa) {
  return ESTILO_ALTERNATIVA[(a.orden - 1) % ESTILO_ALTERNATIVA.length]
}

export function MapaRuta({
  alternativas,
  origen,
  destino,
  etiqueta = 'Mapa de las alternativas (la misma información está en la vista de lista)',
}: {
  alternativas: Alternativa[]
  origen: PuntoElegido
  destino: PuntoElegido
  etiqueta?: string
}) {
  const { data: red } = useQuery({ queryKey: ['red'], queryFn: api.red, staleTime: 10 * 60_000 })
  const puntos = useMemo(() => alternativas.flatMap((a) => a.trazo as [number, number][]), [alternativas])
  const extremos = { forma: 'circulo' as const, color: '#1f2328', glifo: '', texto: '' }
  return (
    <div>
      <Base etiqueta={etiqueta}>
        <Encuadre puntos={puntos.length ? puntos : [[origen.lat, origen.lon], [destino.lat, destino.lon]]} />
        {/* La red del Metro y Tren Ligero, atenuada, como contexto de la ruta. */}
        {red && <CapaLineas lineas={red.lineas.filter((l) => l.sistema !== 'METROBUS')} atenuada />}
        {alternativas.map((a) => {
          const e = estiloDe(a)
          return (
            <Polyline
              key={a.orden}
              positions={a.trazo as [number, number][]}
              pathOptions={{ color: e.color, dashArray: e.dashArray, weight: a.orden === 1 ? 7 : 5, opacity: 0.95 }}
            />
          )
        })}
        <Marker position={[origen.lat, origen.lon]} icon={icono({ ...extremos, glifo: 'O' }, `Origen: ${origen.nombre}`, 26)} title={`Origen: ${origen.nombre}`} />
        <Marker position={[destino.lat, destino.lon]} icon={icono({ ...extremos, glifo: 'D' }, `Destino: ${destino.nombre}`, 26)} title={`Destino: ${destino.nombre}`} />
      </Base>
      <ul className="mt-2 space-y-1" aria-label="Leyenda del mapa">
        {alternativas.map((a) => {
          const e = estiloDe(a)
          return (
            <li key={a.orden} className="flex items-center gap-2">
              <svg width="36" height="10" aria-hidden="true">
                <line x1="0" y1="5" x2="36" y2="5" stroke={e.color} strokeWidth="4" strokeDasharray={e.dashArray} />
              </svg>
              Opción {a.orden} ({e.nombre}): {a.resumen}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

/** Red completa con su color oficial; encima, la accesibilidad de las estaciones con datos. */
export function MapaEstaciones({
  lineas,
  estaciones,
  accesibilidad,
}: {
  lineas: Linea[]
  estaciones: Estacion[]
  accesibilidad: boolean
}) {
  const puntos = useMemo(
    () => lineas.flatMap((l) => l.trazos.flat() as [number, number][]),
    [lineas],
  )
  const conDatos = accesibilidad ? estaciones.filter((e) => e.accesibilidad !== 'SIN_DATOS') : []
  const claves = new Set(conDatos.map((e) => e.clave))
  return (
    <Base etiqueta="Mapa de la red de transporte con la accesibilidad de las estaciones (la misma información está en la vista de lista)">
      <Encuadre puntos={puntos} />
      <CapaLineas lineas={lineas} />
      <CapaPuntos estaciones={estaciones.filter((e) => !claves.has(e.clave))} />
      {conDatos.map((e) => {
        const s = SIMBOLO_ESTACION[e.accesibilidad]
        const etiqueta = `${e.nombre}, ${NOMBRE_SISTEMA[e.sistema]}: ${s.texto}`
        return (
          <Marker key={e.clave} position={[e.lat, e.lon]} icon={icono(s, etiqueta, 16)} title={etiqueta}>
            <Popup>
              <strong>{e.nombre}</strong>
              <br />
              {NOMBRE_SISTEMA[e.sistema]} · Línea {e.lineas.join(', ')}
              <br />
              {s.texto}
            </Popup>
          </Marker>
        )
      })}
    </Base>
  )
}
