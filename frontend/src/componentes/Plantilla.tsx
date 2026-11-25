import { useEffect, useRef } from 'react'
import { Link, Outlet, useLocation } from 'react-router'

/**
 * Estructura común: enlace para saltar al contenido, encabezado y <main>.
 *
 * En una SPA el navegador no anuncia los cambios de página. Por eso, al cambiar
 * de ruta se mueve el foco a <main>: así el lector de pantalla lee la nueva
 * página y quien navega con teclado o switch no tiene que recorrer el encabezado
 * otra vez.
 */
export function Plantilla() {
  const principal = useRef<HTMLElement>(null)
  const { pathname } = useLocation()
  const primeraCarga = useRef(true)

  useEffect(() => {
    if (primeraCarga.current) {
      primeraCarga.current = false // en la carga inicial el foco queda donde el navegador lo pone
      return
    }
    principal.current?.focus()
  }, [pathname])

  return (
    <>
      <a
        href="#contenido"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-4 focus:py-3 focus:text-marca"
      >
        Saltar al contenido
      </a>
      <header className="bg-marca text-white">
        <div className="mx-auto flex max-w-3xl items-center px-4 py-3">
          <Link to="/" className="text-xl font-bold no-underline">
            RutaAccesible
          </Link>
        </div>
      </header>
      <main
        id="contenido"
        ref={principal}
        tabIndex={-1}
        className="mx-auto max-w-3xl px-4 py-8 focus:outline-none"
      >
        <Outlet />
      </main>
    </>
  )
}
