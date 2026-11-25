// Ruta activa (F3-6): se lee sólo de este dispositivo, así funciona sin señal dentro de
// las estaciones. Se advierte que los estados pueden haber cambiado desde que se calculó.
import { Button } from 'react-aria-components'
import { Link } from 'react-router'
import { DetalleAlternativa } from '../componentes/Alternativa'
import { AvisoDemo } from '../componentes/AvisoDemo'
import { useRutaActiva } from '../estado/almacen'
import { fechaHora, haceCuanto } from '../util/formato'

export function RutaActiva() {
  const [ruta, guardar] = useRutaActiva()

  if (!ruta) {
    return (
      <>
        <h1 className="text-3xl font-bold text-marca-oscuro">Ruta activa</h1>
        <p className="mt-4">
          No tienes una ruta activa. Elige una alternativa y pulsa "Usar esta ruta" para
          tenerla disponible sin señal.
        </p>
        <p className="mt-2">
          <Link to="/" className="text-marca underline">
            Planear un viaje
          </Link>
        </p>
      </>
    )
  }

  return (
    <>
      <h1 className="text-3xl font-bold text-marca-oscuro">
        Ruta activa: {ruta.origen} → {ruta.destino}
      </h1>
      <AvisoDemo visible={ruta.datos_demostracion} />
      <p className="mt-2 rounded bg-blue-50 p-3">
        Calculada <span title={fechaHora(ruta.calculado_en)}>{haceCuanto(ruta.calculado_en)}</span>.
        Disponible sin conexión. Los estados de los equipos pueden haber cambiado: cuando
        tengas señal, vuelve a buscar la ruta para confirmarla.
      </p>
      <DetalleAlternativa alt={ruta.alternativa} />
      <Button
        onPress={() => guardar(null)}
        className="mt-6 inline-flex min-h-11 items-center rounded border border-gray-500 px-4 font-semibold outline-none data-[focus-visible]:outline-3 data-[focus-visible]:outline-[var(--color-foco)]"
      >
        Terminar y quitar la ruta activa
      </Button>
    </>
  )
}
