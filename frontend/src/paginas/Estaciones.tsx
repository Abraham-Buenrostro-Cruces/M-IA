// Estaciones por accesibilidad actual (F3-3), en lista o en mapa (equivalentes).
import { useQuery } from '@tanstack/react-query'
import { lazy, Suspense, useState } from 'react'
import { Checkbox } from 'react-aria-components'
import { api, type Accesibilidad, type Estacion } from '../api/cliente'
import { AvisoDemo } from '../componentes/AvisoDemo'
import { SelectorVista, type Vista } from '../componentes/SelectorVista'
import { Estado, SIMBOLO_EQUIPO, SIMBOLO_ESTACION } from '../componentes/Simbolo'
import { haceCuanto, NOMBRE_SISTEMA, NOMBRE_TIPO_EQUIPO } from '../util/formato'

const MapaEstaciones = lazy(() =>
  import('../componentes/Mapas').then((m) => ({ default: m.MapaEstaciones })),
)

const ORDEN: Accesibilidad[] = ['CON_FALLAS', 'ACCESIBLE', 'NO_ACCESIBLE', 'SIN_DATOS']

function Equipos({ clave }: { clave: string }) {
  const { data, isPending, isError } = useQuery({
    queryKey: ['estado-estacion', clave],
    queryFn: () => api.estadoEstacion(clave),
  })
  if (isPending) return <p className="px-3 pb-2">Cargando equipos…</p>
  if (isError) return <p className="px-3 pb-2 text-[#b42318]">No pudimos cargar los equipos.</p>
  if (!data.equipos.length) return <p className="px-3 pb-2">Sin elevadores, rampas ni escaleras eléctricas en el inventario.</p>
  return (
    <ul className="space-y-1 px-3 pb-3">
      {data.equipos.map((e) => (
        <li key={e.codigo} className="flex flex-wrap gap-x-2">
          <Estado s={SIMBOLO_EQUIPO[e.estado] ?? SIMBOLO_EQUIPO.DESCONOCIDO} />
          <span>
            {NOMBRE_TIPO_EQUIPO[e.tipo] ?? e.tipo}: {e.referencia}
          </span>
          <span className="text-sm text-texto-suave">verificado {haceCuanto(e.ultima_verificacion)}</span>
        </li>
      ))}
    </ul>
  )
}

function ItemEstacion({ e }: { e: Estacion }) {
  const [abierta, setAbierta] = useState(false)
  return (
    <li className="rounded border border-gray-300">
      <details onToggle={(ev) => setAbierta((ev.target as HTMLDetailsElement).open)}>
        <summary className="flex min-h-11 cursor-pointer flex-wrap items-center gap-x-3 px-3 py-2">
          <strong>{e.nombre}</strong>
          <span className="text-sm text-texto-suave">
            {NOMBRE_SISTEMA[e.sistema]} · Línea {e.lineas.join(', ')}
          </span>
          <Estado s={SIMBOLO_ESTACION[e.accesibilidad]} className="ml-auto" />
        </summary>
        {abierta && <Equipos clave={e.clave} />}
      </details>
    </li>
  )
}

export function Estaciones() {
  const [vista, setVista] = useState<Vista>('lista')
  const [soloPiloto, setSoloPiloto] = useState(true)
  const { data, isPending, isError } = useQuery({ queryKey: ['estaciones'], queryFn: api.estaciones })

  const estaciones = (data?.estaciones ?? []).filter((e) => !soloPiloto || e.accesibilidad !== 'SIN_DATOS')

  return (
    <>
      <h1 className="text-3xl font-bold text-marca-oscuro">Estaciones</h1>
      <p className="mt-2">Accesibilidad actual para quien no puede usar escaleras.</p>
      {data && <AvisoDemo visible={data.datos_demostracion} />}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <Checkbox
          isSelected={soloPiloto}
          onChange={setSoloPiloto}
          className="flex min-h-11 cursor-pointer items-center gap-2 data-[focus-visible]:outline-3 data-[focus-visible]:outline-[var(--color-foco)]"
        >
          {({ isSelected }) => (
            <>
              <span aria-hidden="true" className="text-xl">
                {isSelected ? '☑' : '☐'}
              </span>
              Sólo el corredor piloto (Líneas 2 y 3)
            </>
          )}
        </Checkbox>
        <SelectorVista vista={vista} alCambiar={setVista} />
      </div>

      {isPending && <p className="mt-4">Cargando estaciones…</p>}
      {isError && (
        <p role="alert" className="mt-4 rounded bg-red-50 p-3 text-[#b42318]">
          No pudimos cargar las estaciones. Revisa tu conexión.
        </p>
      )}

      {data &&
        (vista === 'mapa' ? (
          <div className="mt-4">
            <Suspense fallback={<p>Cargando mapa…</p>}>
              <MapaEstaciones estaciones={estaciones} />
            </Suspense>
          </div>
        ) : (
          ORDEN.map((estado) => {
            const grupo = estaciones.filter((e) => e.accesibilidad === estado)
            if (!grupo.length) return null
            const s = SIMBOLO_ESTACION[estado]
            return (
              <section key={estado} aria-labelledby={`grupo-${estado}`} className="mt-6">
                <h2 id={`grupo-${estado}`} className="text-xl font-bold">
                  <Estado s={s} /> <span className="text-texto">({grupo.length})</span>
                </h2>
                <ul className="mt-2 space-y-2">
                  {grupo.map((e) => (
                    <ItemEstacion key={e.clave} e={e} />
                  ))}
                </ul>
              </section>
            )
          })
        ))}
    </>
  )
}
