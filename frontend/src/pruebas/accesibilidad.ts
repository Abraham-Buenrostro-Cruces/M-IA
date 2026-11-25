import axe from 'axe-core'

/**
 * Corre axe-core sobre un contenedor y devuelve sólo las violaciones graves
 * (impacto "serious" o "critical"), que es el criterio de aceptación de F3-5.
 *
 * Se desactiva "color-contrast" porque jsdom no calcula estilos reales; el
 * contraste se verificará con Playwright en un navegador real (F3-5).
 */
export async function violacionesGraves(contenedor: Element) {
  const resultado = await axe.run(contenedor, {
    rules: { 'color-contrast': { enabled: false } },
  })
  return resultado.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => `${v.id}: ${v.help}`)
}
