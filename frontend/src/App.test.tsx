import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import App from './App'
import { violacionesGraves } from './pruebas/accesibilidad'

function renderizar(ruta = '/') {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <App />
    </MemoryRouter>,
  )
}

describe('Pantalla de inicio', () => {
  it('muestra un único encabezado h1 dentro de main', () => {
    renderizar()
    const principal = screen.getByRole('main')
    expect(principal).toContainElement(screen.getByRole('heading', { level: 1 }))
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })

  it('no tiene violaciones de accesibilidad graves (axe-core)', async () => {
    const { container } = renderizar()
    expect(await violacionesGraves(container)).toEqual([])
  })

  it('el primer Tab llega al enlace "Saltar al contenido"', async () => {
    renderizar()
    await userEvent.tab()
    expect(screen.getByRole('link', { name: 'Saltar al contenido' })).toHaveFocus()
  })
})

describe('Ruta inexistente', () => {
  it('muestra "Página no encontrada" con enlace al inicio', async () => {
    renderizar('/no-existe')
    expect(screen.getByRole('heading', { name: 'Página no encontrada' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: 'Volver al inicio' }))
    expect(screen.getByRole('main')).toHaveFocus() // el foco se mueve al cambiar de página
  })
})
