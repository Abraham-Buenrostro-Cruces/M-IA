import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import App from './App.tsx'
import { Proveedores } from './Proveedores.tsx'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Proveedores>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </Proveedores>
  </StrictMode>,
)
