// Seguimiento de un reporte y lista de mis reportes (F4-1).
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'
import { api, type Reporte } from '../api/cliente'
import { FotoEvidencia } from '../componentes/FotoEvidencia'
import { Estado, SIMBOLO_EQUIPO } from '../componentes/Simbolo'
import { ESTADO_VALIDACION, fechaHora, haceCuanto, NOMBRE_TIPO_PROBLEMA } from '../util/formato'

function TituloEstado({ r }: { r: Reporte }) {
  const e = ESTADO_VALIDACION[r.estado_validacion] ?? { titulo: r.estado_validacion, detalle: '' }
  return (
    <div aria-live="polite" className="mt-4 rounded border-l-4 border-marca bg-blue-50 p-4">
      <p className="text-xl font-bold">{e.titulo}</p>
      <p className="mt-1">{e.detalle}</p>
    </div>
  )
}

export function SeguimientoReporte() {
  const { id = '' } = useParams()
  const { data: r, isPending, isError, error } = useQuery({
    queryKey: ['reporte', id],
    queryFn: () => api.reporte(id),
    // Se consulta cada 1.5 s mientras siga en verificación; luego cada 15 s (corroboración
    // o moderación pueden cambiarlo después).
    refetchInterval: (q) => (q.state.data?.estado_validacion === 'PENDIENTE' ? 1500 : 15_000),
  })

  if (isPending) return <p>Cargando reporte…</p>
  if (isError)
    return (
      <p role="alert" className="rounded bg-red-50 p-3 text-[#b42318]">
        {error.message}
      </p>
    )

  return (
    <>
      <h1 className="text-3xl font-bold text-marca-oscuro">Tu reporte</h1>
      <TituloEstado r={r} />
      <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
        <dt className="font-semibold">Problema</dt>
        <dd>{NOMBRE_TIPO_PROBLEMA[r.tipo_problema] ?? r.tipo_problema}</dd>
        <dt className="font-semibold">Enviado</dt>
        <dd title={fechaHora(r.creado_en)}>{haceCuanto(r.creado_en)}</dd>
        {r.estado_equipo && (
          <>
            <dt className="font-semibold">Estado del equipo ahora</dt>
            <dd>
              <Estado s={SIMBOLO_EQUIPO[r.estado_equipo] ?? SIMBOLO_EQUIPO.DESCONOCIDO} />
            </dd>
          </>
        )}
        {r.puntaje_confianza !== null && r.puntaje_confianza !== undefined && (
          <>
            <dt className="font-semibold">Confianza</dt>
            <dd>{Math.round(r.puntaje_confianza * 100)} de 100</dd>
          </>
        )}
      </dl>
      {r.motivos.length > 0 && (
        <>
          <h2 className="mt-4 font-semibold">Qué influyó</h2>
          <ul className="mt-1 list-disc pl-6">
            {r.motivos.map((m) => (
              <li key={m}>{m[0].toUpperCase() + m.slice(1)}</li>
            ))}
          </ul>
        </>
      )}
      {r.id_evidencia && r.estado_validacion !== 'PENDIENTE' && (
        <div className="mt-4">
          <h2 className="font-semibold">Tu foto, tal como la verán otras personas</h2>
          <FotoEvidencia id={r.id_evidencia} alt="Tu foto, sin datos de ubicación y con los rostros difuminados" />
        </div>
      )}
      <p className="mt-6 flex flex-wrap gap-4">
        <Link to="/reportes" className="text-marca underline">
          Mis reportes
        </Link>
        <Link to="/reportar" className="text-marca underline">
          Hacer otro reporte
        </Link>
      </p>
    </>
  )
}

export function MisReportes() {
  const { data, isPending, isError } = useQuery({ queryKey: ['mis-reportes'], queryFn: api.misReportes })
  return (
    <>
      <h1 className="text-3xl font-bold text-marca-oscuro">Mis reportes</h1>
      {isPending && <p className="mt-4">Cargando…</p>}
      {isError && (
        <p role="alert" className="mt-4 rounded bg-red-50 p-3 text-[#b42318]">
          No pudimos cargar tus reportes.
        </p>
      )}
      {data?.length === 0 && (
        <p className="mt-4">
          Aún no has enviado reportes.{' '}
          <Link to="/reportar" className="text-marca underline">
            Reportar un problema
          </Link>
        </p>
      )}
      <ul className="mt-4 space-y-2">
        {data?.map((r) => (
          <li key={r.id_reporte}>
            <Link to={`/reportes/${r.id_reporte}`} className="block rounded border border-gray-300 p-3 no-underline hover:bg-gray-50">
              <strong>{NOMBRE_TIPO_PROBLEMA[r.tipo_problema]}</strong> · {r.clave_estacion.replace(/^METRO-/, '').replaceAll('_', ' ')}
              <span className="block text-sm text-texto-suave">
                {ESTADO_VALIDACION[r.estado_validacion]?.titulo} · {haceCuanto(r.creado_en)}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </>
  )
}
