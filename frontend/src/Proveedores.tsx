import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { ProveedorPlan } from './estado/ProveedorPlan'

function crearClienteConsultas() {
  return new QueryClient({
    defaultOptions: {
      // Un reintento basta: en el Metro la señal va y viene, pero reintentar mucho
      // sólo retrasa el mensaje de error.
      queries: { retry: 1, refetchOnWindowFocus: false },
      mutations: { retry: 0 },
    },
  })
}

export function Proveedores({ children, cliente }: { children: ReactNode; cliente?: QueryClient }) {
  const [qc] = useState(() => cliente ?? crearClienteConsultas())
  return (
    <QueryClientProvider client={qc}>
      <ProveedorPlan>{children}</ProveedorPlan>
    </QueryClientProvider>
  )
}
