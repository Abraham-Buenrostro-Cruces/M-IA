import { QueryClient } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import App from '../App'
import { Proveedores } from '../Proveedores'

export function renderizarApp(ruta = '/') {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <Proveedores cliente={cliente}>
      <MemoryRouter initialEntries={[ruta]}>
        <App />
      </MemoryRouter>
    </Proveedores>,
  )
}
