import { Button } from 'react-aria-components'
import { Link, useNavigate, useParams } from 'react-router'
import { DetalleAlternativa } from '../componentes/Alternativa'
import { AvisoDemo } from '../componentes/AvisoDemo'
import { useRutaActiva } from '../estado/almacen'
import { useBusqueda } from '../estado/plan'

export function DetalleRuta() {
  const { orden } = useParams()
  const { busqueda } = useBusqueda()
  const [, guardarActiva] = useRutaActiva()
  const navegar = useNavigate()
  const alt = busqueda?.respuesta.alternativas.find((a) => String(a.orden) === orden)

  if (!busqueda || !alt) {
    return (
      <>
        <h1 className="text-3xl font-bold text-marca-oscuro">Ruta no disponible</h1>
        <p className="mt-4">
          <Link to="/" className="text-marca underline">
            Planear un viaje
          </Link>
        </p>
      </>
    )
  }

  return (
    <>
      <p>
        <Link to="/resultados" className="text-marca underline">
          ← Volver a las alternativas
        </Link>
      </p>
      <h1 className="mt-2 text-3xl font-bold text-marca-oscuro">
        Opción {alt.orden}: {busqueda.origen.nombre} → {busqueda.destino.nombre}
      </h1>
      <AvisoDemo visible={busqueda.respuesta.datos_demostracion} />
      <DetalleAlternativa alt={alt} />
      <Button
        onPress={() => {
          guardarActiva({
            alternativa: alt,
            origen: busqueda.origen.nombre,
            destino: busqueda.destino.nombre,
            guardada_en: new Date().toISOString(),
            datos_demostracion: busqueda.respuesta.datos_demostracion,
            calculado_en: busqueda.respuesta.calculado_en,
          })
          navegar('/ruta-activa')
        }}
        className="mt-6 inline-flex min-h-11 w-full items-center justify-center rounded bg-marca px-4 font-semibold text-white outline-none data-[focus-visible]:outline-3 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-[var(--color-foco)]"
      >
        Usar esta ruta (se guarda para consultarla sin señal)
      </Button>
    </>
  )
}
