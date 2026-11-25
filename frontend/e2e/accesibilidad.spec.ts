// axe-core en un navegador real: incluye el contraste de color (F3-5).
import { expect, test } from '@playwright/test'
import { prepararFlujo1, sinViolacionesGraves } from './utilidades'

const PAGINAS: [string, string | RegExp][] = [
  ['/', 'Planea un viaje accesible'],
  ['/perfil', 'Mi perfil de movilidad'],
  ['/resultados', /Rutas de Tasqueña/],
  ['/ruta/1', /Opción 1/],
  ['/ruta-activa', 'Ruta activa'],
  ['/estaciones', 'Estaciones'],
  ['/reportar', 'Reportar un problema'],
  ['/moderacion', 'Moderación'],
]

for (const [ruta, titulo] of PAGINAS) {
  test(`sin violaciones graves en ${ruta}`, async ({ page }) => {
    await prepararFlujo1(page)
    await page.goto(ruta)
    await expect(page.getByRole('heading', { level: 1, name: titulo })).toBeVisible()
    if (ruta === '/estaciones') await expect(page.getByRole('heading', { name: /Con fallas hoy/ })).toBeVisible()
    if (ruta === '/perfil') await expect(page.getByRole('radiogroup')).toBeVisible()
    await sinViolacionesGraves(page)
  })
}

test('sin violaciones graves en las vistas de mapa', async ({ page }) => {
  await prepararFlujo1(page)
  await page.goto('/resultados')
  await page.getByRole('radio', { name: 'Mapa' }).click()
  await expect(page.getByRole('region', { name: /Mapa de las alternativas/ })).toBeVisible()
  await expect(page.locator('.leaflet-marker-icon').first()).toBeVisible()
  await sinViolacionesGraves(page)

  await page.goto('/estaciones')
  await page.getByRole('radio', { name: 'Mapa' }).click()
  await expect(page.locator('.leaflet-marker-icon').first()).toBeVisible()
  await sinViolacionesGraves(page)
})

test('los marcadores del mapa de estaciones tienen nombre y estado en texto', async ({ page }) => {
  await page.goto('/estaciones')
  await page.getByRole('radio', { name: 'Mapa' }).click()
  const zocalo = page.locator('.leaflet-marker-icon', { hasText: 'Zócalo, Metro: Con fallas hoy' })
  await expect(zocalo).toHaveCount(1)
  await expect(zocalo).toHaveAttribute('tabindex', '0') // enfocable con teclado
})

test('sin ruta segura: lo dice primero y ofrece la ruta con asistencia al final (regla 5, D-26)', async ({ page }) => {
  await page.addInitScript(() =>
    localStorage.setItem('ra.perfil', JSON.stringify({ tipo_movilidad: 'silla_manual' })),
  )
  await page.goto('/')
  // Con la red completa (D-25), Tasqueña → Copilco ya tiene ruta por la Línea 12. Popotla
  // sigue sin elevador según el GTFS (D-19) y no hay otra estación accesible a 800 m.
  await page.getByRole('combobox', { name: 'Origen' }).fill('popotla')
  await page.getByRole('option', { name: /^Popotla.*Metro/ }).click()
  await page.getByRole('combobox', { name: 'Destino' }).fill('zapata')
  await page.getByRole('option', { name: /^Zapata.*Metro/ }).click()
  await page.getByRole('button', { name: 'Buscar rutas accesibles' }).click()
  await expect(page.getByRole('heading', { name: /No hay ruta segura hasta tu destino/ })).toBeVisible()
  await expect(page.getByText(/Popotla: escalera/).first()).toBeVisible()
  // Ninguna alternativa: sólo "Otras opciones", y la ruta con asistencia es la última.
  await expect(page.getByRole('heading', { name: /^Opción 1/ })).toHaveCount(0)
  const otras = page.getByRole('region', { name: 'Otras opciones' })
  const tarjetas = otras.getByRole('article')
  const asistencia = tarjetas.last()
  await expect(asistencia.getByRole('heading', { level: 3 })).toContainText('Ruta completa con asistencia del personal')
  await expect(asistencia.getByText('Popotla: escalera con 20 escalones', { exact: true })).toBeVisible()
  await asistencia.getByText('Ver pasos de esta opción').click()
  await expect(asistencia.getByText(/Necesitas ayuda del personal: escalera con 20 escalones/)).toBeVisible()
  await sinViolacionesGraves(page)
  // En su mapa, la estación donde se necesita ayuda lleva un marcador rojo con texto.
  await asistencia.getByRole('button', { name: /^Ver mapa de Ruta completa con asistencia/ }).click()
  await expect(asistencia.locator('.marcador-ra', { hasText: /Necesitas ayuda: Popotla: escalera/ }).first()).toBeAttached()
  await sinViolacionesGraves(page)
})

test('el mapa dibuja las 12 líneas del Metro con su color oficial y suma Metrobús', async ({ page }) => {
  await page.goto('/estaciones')
  await page.getByRole('radio', { name: 'Mapa' }).click()
  const metro = page.locator('path.linea-metro')
  await expect(metro).toHaveCount(12)
  // Color oficial de la Línea 2 en el GTFS (#0071C1).
  await expect(page.locator('path.linea-metro[stroke="#0071C1"]')).toHaveCount(1)
  await expect(page.locator('path.linea-metrobus')).toHaveCount(0)
  await page.locator('label').filter({ has: page.getByRole('checkbox', { name: 'Metrobús' }) }).click()
  await expect(page.locator('path.linea-metrobus').first()).toBeVisible()
  expect(await page.locator('path.linea-metrobus').count()).toBeGreaterThanOrEqual(8)
  await sinViolacionesGraves(page)
})
