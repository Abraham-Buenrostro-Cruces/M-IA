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
import { recortarTrazo } from '../util/trazos'
import { SIMBOLO_ASISTENCIA, SIMBOLO_ESTACION, svgSimbolo, type Simbologia } from './simbologia'

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

const COLOR_A_PIE = '#57606a'
const TRANSBORDO: Simbologia = { forma: 'circulo', color: '#1f2328', glifo: 'T', texto: 'Transbordo' }

type Tramo = Alternativa['tramos'][number]

/** Los puntos que se dibujan de un tramo: en transporte, el trazo oficial de su línea recortado
 *  entre la estación de subida y la de bajada; si no se puede, los centros de estación. */
function puntosDe(t: Tramo, lineas: Map<string, Linea>): [number, number][] {
  const respaldo = t.puntos as [number, number][]
  const linea = t.route_id ? lineas.get(t.route_id) : undefined
  if (t.tipo !== 'transporte' || !linea || respaldo.length < 2) return respaldo
  return recortarTrazo(linea.trazos as [number, number][][], respaldo[0], respaldo[respaldo.length - 1]) ?? respaldo
}

/** Mapa de una o varias rutas: sólo las líneas que usan, y sólo entre donde se sube y donde se
 *  baja, con su color oficial; los tramos a pie, punteados en gris. Cada opción se distingue por
 *  el patrón de línea (continua, discontinua, punteada), no sólo por color (WCAG 1.4.1). */
export function MapaRuta({
  alternativas,
  origen,
  destino,
  etiqueta = 'Mapa de las alternativas (la misma información está en la vista de lista)',
  asistencia = [],
}: {
  alternativas: Alternativa[]
  origen: PuntoElegido
  destino: PuntoElegido
  etiqueta?: string
  /** Puntos de la ruta con asistencia (D-26): marcador rojo en su estación. */
  asistencia?: { estacion: string | null; descripcion: string }[]
}) {
  const { data: red } = useQuery({ queryKey: ['red'], queryFn: api.red, staleTime: 10 * 60_000 })
  const lineas = useMemo(() => new Map((red?.lineas ?? []).map((l) => [l.route_id, l])), [red])
  const dibujo = useMemo(
    () => alternativas.map((a) => ({ a, tramos: a.tramos.map((t) => ({ t, puntos: puntosDe(t, lineas) })) })),
    [alternativas, lineas],
  )
  const encuadre = useMemo(() => {
    const todos = dibujo.flatMap((d) => d.tramos.flatMap((x) => x.puntos))
    return todos.length ? todos : ([[origen.lat, origen.lon], [destino.lat, destino.lon]] as [number, number][])
  }, [dibujo, origen, destino])
  const extremos = { forma: 'circulo' as const, color: '#1f2328', glifo: '', texto: '' }
  return (
    <div>
      <Base etiqueta={etiqueta}>
        <Encuadre puntos={encuadre} />
        {dibujo.map(({ a, tramos }) => {
          const e = estiloDe(a)
          const ancho = a.orden === 1 ? 7 : 5
          return tramos.map(({ t, puntos }, i) => {
            const clave = `${a.orden}-${i}`
            if (t.tipo === 'a_pie') {
              return (
                <Polyline key={clave} positions={puntos} className="tramo-a-pie" interactive={false}
                  pathOptions={{ color: COLOR_A_PIE, weight: 3, dashArray: '2 7', opacity: 0.9 }} />
              )
            }
            const color = (t.route_id && lineas.get(t.route_id)?.color) || e.color
            return [
              <Polyline key={`${clave}-borde`} positions={puntos} interactive={false}
                pathOptions={{ color: '#ffffff', weight: ancho + 3, opacity: 0.9, lineCap: 'round' }} />,
              <Polyline key={clave} positions={puntos} className="tramo-transporte" interactive={false}
                pathOptions={{ color, weight: ancho, dashArray: e.dashArray, opacity: 1, lineCap: 'round' }} />,
            ]
          })
        })}
        {dibujo.flatMap(({ a, tramos }) =>
          tramos
            .filter(({ t }) => t.tipo === 'transporte')
            .slice(1) // el primer abordaje no es transbordo
            .map(({ t, puntos }) => {
              const texto = `Opción ${a.orden}: cambia a ${t.linea} en ${t.desde}`
              return <Marker key={`${a.orden}-${texto}`} position={puntos[0]} icon={icono(TRANSBORDO, texto, 22)} title={texto} />
            }),
        )}
        {asistencia.map((p) => {
          const e = p.estacion ? red?.estaciones.find((x) => x.clave === p.estacion) : undefined
          if (!e) return null // p. ej. una caminata larga: está en la lista, no tiene estación
          const texto = `${SIMBOLO_ASISTENCIA.texto}: ${p.descripcion}`
          return (
            <Marker key={p.descripcion} position={[e.lat, e.lon]} icon={icono(SIMBOLO_ASISTENCIA, texto, 28)} title={texto} />
          )
        })}
        <Marker position={[origen.lat, origen.lon]} icon={icono({ ...extremos, glifo: 'O' }, `Origen: ${origen.nombre}`, 26)} title={`Origen: ${origen.nombre}`} />
        <Marker position={[destino.lat, destino.lon]} icon={icono({ ...extremos, glifo: 'D' }, `Destino: ${destino.nombre}`, 26)} title={`Destino: ${destino.nombre}`} />
      </Base>
      <ul className="mt-2 space-y-2" aria-label="Leyenda del mapa">
        {alternativas.map((a) => {
          const e = estiloDe(a)
          const viajes = a.tramos.filter((t) => t.tipo === 'transporte')
          return (
            <li key={a.orden}>
              <span className="font-semibold">
                Opción {a.orden} ({e.nombre}):
              </span>
              <ul className="ml-2 mt-1 space-y-0.5">
                {viajes.map((t, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm">
                    <svg width="36" height="10" aria-hidden="true">
                      <line x1="0" y1="5" x2="36" y2="5" strokeWidth="5" strokeDasharray={e.dashArray}
                        stroke={(t.route_id && lineas.get(t.route_id)?.color) || e.color} />
                    </svg>
                    {t.linea}: de {t.desde} a {t.hasta}
                  </li>
                ))}
                <li className="flex items-center gap-2 text-sm">
                  <svg width="36" height="10" aria-hidden="true">
                    <line x1="0" y1="5" x2="36" y2="5" stroke={COLOR_A_PIE} strokeWidth="3" strokeDasharray="2 7" />
                  </svg>
                  A pie (línea punteada gris)
                </li>
              </ul>
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
