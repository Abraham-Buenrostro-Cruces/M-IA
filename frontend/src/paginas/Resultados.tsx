// Resultados (F3-4). Regla 5: si no hay ruta segura se dice explícitamente, antes que nada.
import { lazy, Suspense, useEffect, useState } from 'react'
import { Button } from 'react-aria-components'
import { Link } from 'react-router'
import { TarjetaAlternativa } from '../componentes/Alternativa'
import { AvisoDemo } from '../componentes/AvisoDemo'
import { TarjetaOtraOpcion } from '../componentes/OtraOpcion'
import { SelectorVista, type Vista } from '../componentes/SelectorVista'
import { useBusqueda } from '../estado/plan'
import { hablar, puedeHablar, textoDeResultado } from '../util/voz'

const MapaRuta = lazy(() => import('../componentes/Mapas').then((m) => ({ default: m.MapaRuta })))

export function Resultados() {
  const { busqueda, guardar } = useBusqueda()
  const [vista, setVista] = useState<Vista>('lista')

  // Si la búsqueda se pidió por voz, la recomendación se lee sola una vez (F5-4).
  useEffect(() => {
    if (busqueda?.porVoz) {
      hablar(textoDeResultado(busqueda.respuesta))
      guardar({ ...busqueda, porVoz: false })
    }
  }, [busqueda, guardar])

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
      {puedeHablar() && (
        <Button
          onPress={() => hablar(textoDeResultado(r))}
          className="inline-flex min-h-11 items-center rounded border border-marca px-4 font-semibold text-marca outline-none data-[focus-visible]:outline-3 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-[var(--color-foco)]"
        >
          <span aria-hidden="true">🔊 </span>Escuchar el resultado
        </Button>
      )}
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

      {r.otras_opciones.length > 0 && (
        <section aria-labelledby="titulo-otras" className="mt-8">
          <h2 id="titulo-otras" className="text-xl font-bold">
            Otras opciones
          </h2>
          <p className="mt-1">
            Ninguna es una ruta segura hasta tu destino. Van de la más a la menos conveniente; la ruta con
            asistencia, si la hay, siempre al final.
          </p>
          <div className="mt-4 space-y-4">
            {r.otras_opciones.map((o) => (
              <TarjetaOtraOpcion
                key={o.tipo}
                opcion={o}
                mapa={
                  <Suspense fallback={<p>Cargando mapa…</p>}>
                    <MapaRuta
                      alternativas={[o.ruta]}
                      origen={origen}
                      destino={destino}
                      asistencia={o.puntos_asistencia}
                      etiqueta={`Mapa de: ${o.titulo} (la misma información está en sus pasos)`}
                    />
                  </Suspense>
                }
              />
            ))}
          </div>
        </section>
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
