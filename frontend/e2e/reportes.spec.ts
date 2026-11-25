// Fase 4 en navegador real contra el backend real: flujo 2 (reporte con foto),
// corroboración de otra persona (F4-7) y moderación (F4-6).
import { expect, test, type Browser, type Page } from '@playwright/test'
import { join } from 'node:path'
import { reiniciarDemo } from './preparacion'
import { PERFIL_SILLA, sinViolacionesGraves } from './utilidades'

const FOTOS = join(import.meta.dirname, '..', '..', 'data', 'demo', 'fotos')
const EN_PINO_SUAREZ = { latitude: 19.4244, longitude: -99.1329, accuracy: 10 }
const EN_COPILCO = { latitude: 19.3361, longitude: -99.1764, accuracy: 10 }

// Los reportes cambian estados de equipos: se reinicia la demo antes y después de cada
// prueba para no afectar a las demás. Corre sólo en el proyecto "escritorio" (ver
// playwright.config.ts): el flujo no depende del tamaño de pantalla.
// Los 30 s por omisión no alcanzan: el reinicio de la demo (antes y después) cuenta dentro
// del tiempo de la prueba, y el flujo 2 abre dos contextos y espera al trabajador de estado.
test.setTimeout(90_000)
test.beforeEach(async () => reiniciarDemo())
test.afterEach(async () => reiniciarDemo())

async function personaEn(browser: Browser, geolocation = EN_PINO_SUAREZ) {
  const contexto = await browser.newContext({
    baseURL: 'http://127.0.0.1:4173',
    geolocation,
    permissions: ['geolocation'],
    locale: 'es-MX',
  })
  return contexto.newPage()
}

/** Clic en la etiqueta de una opción de React Aria (el input está oculto visualmente). */
async function elegir(page: Page, nombre: RegExp | string) {
  await page.locator('label').filter({ has: page.getByRole('radio', { name: nombre }) }).click()
}

async function reportar(page: Page, estacion: string, equipo: RegExp, foto: string) {
  await page.goto('/reportar')
  await page.getByRole('button', { name: /estación más cercana/ }).click()
  await expect(page.getByRole('combobox', { name: 'Estación' })).toHaveValue(estacion)
  await elegir(page, equipo)
  await elegir(page, 'Fuera de servicio')
  await page.getByLabel(/Una foto permite verificar/).setInputFiles(join(FOTOS, foto))
  await page.getByRole('button', { name: 'Enviar reporte' }).click()
  await expect(page.getByRole('heading', { name: 'Tu reporte' })).toBeVisible()
}

test('flujo 2: Luis reporta con foto y otra persona lo corrobora', async ({ browser }) => {
  // Luis es una persona nueva (reputación 0.5): su reporte queda en zona gris, pero el
  // equipo ya pasa a "posible falla" (basta s >= 0.40).
  //
  // Con la red completa (D-25), una ruta que depende de un equipo en posible falla queda
  // detrás de otras que lo evitan, y quien consulta ya no la ve. Por eso Luis reporta el
  // único elevador de salida de Copilco: toda ruta en silla de ruedas a Copilco lo usa.
  const luis = await personaEn(browser, EN_COPILCO)
  await reportar(luis, 'Copilco', /^elevador salida A/i, 'elevador-fuera-de-servicio.jpg')
  await expect(luis.getByText('Esperando confirmación')).toBeVisible({ timeout: 10_000 })
  await expect(luis.getByText('Posible falla', { exact: true })).toBeVisible()
  await expect(luis.getByRole('img', { name: /rostros difuminados/ })).toBeVisible()
  await sinViolacionesGraves(luis)

  // Ana busca una ruta a Copilco: en su detalle, la app le pregunta si el elevador sigue
  // fuera de servicio.
  const ana = await personaEn(browser)
  await ana.addInitScript(() =>
    localStorage.setItem('ra.perfil', JSON.stringify({ tipo_movilidad: 'silla_manual' })),
  )
  const peticion = {
    origen: { clave_estacion: 'METRO-TASQUENA' },
    destino: { clave_estacion: 'METRO-COPILCO' },
    perfil: PERFIL_SILLA,
  }
  const plan = await (await ana.request.post('/api/rutas/plan', { data: peticion })).json()
  type Alt = { orden: number; equipos_criticos: { codigo: string; estado: string }[] }
  const conFalla = plan.alternativas.find((a: Alt) =>
    a.equipos_criticos.some((e) => e.codigo === 'METRO-COPILCO/SAL-A/ELV' && e.estado === 'FALLA_PROBABLE'),
  )
  expect(conFalla).toBeDefined()
  await ana.addInitScript((b) => sessionStorage.setItem('ra.busqueda', b), JSON.stringify({
    origen: { nombre: 'Tasqueña', lat: 19.3438, lon: -99.1395, clave_estacion: 'METRO-TASQUENA' },
    destino: { nombre: 'Copilco', lat: 19.3361, lon: -99.177, clave_estacion: 'METRO-COPILCO' },
    respuesta: plan,
  }))
  await ana.goto(`/ruta/${conFalla.orden}`)
  const pregunta = ana.getByRole('region', { name: /Sigue fuera de servicio el elevador salida A/ })
  await pregunta.getByRole('button', { name: 'Sí, sigue fuera de servicio' }).click()
  await expect(pregunta.getByRole('status')).toContainText('¡Gracias!')
  await sinViolacionesGraves(ana)

  // Con la corroboración, el reporte de Luis se verifica y la falla queda confirmada
  // (dos personas distintas, una con foto verificada).
  await expect(luis.getByText('Falla confirmada', { exact: true })).toBeVisible({ timeout: 20_000 })
  await expect(luis.getByText('Verificado', { exact: true })).toBeVisible()
})

test('moderación: confirma un reporte en zona gris', async ({ browser, page }) => {
  const persona = await personaEn(browser)
  await reportar(persona, 'Pino Suárez', /elevador salida Pino Suárez/i, 'rampa-bloqueada.jpg')
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
