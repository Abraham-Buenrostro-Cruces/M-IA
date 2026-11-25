// Fase 4 en navegador real contra el backend real: flujo 2 (reporte con foto),
// corroboración de otra persona (F4-7) y moderación (F4-6).
import { expect, test, type Browser, type Page } from '@playwright/test'
import { join } from 'node:path'
import { reiniciarDemo } from './preparacion'
import { PETICION_FLUJO1, sinViolacionesGraves } from './utilidades'

const FOTOS = join(import.meta.dirname, '..', '..', 'data', 'demo', 'fotos')
const EN_PINO_SUAREZ = { latitude: 19.4244, longitude: -99.1329, accuracy: 10 }

// Los reportes cambian estados de equipos: se reinicia la demo antes y después de cada
// prueba para no afectar a las demás. Corre sólo en el proyecto "escritorio" (ver
// playwright.config.ts): el flujo no depende del tamaño de pantalla.
test.beforeEach(async () => reiniciarDemo())
test.afterEach(async () => reiniciarDemo())

async function personaEnPinoSuarez(browser: Browser) {
  const contexto = await browser.newContext({
    baseURL: 'http://127.0.0.1:4173',
    geolocation: EN_PINO_SUAREZ,
    permissions: ['geolocation'],
    locale: 'es-MX',
  })
  return contexto.newPage()
}

/** Clic en la etiqueta de una opción de React Aria (el input está oculto visualmente). */
async function elegir(page: Page, nombre: RegExp | string) {
  await page.locator('label').filter({ has: page.getByRole('radio', { name: nombre }) }).click()
}

async function reportar(page: Page, equipo: RegExp, foto: string) {
  await page.goto('/reportar')
  await page.getByRole('button', { name: /estación más cercana/ }).click()
  await expect(page.getByRole('combobox', { name: 'Estación' })).toHaveValue('Pino Suárez')
  await elegir(page, equipo)
  await elegir(page, 'Fuera de servicio')
  await page.getByLabel(/Una foto permite verificar/).setInputFiles(join(FOTOS, foto))
  await page.getByRole('button', { name: 'Enviar reporte' }).click()
  await expect(page.getByRole('heading', { name: 'Tu reporte' })).toBeVisible()
}

test('flujo 2: Luis reporta con foto y otra persona lo corrobora', async ({ browser }) => {
  // Luis es una persona nueva (reputación 0.5): su reporte queda en zona gris, pero el
  // equipo ya pasa a "posible falla" (basta s >= 0.40).
  const luis = await personaEnPinoSuarez(browser)
  await reportar(luis, /elevador salida José María Izazaga/i, 'elevador-fuera-de-servicio.jpg')
  await expect(luis.getByText('Esperando confirmación')).toBeVisible({ timeout: 10_000 })
  await expect(luis.getByText('Posible falla', { exact: true })).toBeVisible()
  await expect(luis.getByRole('img', { name: /rostros difuminados/ })).toBeVisible()
  await sinViolacionesGraves(luis)

  // Ana busca la ruta del flujo 1: la salida José María Izazaga ya no es la recomendada
  // y, en su detalle, la app le pregunta si sigue fuera de servicio.
  const ana = await personaEnPinoSuarez(browser)
  await ana.addInitScript(() =>
    localStorage.setItem('ra.perfil', JSON.stringify({ tipo_movilidad: 'silla_manual' })),
  )
  const plan = await (await ana.request.post('/api/rutas/plan', { data: PETICION_FLUJO1 })).json()
  const conFalla = plan.alternativas.find((a: { resumen: string }) => a.resumen.includes('José María Izazaga'))
  expect(conFalla.orden).toBeGreaterThan(1)
  await ana.addInitScript((b) => sessionStorage.setItem('ra.busqueda', b), JSON.stringify({
    origen: { nombre: 'Tasqueña', lat: 19.3438, lon: -99.1395, clave_estacion: 'METRO-TASQUENA' },
    destino: { nombre: 'Museo de la Ciudad de México', lat: 19.42965, lon: -99.1323 },
    respuesta: plan,
  }))
  await ana.goto(`/ruta/${conFalla.orden}`)
  const pregunta = ana.getByRole('region', { name: /Sigue fuera de servicio el elevador salida José María Izazaga/ })
  await pregunta.getByRole('button', { name: 'Sí, sigue fuera de servicio' }).click()
  await expect(pregunta.getByRole('status')).toContainText('¡Gracias!')
  await sinViolacionesGraves(ana)

  // Con la corroboración, el reporte de Luis se verifica y la falla queda confirmada
  // (dos personas distintas, una con foto verificada).
  await expect(luis.getByText('Falla confirmada', { exact: true })).toBeVisible({ timeout: 20_000 })
  await expect(luis.getByText('Verificado', { exact: true })).toBeVisible()
})

test('moderación: confirma un reporte en zona gris', async ({ browser, page }) => {
  const persona = await personaEnPinoSuarez(browser)
  await reportar(persona, /elevador salida Pino Suárez/i, 'rampa-bloqueada.jpg')
  await expect(persona.getByText('Esperando confirmación')).toBeVisible({ timeout: 10_000 })

  await page.goto('/moderacion')
  await page.getByLabel('Token de moderación').fill(process.env.RA_TOKEN_MODERADOR!)
  await page.getByRole('button', { name: 'Entrar' }).click()
  const tarjeta = page.getByRole('article', { name: /Fuera de servicio · Pino Suárez/ })
  await expect(tarjeta).toBeVisible()
  await expect(tarjeta.getByRole('img', { name: /ya saneada/ })).toBeVisible()
  await sinViolacionesGraves(page)
  await tarjeta.getByRole('button', { name: /Confirmar/ }).click()
  await expect(page.getByText('No hay reportes por revisar.')).toBeVisible()

  await persona.reload()
  await expect(persona.getByText('Confirmado por moderación')).toBeVisible()
})
