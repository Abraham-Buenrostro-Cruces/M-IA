import AxeBuilder from '@axe-core/playwright'
import { expect, type Locator, type Page } from '@playwright/test'

/** Pulsa Tab hasta que `objetivo` tenga el foco: comprueba que se alcanza con teclado. */
export async function tabularHasta(page: Page, objetivo: Locator, maximo = 40) {
  for (let i = 0; i < maximo; i++) {
    if (await objetivo.evaluate((el) => el === document.activeElement).catch(() => false)) return
    await page.keyboard.press('Tab')
  }
  throw new Error(`No se alcanzó con Tab en ${maximo} pulsaciones: ${objetivo}`)
}

/** axe-core con WCAG 2.1 A/AA; sólo se aceptan violaciones menores o moderadas. */
export async function sinViolacionesGraves(page: Page) {
  const r = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
  const graves = r.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => `${v.id} (${v.nodes.length}): ${v.help} → ${v.nodes[0]?.target.join(' ')}`)
  expect(graves).toEqual([])
}

/**
 * Elige una opción del autocompletado como lo haría la persona en ese dispositivo. En
 * celular, un toque con el dedo cuando la lista ya se acomodó: el clic de ratón de Playwright
 * desplaza antes la página y React Aria cierra la lista al desplazarse (con un dedo real no
 * pasa, ver la depuración de la Fase 5).
 */
export async function elegirOpcion(page: Page, opcion: Locator) {
  await expect(opcion).toBeVisible()
  const tactil = await page.evaluate(() => matchMedia('(pointer: coarse)').matches)
  if (!tactil) return opcion.click()
  await page.waitForTimeout(300) // la lista termina de posicionarse
  const caja = (await opcion.boundingBox())!
  await page.touchscreen.tap(caja.x + caja.width / 2, caja.y + caja.height / 2)
}

export const PERFIL_SILLA = { tipo_movilidad: 'silla_manual' }

export const PETICION_FLUJO1 = {
  origen: { clave_estacion: 'METRO-TASQUENA' },
  destino: { lat: 19.42965, lon: -99.1323 },
  perfil: PERFIL_SILLA,
}

/** Deja preparados perfil y búsqueda del flujo 1 (sin recorrer la UI). */
export async function prepararFlujo1(page: Page) {
  const r = await page.request.post('/api/rutas/plan', { data: PETICION_FLUJO1 })
  expect(r.ok()).toBe(true)
  const busqueda = {
    origen: { nombre: 'Tasqueña', lat: 19.3438, lon: -99.1395, clave_estacion: 'METRO-TASQUENA' },
    destino: { nombre: 'Museo de la Ciudad de México', lat: 19.42965, lon: -99.1323 },
    respuesta: await r.json(),
  }
  await page.addInitScript(
    ([perfil, b]) => {
      localStorage.setItem('ra.perfil', perfil)
      sessionStorage.setItem('ra.busqueda', b)
    },
    [JSON.stringify(PERFIL_SILLA), JSON.stringify(busqueda)],
  )
  return busqueda
}
