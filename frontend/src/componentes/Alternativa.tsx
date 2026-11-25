// Presentación de una alternativa: tarjeta (resultados) y detalle (detalle y ruta activa).
// Regla de seguridad 4: toda ruta muestra IAR, equipos críticos, última verificación y plan B.
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import type { Alternativa, EquipoCritico } from '../api/cliente'
import { fechaHora, haceCuanto, metros, minutos } from '../util/formato'
import { MapaDesplegable } from './MapaDesplegable'
import { PreguntaCorroboracion } from './PreguntaCorroboracion'
import { Estado, SIMBOLO_ASISTENCIA, SIMBOLO_EQUIPO, SIMBOLO_IAR, Simbolo } from './Simbolo'

export function InsigniaIar({ alt }: { alt: Alternativa }) {
  const s = SIMBOLO_IAR[alt.categoria_iar]
  return (
    <p className="inline-flex items-center gap-2 rounded border-2 px-2 py-1" style={{ borderColor: s.color }}>
      <Simbolo s={s} />
      <span>
        <abbr title="Índice de Accesibilidad de Ruta: probabilidad de completar el viaje sin barreras" className="no-underline">
          IAR
        </abbr>{' '}
        <strong className="text-lg">{Math.round(alt.iar)}</strong>
        {' '}<span className="sr-only">de 100</span>
        <span style={{ color: s.color }} className="font-semibold">
          {' '}
          · {s.texto}
        </span>
      </span>
    </p>
  )
}

export function Equipo({ e, ahora }: { e: EquipoCritico; ahora?: Date }) {
  return (
    <li className="flex flex-wrap items-baseline gap-x-2">
      <Estado s={SIMBOLO_EQUIPO[e.estado] ?? SIMBOLO_EQUIPO.DESCONOCIDO} />
      <span>
        {e.referencia[0].toUpperCase() + e.referencia.slice(1)} · {e.nombre_estacion}
      </span>
      <span className="text-sm text-texto-suave" title={fechaHora(e.ultima_verificacion)}>
        verificado {haceCuanto(e.ultima_verificacion, ahora)}
      </span>
    </li>
  )
}

export function Advertencias({ alt }: { alt: Alternativa }) {
  if (!alt.advertencias.length) return null
  return (
    <ul className="mt-3 space-y-1 rounded bg-amber-50 p-3" aria-label="Advertencias">
      {alt.advertencias.map((a) => (
        <li key={a}>
          <span aria-hidden="true">⚠ </span>
          <strong>Atención:</strong> {a}
        </li>
      ))}
    </ul>
  )
}

export function Datos({ alt }: { alt: Alternativa }) {
  return (
    <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
      <div>
        <dt className="text-sm text-texto-suave">Tiempo</dt>
        <dd className="font-semibold">{minutos(alt.tiempo_total_min)}</dd>
      </div>
      <div>
        <dt className="text-sm text-texto-suave">Transbordos</dt>
        <dd className="font-semibold">{alt.transbordos}</dd>
      </div>
      <div>
        <dt className="text-sm text-texto-suave">A pie</dt>
        <dd className="font-semibold">{metros(alt.distancia_pie_m)}</dd>
      </div>
    </dl>
  )
}

/** ``mapa``: el mapa de esta opción, si la página lo ofrece (botón "Ver mapa"). Se pasa ya
 *  construido para que la tarjeta no dependa de Leaflet, que se carga sólo al abrirlo. */
export function TarjetaAlternativa({
  alt,
  ahora,
  mapa,
}: {
  alt: Alternativa
  ahora?: Date
  mapa?: ReactNode
}) {
  const id = `alt-${alt.orden}`
  return (
    <article aria-labelledby={id} className="rounded-lg border border-gray-300 p-4 shadow-sm">
      <h3 id={id} className="text-lg font-bold">
        Opción {alt.orden}
        {alt.recomendada && <span className="ml-2 rounded bg-marca px-2 py-0.5 text-sm text-white">Recomendada</span>}
      </h3>
      <p className="mt-1">{alt.resumen}</p>
      <div className="mt-2">
        <InsigniaIar alt={alt} />
      </div>
      <Datos alt={alt} />
      <h4 className="mt-3 font-semibold">Equipos críticos</h4>
      {alt.equipos_criticos.length ? (
        <ul className="mt-1 space-y-1">
          {alt.equipos_criticos.map((e) => (
            <Equipo key={e.codigo} e={e} ahora={ahora} />
          ))}
        </ul>
      ) : (
        <p className="mt-1">No depende de elevadores ni rampas.</p>
      )}
      <Advertencias alt={alt} />
      <div className="mt-4 flex flex-wrap gap-3">
        <Link
          to={`/ruta/${alt.orden}`}
          aria-label={`Ver pasos y plan B de la opción ${alt.orden}`}
          className="inline-flex min-h-11 items-center rounded bg-marca px-4 font-semibold text-white no-underline hover:bg-marca-oscuro"
        >
          Ver pasos y plan B
        </Link>
        {mapa && <MapaDesplegable nombre={`la opción ${alt.orden}`}>{mapa}</MapaDesplegable>}
      </div>
    </article>
  )
}

/** Pasos numerados. En la ruta con asistencia (D-26), los que necesitan ayuda van en rojo
 *  con símbolo y texto, nunca sólo con color (WCAG 1.4.1). */
export function ListaPasos({ alt }: { alt: Alternativa }) {
  return (
    <ol className="mt-2 list-decimal space-y-2 pl-6">
      {alt.pasos.map((p, i) => (
        <li key={i} className={p.asistencia ? 'rounded border-l-4 border-[#b42318] bg-red-50 py-1 pl-2' : undefined}>
          {p.descripcion}
          {p.duracion_s >= 60 && (
            <span className="text-sm text-texto-suave"> ({minutos(p.duracion_s / 60)})</span>
          )}
          {p.asistencia && (
            <span className="mt-1 flex items-center gap-2 font-semibold text-[#b42318]">
              <Simbolo s={SIMBOLO_ASISTENCIA} />
              <span>Necesitas ayuda del personal: {p.asistencia}</span>
            </span>
          )}
        </li>
      ))}
    </ol>
  )
}

export function DetalleAlternativa({ alt, ahora }: { alt: Alternativa; ahora?: Date }) {
  return (
    <div>
      <p className="text-lg">{alt.resumen}</p>
      <div className="mt-2">
        <InsigniaIar alt={alt} />
      </div>
      <Datos alt={alt} />
      <p className="mt-3">{alt.explicacion}</p>
      <Advertencias alt={alt} />

      <h2 className="mt-6 text-xl font-bold">Pasos</h2>
      <ListaPasos alt={alt} />

      <h2 className="mt-6 text-xl font-bold">Equipos críticos</h2>
      {alt.equipos_criticos.length ? (
        <ul className="mt-2 space-y-1">
          {alt.equipos_criticos.map((e) => (
            <Equipo key={e.codigo} e={e} ahora={ahora} />
          ))}
        </ul>
      ) : (
        <p className="mt-2">Esta ruta no depende de elevadores ni rampas.</p>
      )}
      {alt.equipos_criticos
        .filter((e) => e.estado === 'FALLA_PROBABLE')
        .map((e) => (
          <PreguntaCorroboracion key={e.codigo} equipo={e} />
        ))}

      <h2 className="mt-6 text-xl font-bold">Plan B</h2>
      <ul className="mt-2 space-y-2">
        {alt.planes_b.map((b) => (
          <li key={b.equipo} className="rounded border-l-4 border-marca bg-blue-50 p-3">
            {b.descripcion}
          </li>
        ))}
      </ul>
    </div>
  )
}
