// Tarjeta de una "otra opción" cuando no hay ruta segura (D-26). Va siempre después del aviso
// "No hay ruta segura hasta tu destino" y aparte de las alternativas; nunca se presenta como
// recomendada (regla de seguridad 5). La ruta con asistencia es la última y marca en rojo,
// con símbolo y texto, dónde se necesita ayuda y por qué.
import type { ReactNode } from 'react'
import type { OtraOpcion } from '../api/cliente'
import { metros } from '../util/formato'
import { Advertencias, Datos, Equipo, InsigniaIar, ListaPasos } from './Alternativa'
import { MapaDesplegable } from './MapaDesplegable'
import { SIMBOLO_ASISTENCIA, SIMBOLO_EQUIPO, Simbolo } from './Simbolo'

const ETIQUETA: Record<OtraOpcion['tipo'], { texto: string; clase: string }> = {
  estacion_cercana: { texto: 'Llega cerca de tu destino', clase: 'bg-blue-100 text-marca-oscuro' },
  si_se_repara: { texto: 'No disponible hoy', clase: 'bg-amber-100 text-[#7a4f00]' },
  con_asistencia: { texto: 'Requiere asistencia', clase: 'bg-[#b42318] text-white' },
}

export function TarjetaOtraOpcion({
  opcion,
  ahora,
  mapa,
}: {
  opcion: OtraOpcion
  ahora?: Date
  mapa?: ReactNode
}) {
  const id = `otra-${opcion.tipo}`
  const ruta = opcion.ruta
  const asistencia = opcion.tipo === 'con_asistencia'
  const etiqueta = ETIQUETA[opcion.tipo]
  return (
    <article
      aria-labelledby={id}
      className={`rounded-lg border p-4 shadow-sm ${asistencia ? 'border-2 border-[#b42318]' : 'border-gray-300'}`}
    >
      <h3 id={id} className="text-lg font-bold">
        {opcion.titulo}
        <span className={`ml-2 rounded px-2 py-0.5 text-sm ${etiqueta.clase}`}>{etiqueta.texto}</span>
      </h3>
      <p className="mt-1">{opcion.descripcion}</p>
      <p className="mt-2 text-texto-suave">{ruta.resumen}</p>

      <div className="mt-2">
        {opcion.tipo === 'si_se_repara' && <p className="text-sm font-semibold">IAR si se repara:</p>}
        <InsigniaIar alt={ruta} />
      </div>
      <Datos alt={ruta} />
      {opcion.distancia_restante_m != null && (
        <p className="mt-2">
          <strong>Te faltan unos {metros(opcion.distancia_restante_m)}</strong> en línea recta desde esa salida hasta
          tu destino.
        </p>
      )}

      {opcion.equipos_a_reparar.length > 0 && (
        <>
          <h4 className="mt-3 font-semibold">Qué falta reparar</h4>
          <ul className="mt-1 space-y-1">
            {opcion.equipos_a_reparar.map((m) => (
              <li key={m} className="flex items-baseline gap-2">
                <Simbolo s={SIMBOLO_EQUIPO.FALLA_CONFIRMADA} />
                <span>{m[0].toUpperCase() + m.slice(1)}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {asistencia && (
        <>
          <h4 className="mt-3 font-semibold text-[#b42318]">Dónde necesitas ayuda del personal</h4>
          <ul className="mt-1 space-y-1">
            {opcion.puntos_asistencia.map((p) => (
              <li key={p.descripcion} className="flex items-baseline gap-2 font-semibold text-[#b42318]">
                <Simbolo s={SIMBOLO_ASISTENCIA} />
                <span>{p.descripcion}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {!asistencia && ruta.equipos_criticos.length > 0 && (
        <>
          <h4 className="mt-3 font-semibold">Equipos críticos</h4>
          <ul className="mt-1 space-y-1">
            {ruta.equipos_criticos.map((e) => (
              <Equipo key={e.codigo} e={e} ahora={ahora} />
            ))}
          </ul>
        </>
      )}
      <Advertencias alt={ruta} />

      <details className="mt-3">
        <summary className="min-h-11 cursor-pointer py-2 font-semibold text-marca">Ver pasos de esta opción</summary>
        <ListaPasos alt={ruta} />
      </details>
      {mapa && (
        <div className="mt-3 flex flex-wrap gap-3">
          <MapaDesplegable nombre={opcion.titulo}>{mapa}</MapaDesplegable>
        </div>
      )}
    </article>
  )
}
