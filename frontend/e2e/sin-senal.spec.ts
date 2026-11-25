// F3-6: la ruta activa se abre sin conexión gracias al service worker y a localStorage.
import { expect, test } from '@playwright/test'
import { prepararFlujo1 } from './utilidades'

test('la ruta activa abre sin red', async ({ page, context }) => {
  await prepararFlujo1(page)
  await page.goto('/ruta/1')
  await page.getByRole('button', { name: /Usar esta ruta/ }).click()
  await expect(page.getByRole('heading', { level: 1, name: /Ruta activa/ })).toBeVisible()
  // Esperar a que el service worker termine de instalarse y de precachear la app.
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready
  })

  await context.setOffline(true)
  await page.goto('/ruta-activa')
  await expect(page.getByRole('heading', { level: 1, name: /Ruta activa: Tasqueña/ })).toBeVisible()
  await expect(page.getByText(/Disponible sin conexión/)).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Plan B' })).toBeVisible()
  await context.setOffline(false)
})
