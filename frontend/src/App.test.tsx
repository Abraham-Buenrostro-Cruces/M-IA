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
      'Planear', 'Estaciones', 'Reportar', 'Ruta activa', 'Mi perfil',
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
    expect(screen.getByText(/Encontramos 3 alternativas/)).toBeInTheDocument()
    const tarjetas = screen.getAllByRole('article')
    expect(tarjetas).toHaveLength(3)
    expect(within(tarjetas[0]).getByText('Recomendada')).toBeInTheDocument()
    expect(within(tarjetas[0]).getByText(/Pino Suárez, salida José María Izazaga/)).toBeInTheDocument()
    expect(within(tarjetas[0]).getByText('96')).toBeInTheDocument()
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
    expect(await screen.findByTestId('mapa-ruta')).toHaveTextContent('Mapa con 3 alternativas')
    await userEvent.click(screen.getByRole('radio', { name: 'Lista' }))
    expect(screen.getAllByRole('article')).toHaveLength(3)
  })

  it('cada opción abre y cierra su propio mapa con "Ver mapa"', async () => {
    buscarConFlujo1()
    renderizarApp('/resultados')
    const segunda = screen.getAllByRole('article')[1]
    const boton = within(segunda).getByRole('button', { name: 'Ver mapa de la opción 2' })
    expect(boton).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(boton)
    expect(boton).toHaveAttribute('aria-expanded', 'true')
    // Sólo esa opción, dentro de su tarjeta; la otra tarjeta no abre nada.
    expect(await within(segunda).findByTestId('mapa-ruta')).toHaveTextContent('Mapa con 1 alternativa')
    expect(screen.getAllByTestId('mapa-ruta')).toHaveLength(1)
    await userEvent.click(within(segunda).getByRole('button', { name: 'Ocultar mapa de la opción 2' }))
    expect(screen.queryByTestId('mapa-ruta')).not.toBeInTheDocument()
  })

  it('sin ruta segura lo dice primero y ofrece las otras opciones en orden (regla 5, D-26)', async () => {
    localStorage.setItem('ra.perfil', PERFIL_SILLA)
    sessionStorage.setItem(
      'ra.busqueda',
      JSON.stringify({
        origen: { nombre: 'Terminal Aérea', lat: 0, lon: 0 },
        destino: { nombre: 'Lechería', lat: 0, lon: 0 },
        respuesta: datos.planSinRuta,
      }),
    )
    renderizarApp('/resultados')
    const aviso = screen.getByRole('heading', { name: /No hay ruta segura hasta tu destino/ })
    expect(screen.getByRole('heading', { name: 'Qué puedes hacer' })).toBeInTheDocument()
    // Ninguna alternativa recomendada; las otras opciones van aparte, después del aviso.
    expect(screen.queryByRole('heading', { name: /^Opción 1/ })).not.toBeInTheDocument()
    const otras = screen.getByRole('region', { name: 'Otras opciones' })
    expect(aviso.compareDocumentPosition(otras) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    const tarjetas = within(otras).getAllByRole('article')
    expect(tarjetas.map((t) => within(t).getByRole('heading', { level: 3 }).textContent)).toEqual([
      expect.stringMatching(/^Llegar sin barreras hasta San Rafael.*Llega cerca de tu destino$/),
      expect.stringMatching(/^Ruta disponible cuando se repare.*No disponible hoy$/),
      expect.stringMatching(/^Ruta completa con asistencia del personal.*Requiere asistencia$/),
    ])
    // La ruta con asistencia (siempre la última) marca dónde pedir ayuda y por qué, con texto.
    const asistencia = tarjetas[2]
    expect(within(asistencia).getByRole('heading', { name: 'Dónde necesitas ayuda del personal' })).toBeInTheDocument()
    expect(within(asistencia).getAllByText(/Lechería: escalera con 20 escalones/).length).toBeGreaterThan(0)
    await userEvent.click(within(asistencia).getByText('Ver pasos de esta opción'))
    expect(within(asistencia).getByText(/Necesitas ayuda del personal: escalera con 20 escalones/)).toBeVisible()
    // Cada opción también tiene su mapa.
    await userEvent.click(within(asistencia).getByRole('button', { name: /^Ver mapa de Ruta completa con asistencia/ }))
    expect(await within(asistencia).findByTestId('mapa-ruta')).toHaveTextContent('Mapa con 1 alternativa')
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
    // Por omisión sólo el Metro; las demás se agregan por sistema (red completa, D-25).
    expect(screen.getByText('Acatitla')).toBeInTheDocument()
    expect(screen.queryByText('Lechería')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('checkbox', { name: 'Tren Suburbano' }))
    expect(screen.getByText('Lechería')).toBeInTheDocument()

    await userEvent.click(screen.getByText('Zócalo'))
    expect(await screen.findByText(/Falla confirmada/)).toBeInTheDocument()
  })

  it('el mapa dibuja la red por sistema, con accesibilidad y leyenda de líneas', async () => {
    renderizarApp('/estaciones')
    await screen.findByRole('heading', { name: /Con fallas hoy/ })
    await userEvent.click(screen.getByRole('radio', { name: 'Mapa' }))
    const metro = datos.red.estaciones.filter((e) => e.sistema === 'METRO').length
    // Por defecto: sólo Metro (12 líneas) con la capa de accesibilidad.
    expect(await screen.findByTestId('mapa-estaciones')).toHaveTextContent(
      `Mapa con 12 líneas y ${metro} estaciones con accesibilidad`,
    )
    const leyenda = screen.getByRole('list', { name: 'Líneas en el mapa' })
    expect(within(leyenda).getAllByRole('listitem')).toHaveLength(12)
    expect(leyenda).toHaveTextContent('Metro Línea 12')
    expect(leyenda).toHaveTextContent('Metro Línea 2 · Cuatro Caminos - Tasqueña')

    await userEvent.click(screen.getByRole('checkbox', { name: 'Metrobús' }))
    expect(screen.getByTestId('mapa-estaciones')).toHaveTextContent('Mapa con 20 líneas')
    await userEvent.click(screen.getByRole('checkbox', { name: /Mostrar accesibilidad/ }))
    expect(screen.getByTestId('mapa-estaciones')).not.toHaveTextContent('con accesibilidad')
  })
})

describe('Accesibilidad automática (F3-5, axe-core)', () => {
  it.each(['/', '/perfil', '/resultados', '/ruta/1', '/ruta-activa', '/estaciones', '/reportar', '/reportes', '/moderacion'])(
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
