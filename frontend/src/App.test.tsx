import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { datos, peticiones, servidor } from './pruebas/api-simulada'
import { violacionesGraves } from './pruebas/accesibilidad'
import { renderizarApp } from './pruebas/renderizar'

const PERFIL_SILLA = JSON.stringify({ tipo_movilidad: 'silla_manual' })

async function elegirLugar(etiqueta: string, texto: string, opcion: RegExp) {
  const campo = screen.getByRole('combobox', { name: etiqueta })
  await userEvent.clear(campo)
  await userEvent.type(campo, texto)
  await userEvent.click(await screen.findByRole('option', { name: opcion }))
}

function buscarConFlujo1() {
  localStorage.setItem('ra.perfil', PERFIL_SILLA)
  sessionStorage.setItem(
    'ra.busqueda',
    JSON.stringify({
      origen: { nombre: 'Tasqueña', lat: 19.34, lon: -99.14, clave_estacion: 'METRO-TASQUENA' },
      destino: { nombre: 'Museo de la Ciudad de México', lat: 19.42965, lon: -99.1323 },
      respuesta: datos.planFlujo1,
    }),
  )
}

describe('Plantilla', () => {
  it('un único h1 dentro de main y navegación principal', async () => {
    renderizarApp()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    const nav = screen.getByRole('navigation', { name: 'Principal' })
    expect(within(nav).getAllByRole('link').map((a) => a.textContent)).toEqual([
      'Planear', 'Estaciones', 'Ruta activa', 'Mi perfil',
    ])
  })

  it('el primer Tab llega a "Saltar al contenido"', async () => {
    renderizarApp()
    await userEvent.tab()
    expect(screen.getByRole('link', { name: 'Saltar al contenido' })).toHaveFocus()
  })

  it('al navegar, el foco pasa a main', async () => {
    renderizarApp('/no-existe')
    await userEvent.click(screen.getByRole('link', { name: 'Volver al inicio' }))
    expect(screen.getByRole('main')).toHaveFocus()
  })
})

describe('Perfil (F3-2)', () => {
  it('sin perfil, la búsqueda pide elegir uno y el botón está deshabilitado', () => {
    renderizarApp()
    expect(screen.getByRole('link', { name: 'Elegir perfil' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Buscar rutas accesibles' })).toBeDisabled()
  })

  it('elegir y ajustar el perfil lo guarda sólo en este dispositivo', async () => {
    renderizarApp('/perfil')
    await userEvent.click(await screen.findByRole('radio', { name: /Silla de ruedas manual/ }))
    await userEvent.click(screen.getByRole('checkbox', { name: /escaleras eléctricas/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Guardar perfil' }))
    expect(await screen.findByText('Perfil guardado en este dispositivo.')).toBeInTheDocument()
    // Sólo se guardan las diferencias con el predefinido.
    expect(JSON.parse(localStorage.getItem('ra.perfil')!)).toEqual({
      tipo_movilidad: 'silla_manual',
      puede_escalera_electrica: true,
    })
    // Ninguna petición envió el perfil (sólo se consultaron las plantillas).
    expect(peticiones.every((p) => !p.cuerpo.includes('silla_manual'))).toBe(true)
  })

  it('borrar el perfil lo elimina del dispositivo', async () => {
    localStorage.setItem('ra.perfil', PERFIL_SILLA)
    renderizarApp('/perfil')
    await userEvent.click(await screen.findByRole('button', { name: 'Borrar mi perfil' }))
    expect(localStorage.getItem('ra.perfil')).toBeNull()
  })
})

describe('Búsqueda y resultados (F3-1, F3-4)', () => {
  it('flujo 1 completo: buscar, ver alternativas, descartada y detalle', async () => {
    localStorage.setItem('ra.perfil', PERFIL_SILLA)
    renderizarApp()
    await elegirLugar('Origen', 'tasque', /^Tasqueña.*Metro/)
    await elegirLugar('Destino', 'museo', /Museo de la Ciudad de México/)
    await userEvent.click(screen.getByRole('button', { name: 'Buscar rutas accesibles' }))

    expect(await screen.findByRole('heading', { level: 1, name: /Rutas de Tasqueña a Museo/ })).toBeInTheDocument()
    expect(screen.getByText(/Datos de demostración/)).toBeInTheDocument()
    expect(screen.getByText(/Encontramos 2 alternativas/)).toBeInTheDocument()
    const tarjetas = screen.getAllByRole('article')
    expect(tarjetas).toHaveLength(2)
    expect(within(tarjetas[0]).getByText('Recomendada')).toBeInTheDocument()
    expect(within(tarjetas[0]).getByText(/Pino Suárez, salida José María Izazaga/)).toBeInTheDocument()
    expect(within(tarjetas[0]).getByText('92')).toBeInTheDocument()
    expect(within(tarjetas[1]).getByText(/no se verifica desde hace 30 h/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Rutas descartadas' })).toBeInTheDocument()
    expect(screen.getByText(/falla confirmada/)).toBeInTheDocument()

    // El perfil viajó sólo dentro de POST /rutas/plan (regla 6).
    const conPerfil = peticiones.filter((p) => p.cuerpo.includes('silla_manual'))
    expect(conPerfil.map((p) => `${p.metodo} ${new URL(p.url).pathname}`)).toEqual(['POST /api/rutas/plan'])

    await userEvent.click(within(tarjetas[0]).getByRole('link', { name: /Ver pasos y plan B/ }))
    expect(await screen.findByRole('heading', { name: 'Pasos' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Plan B' })).toBeInTheDocument()
    expect(screen.getAllByRole('listitem').some((li) => /Aborda la Línea 2/.test(li.textContent ?? ''))).toBe(true)
  })

  it('la vista de mapa muestra las mismas alternativas que la lista', async () => {
    buscarConFlujo1()
    renderizarApp('/resultados')
    await userEvent.click(screen.getByRole('radio', { name: 'Mapa' }))
    expect(await screen.findByTestId('mapa-ruta')).toHaveTextContent('Mapa con 2 alternativas')
    await userEvent.click(screen.getByRole('radio', { name: 'Lista' }))
    expect(screen.getAllByRole('article')).toHaveLength(2)
  })

  it('sin ruta segura lo dice explícitamente con obstáculos y sugerencias (regla 5)', async () => {
    localStorage.setItem('ra.perfil', PERFIL_SILLA)
    sessionStorage.setItem(
      'ra.busqueda',
      JSON.stringify({
        origen: { nombre: 'Tasqueña', lat: 0, lon: 0 },
        destino: { nombre: 'Copilco', lat: 0, lon: 0 },
        respuesta: datos.planSinRuta,
      }),
    )
    renderizarApp('/resultados')
    expect(screen.getByRole('heading', { name: /No encontramos una ruta segura/ })).toBeInTheDocument()
    expect(screen.getByText(/Hidalgo: escalera/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Qué puedes hacer' })).toBeInTheDocument()
    expect(screen.queryAllByRole('article')).toHaveLength(0)
  })

  it('un error del servidor se anuncia', async () => {
    servidor.use(http.post('*/api/rutas/plan', () => HttpResponse.json({ detail: 'Falla de prueba' }, { status: 500 })))
    localStorage.setItem('ra.perfil', PERFIL_SILLA)
    renderizarApp()
    await elegirLugar('Origen', 'tasque', /^Tasqueña.*Metro/)
    await elegirLugar('Destino', 'museo', /Museo de la Ciudad de México/)
    await userEvent.click(screen.getByRole('button', { name: 'Buscar rutas accesibles' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Falla de prueba')
  })
})

describe('Ruta activa sin señal (F3-6)', () => {
  it('"Usar esta ruta" la guarda y se puede consultar sin conexión', async () => {
    buscarConFlujo1()
    renderizarApp('/ruta/1')
    await userEvent.click(screen.getByRole('button', { name: /Usar esta ruta/ }))
    expect(await screen.findByRole('heading', { level: 1, name: /Ruta activa: Tasqueña/ })).toBeInTheDocument()
    expect(JSON.parse(localStorage.getItem('ra.ruta-activa')!).alternativa.orden).toBe(1)
  })

  it('la ruta activa se muestra aunque la red falle', async () => {
    servidor.use(http.all('*', () => HttpResponse.error()))
    buscarConFlujo1()
    localStorage.setItem(
      'ra.ruta-activa',
      JSON.stringify({
        alternativa: datos.planFlujo1.alternativas[0],
        origen: 'Tasqueña',
        destino: 'Museo de la Ciudad de México',
        guardada_en: new Date().toISOString(),
        datos_demostracion: true,
        calculado_en: datos.planFlujo1.calculado_en,
      }),
    )
    renderizarApp('/ruta-activa')
    expect(screen.getByText(/Disponible sin conexión/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Plan B' })).toBeInTheDocument()
  })
})

describe('Estaciones (F3-3)', () => {
  it('agrupa por estado con texto, y el detalle carga los equipos', async () => {
    renderizarApp('/estaciones')
    expect(await screen.findByRole('heading', { name: /Con fallas hoy/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /^Accesible/ })).toBeInTheDocument()
    expect(screen.queryByText('Acatitla')).not.toBeInTheDocument() // fuera del piloto por defecto
    await userEvent.click(screen.getByRole('checkbox', { name: /Sólo el corredor piloto/ }))
    expect(screen.getByText('Acatitla')).toBeInTheDocument()

    await userEvent.click(screen.getByText('Zócalo'))
    expect(await screen.findByText(/Falla confirmada/)).toBeInTheDocument()
  })

  it('el mapa recibe las mismas estaciones que la lista', async () => {
    renderizarApp('/estaciones')
    await screen.findByRole('heading', { name: /Con fallas hoy/ })
    await userEvent.click(screen.getByRole('radio', { name: 'Mapa' }))
    const visibles = datos.estaciones.estaciones.filter((e) => e.accesibilidad !== 'SIN_DATOS').length
    expect(await screen.findByTestId('mapa-estaciones')).toHaveTextContent(`Mapa con ${visibles} estaciones`)
  })
})

describe('Accesibilidad automática (F3-5, axe-core)', () => {
  it.each(['/', '/perfil', '/resultados', '/ruta/1', '/ruta-activa', '/estaciones'])(
    'sin violaciones graves en %s',
    async (ruta) => {
      buscarConFlujo1()
      const { container } = renderizarApp(ruta)
      await waitFor(() => expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1))
      if (ruta === '/estaciones') await screen.findByRole('heading', { name: /Con fallas hoy/ })
      if (ruta === '/perfil') await screen.findByRole('radiogroup')
      expect(await violacionesGraves(container)).toEqual([])
    },
  )
})
