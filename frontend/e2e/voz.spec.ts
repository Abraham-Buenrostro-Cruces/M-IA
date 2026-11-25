// Consulta por voz en un navegador real (F5): Chromium graba con un micrófono simulado que
// "dice" uno de los audios SINTÉTICOS de data/demo/audios/. El navegador lo recodifica a
// webm, así que el transcriptor simulado no reconoce su huella y usa la frase de
// demostración (RA_VOZ_FRASE_DEMO = el flujo 1); lo que se prueba aquí es el recorrido
// completo: permiso, grabación, envío, interpretación, búsqueda y lectura del resultado.
import { expect, test } from '@playwright/test'
import { join } from 'node:path'
import { sinViolacionesGraves } from './utilidades'

const AUDIO = join(import.meta.dirname, '..', '..', 'data', 'demo', 'audios', 'flujo1.wav')

test.use({
  permissions: ['microphone'],
  launchOptions: {
    args: [
      '--use-fake-ui-for-media-stream',
      '--use-fake-device-for-media-stream',
      `--use-file-for-fake-audio-capture=${AUDIO}`,
    ],
  },
})

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() =>
    localStorage.setItem('ra.perfil', JSON.stringify({ tipo_movilidad: 'silla_manual' })),
  )
})

test('hablar: graba, entiende la frase y muestra las rutas', async ({ page }) => {
  await page.goto('/')
  const voz = page.getByRole('region', { name: 'Pídela con tu voz' })
  await sinViolacionesGraves(page)
  await voz.getByRole('button', { name: 'Hablar' }).click()
  await expect(voz.getByRole('status')).toContainText('Escuchando')
  await page.waitForTimeout(1500) // una frase corta
  await voz.getByRole('button', { name: 'Terminar' }).click()

  await expect(page.getByRole('heading', { level: 1, name: /Rutas de Tasqueña a Museo de la Ciudad/ })).toBeVisible()
  await expect(page.getByText(/Encontramos \d alternativas?/)).toBeVisible()
  await expect(page.getByRole('button', { name: /Escuchar el resultado/ })).toBeVisible()
})

test('aclarar por escrito: Viaducto del Metro o del Metrobús, y luego el origen', async ({ page }) => {
  await page.goto('/')
  const voz = page.getByRole('region', { name: 'Pídela con tu voz' })
  await voz.getByLabel('O escríbelo como lo dirías').fill('quiero ir a Viaducto')
  await voz.getByRole('button', { name: 'Enviar' }).click()
  const duda = voz.getByRole('group', { name: /Viaducto del Metro o Viaducto del Metrobús/ })
  await expect(duda).toBeVisible()
  await sinViolacionesGraves(page)
  await duda.getByRole('button', { name: /^Viaducto \(Metrobús/ }).click()
  const origen = voz.getByRole('group', { name: /Desde dónde sales/ })
  await expect(origen).toBeVisible()
  // Responder el origen escribiéndolo, como se diría.
  await voz.getByLabel('O escríbelo como lo dirías').fill('desde Zapata')
  await voz.getByRole('button', { name: 'Enviar' }).click()
  await expect(page.getByRole('heading', { level: 1, name: /Rutas de Zapata a Viaducto/ })).toBeVisible()
})
