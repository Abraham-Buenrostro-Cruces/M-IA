// Mapas con Leaflet + OpenStreetMap (respaldo sin llave de Google Maps, 08-mvp).
// El mapa es complementario: la misma información está siempre en la vista de lista
// (F3-4), así que una persona que no puede usar el mapa no pierde nada.
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import { useEffect } from 'react'
import type { Alternativa, Estacion } from '../api/cliente'
import type { PuntoElegido } from '../estado/plan'
import { NOMBRE_SISTEMA } from '../util/formato'
import { SIMBOLO_ESTACION, svgSimbolo, type Simbologia } from './simbologia'

const CENTRO_CDMX: [number, number] = [19.4326, -99.1332]
const ATRIBUCION = '&copy; colaboradores de <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

// Cada alternativa: color + patrón de línea distinto (no sólo color).
const ESTILO_ALTERNATIVA = [
  { color: '#0b4f8a', dashArray: undefined, nombre: 'línea continua' },
  { color: '#7a2e8e', dashArray: '10 8', nombre: 'línea discontinua' },
  { color: '#8a4b0b', dashArray: '2 8', nombre: 'línea punteada' },
]

function icono(s: Simbologia, etiqueta: string) {
  return L.divIcon({
    className: 'marcador-ra',
    // El texto oculto hace que el marcador enfocable tenga nombre accesible.
    html: `${svgSimbolo(s, 26)}<span class="sr-only">${etiqueta}</span>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
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
      <MapContainer center={CENTRO_CDMX} zoom={13} className="h-[60vh] min-h-80 w-full rounded border border-gray-300" keyboard>
        <TileLayer attribution={ATRIBUCION} url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
        {children}
      </MapContainer>
    </section>
  )
}

export function MapaRuta({
  alternativas,
  origen,
  destino,
}: {
  alternativas: Alternativa[]
  origen: PuntoElegido
  destino: PuntoElegido
}) {
  const puntos = alternativas.flatMap((a) => a.trazo as [number, number][])
  const extremos = { forma: 'circulo' as const, color: '#1f2328', glifo: '', texto: '' }
  return (
    <div>
      <Base etiqueta="Mapa de las alternativas (la misma información está en la vista de lista)">
        <Encuadre puntos={puntos.length ? puntos : [[origen.lat, origen.lon], [destino.lat, destino.lon]]} />
        {alternativas.map((a, i) => {
          const e = ESTILO_ALTERNATIVA[i % ESTILO_ALTERNATIVA.length]
          return (
            <Polyline
              key={a.orden}
              positions={a.trazo as [number, number][]}
              pathOptions={{ color: e.color, dashArray: e.dashArray, weight: i === 0 ? 6 : 4, opacity: 0.9 }}
            />
          )
        })}
        <Marker position={[origen.lat, origen.lon]} icon={icono({ ...extremos, glifo: 'O' }, `Origen: ${origen.nombre}`)} title={`Origen: ${origen.nombre}`} />
        <Marker position={[destino.lat, destino.lon]} icon={icono({ ...extremos, glifo: 'D' }, `Destino: ${destino.nombre}`)} title={`Destino: ${destino.nombre}`} />
      </Base>
      <ul className="mt-2 space-y-1" aria-label="Leyenda del mapa">
        {alternativas.map((a, i) => {
          const e = ESTILO_ALTERNATIVA[i % ESTILO_ALTERNATIVA.length]
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

export function MapaEstaciones({ estaciones }: { estaciones: Estacion[] }) {
  const puntos = estaciones.map((e) => [e.lat, e.lon] as [number, number])
  return (
    <Base etiqueta="Mapa de estaciones por accesibilidad (la misma información está en la vista de lista)">
      <Encuadre puntos={puntos} />
      {estaciones.map((e) => {
        const s = SIMBOLO_ESTACION[e.accesibilidad]
        const etiqueta = `${e.nombre}, ${NOMBRE_SISTEMA[e.sistema]}: ${s.texto}`
        return (
          <Marker key={e.clave} position={[e.lat, e.lon]} icon={icono(s, etiqueta)} title={etiqueta}>
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
