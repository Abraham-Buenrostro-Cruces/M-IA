// Resultados (F3-4). Regla 5: si no hay ruta segura se dice explícitamente, antes que nada.
import { lazy, Suspense, useState } from 'react'
import { Link } from 'react-router'
import { TarjetaAlternativa } from '../componentes/Alternativa'
import { AvisoDemo } from '../componentes/AvisoDemo'
import { SelectorVista, type Vista } from '../componentes/SelectorVista'
import { useBusqueda } from '../estado/plan'

const MapaRuta = lazy(() => import('../componentes/Mapas').then((m) => ({ default: m.MapaRuta })))

export function Resultados() {
  const { busqueda } = useBusqueda()
  const [vista, setVista] = useState<Vista>('lista')

  if (!busqueda) {
    return (
      <>
        <h1 className="text-3xl font-bold text-marca-oscuro">Resultados</h1>
        <p className="mt-4">
          Aún no has buscado una ruta.{' '}
          <Link to="/" className="text-marca underline">
            Planear un viaje
          </Link>
        </p>
      </>
    )
  }

  const { origen, destino, respuesta: r } = busqueda
  const n = r.alternativas.length
  return (
    <>
      <h1 className="text-3xl font-bold text-marca-oscuro">
        Rutas de {origen.nombre} a {destino.nombre}
      </h1>
      <AvisoDemo visible={r.datos_demostracion} />
      <p aria-live="polite" className="mt-2">
        {n === 0
          ? 'No encontramos rutas para tu perfil.'
          : `Encontramos ${n} ${n === 1 ? 'alternativa' : 'alternativas'}.`}
      </p>

      {!r.hay_ruta_segura && (
        <section aria-labelledby="titulo-sin-ruta" className="mt-4 rounded border-2 border-[#b42318] bg-red-50 p-4">
          <h2 id="titulo-sin-ruta" className="text-xl font-bold text-[#b42318]">
            <span aria-hidden="true">✕ </span>
            {r.aviso ?? 'No hay ruta segura hasta tu destino.'}
          </h2>
          {r.obstaculos.length > 0 && (
            <>
              <h3 className="mt-3 font-semibold">Qué lo impide</h3>
              <ul className="mt-1 list-disc pl-6">
                {r.obstaculos.map((o) => (
                  <li key={o.descripcion}>{o.descripcion}</li>
                ))}
              </ul>
            </>
          )}
          {r.sugerencias.length > 0 && (
            <>
              <h3 className="mt-3 font-semibold">Qué puedes hacer</h3>
              <ul className="mt-1 list-disc pl-6">
                {r.sugerencias.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {n > 0 && (
        <div className="mt-6 flex items-center justify-between gap-3">
          <h2 className="text-xl font-bold">{r.hay_ruta_segura ? 'Alternativas' : 'Opciones con riesgo alto'}</h2>
          <SelectorVista vista={vista} alCambiar={setVista} />
        </div>
      )}

      {vista === 'mapa' && n > 0 ? (
        <div className="mt-4">
          <Suspense fallback={<p>Cargando mapa…</p>}>
            <MapaRuta alternativas={r.alternativas} origen={origen} destino={destino} />
          </Suspense>
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          {r.alternativas.map((a) => (
            <TarjetaAlternativa
              key={a.orden}
              alt={a}
              mapa={
                <Suspense fallback={<p>Cargando mapa…</p>}>
                  <MapaRuta
                    alternativas={[a]}
                    origen={origen}
                    destino={destino}
                    etiqueta={`Mapa de la opción ${a.orden} (la misma información está en sus pasos)`}
                  />
                </Suspense>
              }
            />
          ))}
        </div>
      )}

      {r.descartadas.length > 0 && (
        <section aria-labelledby="titulo-descartadas" className="mt-6">
          <h2 id="titulo-descartadas" className="text-xl font-bold">
            Rutas descartadas
          </h2>
          <ul className="mt-2 space-y-2">
            {r.descartadas.map((d) => (
              <li key={d.resumen} className="rounded border border-gray-300 p-3">
                <strong>{d.resumen}</strong>: {d.motivo}.
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="mt-6">
        <Link to="/" className="text-marca underline">
          Hacer otra búsqueda
        </Link>
      </p>
    </>
  )
}
