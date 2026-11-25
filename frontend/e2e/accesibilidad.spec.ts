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

test('sin ruta segura: el aviso aparece y no se muestran alternativas (regla 5)', async ({ page }) => {
  await page.addInitScript(() =>
    localStorage.setItem('ra.perfil', JSON.stringify({ tipo_movilidad: 'silla_manual' })),
  )
  await page.goto('/')
  await page.getByRole('combobox', { name: 'Origen' }).fill('tasqueña')
  await page.getByRole('option', { name: /^Tasqueña.*Metro/ }).click()
  await page.getByRole('combobox', { name: 'Destino' }).fill('copilco')
  await page.getByRole('option', { name: /^Copilco.*Metro/ }).click()
  await page.getByRole('button', { name: 'Buscar rutas accesibles' }).click()
  await expect(page.getByRole('heading', { name: /No encontramos una ruta segura/ })).toBeVisible()
  await expect(page.getByText(/Hidalgo: escalera/)).toBeVisible()
  await expect(page.getByRole('article')).toHaveCount(0)
})
