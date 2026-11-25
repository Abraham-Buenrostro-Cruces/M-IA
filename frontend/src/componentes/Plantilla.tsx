import { useEffect, useRef } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'

const SECCIONES = [
  { a: '/', texto: 'Planear' },
  { a: '/estaciones', texto: 'Estaciones' },
  { a: '/reportar', texto: 'Reportar' },
  { a: '/ruta-activa', texto: 'Ruta activa' },
  { a: '/perfil', texto: 'Mi perfil' },
]

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
        <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-x-6 gap-y-1 px-4 py-2">
          <Link to="/" className="py-2 text-xl font-bold no-underline">
            M-IA
          </Link>
          <nav aria-label="Principal">
            <ul className="flex flex-wrap gap-x-1">
              {SECCIONES.map((s) => (
                <li key={s.a}>
                  <NavLink
                    to={s.a}
                    end={s.a === '/'}
                    className={({ isActive }) =>
                      `inline-flex min-h-11 items-center rounded px-2 no-underline ${isActive ? 'bg-white font-semibold text-marca' : 'text-white underline-offset-4 hover:underline'}`
                    }
                  >
                    {s.texto}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
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
      <footer className="mx-auto max-w-3xl border-t border-gray-300 px-4 py-4 text-sm">
        <nav aria-label="Secundaria">
          <ul className="flex flex-wrap gap-x-4">
            <li>
              <Link to="/reportes" className="inline-flex min-h-11 items-center text-marca underline">
                Mis reportes
              </Link>
            </li>
            <li>
              <Link to="/moderacion" className="inline-flex min-h-11 items-center text-marca underline">
                Moderación
              </Link>
            </li>
          </ul>
        </nav>
      </footer>
    </>
  )
}
