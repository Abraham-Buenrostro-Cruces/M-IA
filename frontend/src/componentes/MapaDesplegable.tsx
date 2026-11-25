// Botón "Ver mapa" / "Ocultar mapa" y el mapa que abre debajo, dentro de la misma tarjeta.
// Se comparte entre las alternativas y las otras opciones (D-26). El mapa llega ya
// construido (``children``) para que la tarjeta no dependa de Leaflet, que se carga sólo al
// abrirlo; la lista de pasos sigue siendo equivalente al mapa.
import { useId, useState, type ReactNode } from 'react'
import { Button } from 'react-aria-components'

export function MapaDesplegable({ nombre, children }: { nombre: string; children: ReactNode }) {
  const [abierto, setAbierto] = useState(false)
  const id = useId()
  return (
    <>
      <Button
        onPress={() => setAbierto((v) => !v)}
        aria-expanded={abierto}
        aria-controls={id}
        // Nombre completo para lectores de pantalla; contiene el texto visible (WCAG 2.5.3).
        aria-label={`${abierto ? 'Ocultar mapa' : 'Ver mapa'} de ${nombre}`}
        className="inline-flex min-h-11 items-center rounded border-2 border-marca px-4 font-semibold text-marca outline-none data-[focus-visible]:outline-3 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-[var(--color-foco)]"
      >
        {abierto ? 'Ocultar mapa' : 'Ver mapa'}
      </Button>
      {abierto && (
        <div id={id} className="mt-4 w-full">
          {children}
        </div>
      )}
    </>
  )
}
