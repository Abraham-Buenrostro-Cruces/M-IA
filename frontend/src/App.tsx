import { Route, Routes } from 'react-router'
import { Plantilla } from './componentes/Plantilla'
import { DetalleRuta } from './paginas/DetalleRuta'
import { Estaciones } from './paginas/Estaciones'
import { NoEncontrada } from './paginas/NoEncontrada'
import { Perfil } from './paginas/Perfil'
import { Planear } from './paginas/Planear'
import { Resultados } from './paginas/Resultados'
import { RutaActiva } from './paginas/RutaActiva'

export default function App() {
  return (
    <Routes>
      <Route element={<Plantilla />}>
        <Route index element={<Planear />} />
        <Route path="perfil" element={<Perfil />} />
        <Route path="resultados" element={<Resultados />} />
        <Route path="ruta/:orden" element={<DetalleRuta />} />
        <Route path="ruta-activa" element={<RutaActiva />} />
        <Route path="estaciones" element={<Estaciones />} />
        <Route path="*" element={<NoEncontrada />} />
      </Route>
    </Routes>
  )
}
