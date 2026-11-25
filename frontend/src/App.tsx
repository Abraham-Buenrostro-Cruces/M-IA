import { Route, Routes } from 'react-router'
import { Plantilla } from './componentes/Plantilla'
import { DetalleRuta } from './paginas/DetalleRuta'
import { Estaciones } from './paginas/Estaciones'
import { MisReportes, SeguimientoReporte } from './paginas/MisReportes'
import { Moderacion } from './paginas/Moderacion'
import { NoEncontrada } from './paginas/NoEncontrada'
import { Perfil } from './paginas/Perfil'
import { Planear } from './paginas/Planear'
import { Reportar } from './paginas/Reportar'
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
        <Route path="reportar" element={<Reportar />} />
        <Route path="reportes" element={<MisReportes />} />
        <Route path="reportes/:id" element={<SeguimientoReporte />} />
        <Route path="moderacion" element={<Moderacion />} />
        <Route path="*" element={<NoEncontrada />} />
      </Route>
    </Routes>
  )
}
