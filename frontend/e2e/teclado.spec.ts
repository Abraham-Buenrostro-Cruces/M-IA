// Flujo 1 completo usando SÓLO el teclado (F3-5): elegir perfil, buscar, ver el detalle y
// guardar la ruta activa.
import { expect, test } from '@playwright/test'
import { tabularHasta } from './utilidades'

test('flujo 1 sólo con teclado', async ({ page }) => {
  await page.goto('/perfil')

  // Perfil: Tab al grupo de opciones y Espacio para elegir la primera (silla manual).
  const silla = page.getByRole('radio', { name: /Silla de ruedas manual/ })
  await tabularHasta(page, silla)
  await page.keyboard.press('Space')
  await expect(silla).toBeChecked()
  await tabularHasta(page, page.getByRole('button', { name: 'Guardar perfil' }))
  await page.keyboard.press('Enter')
  await expect(page.getByText('Perfil guardado en este dispositivo.')).toBeVisible()

  // Navegación principal -> Planear.
  await tabularHasta(page, page.getByRole('navigation', { name: 'Principal' }).getByRole('link', { name: 'Planear' }))
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { level: 1, name: 'Planea un viaje accesible' })).toBeVisible()

  // Origen: escribir, flecha abajo y Enter.
  const origen = page.getByRole('combobox', { name: 'Origen' })
  await tabularHasta(page, origen)
  await page.keyboard.type('tasqueña')
  await expect(page.getByRole('option', { name: /^Tasqueña.*Metro/ })).toBeVisible()
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await expect(origen).toHaveValue('Tasqueña')

  const destino = page.getByRole('combobox', { name: 'Destino' })
  await tabularHasta(page, destino)
  await page.keyboard.type('museo de la ciudad de')
  await expect(page.getByRole('option', { name: /Museo de la Ciudad de México/ })).toBeVisible()
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await expect(destino).toHaveValue('Museo de la Ciudad de México')

  await tabularHasta(page, page.getByRole('button', { name: 'Buscar rutas accesibles' }))
  await page.keyboard.press('Enter')

  // Resultados: la recomendada es la del flujo 1 (Pino Suárez) y Zócalo queda descartada.
  await expect(page.getByRole('heading', { level: 1, name: /Rutas de Tasqueña a Museo/ })).toBeVisible()
  const primera = page.getByRole('article').first()
  await expect(primera).toContainText('Recomendada')
  await expect(primera).toContainText('Pino Suárez, salida José María Izazaga')
  await expect(page.getByText(/Zócalo, salida Plaza de la Constitución/)).toBeVisible()

  await tabularHasta(page, primera.getByRole('link', { name: /Ver pasos y plan B/ }))
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { name: 'Plan B' })).toBeVisible()

  await tabularHasta(page, page.getByRole('button', { name: /Usar esta ruta/ }), 80)
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { level: 1, name: /Ruta activa: Tasqueña/ })).toBeVisible()
})
