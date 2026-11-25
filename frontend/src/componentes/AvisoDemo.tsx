// Franja de "datos de demostración" (regla 4 de CLAUDE.md): el inventario de equipos y sus
// estados son de demostración mientras no existan datos reales.
export function AvisoDemo({ visible = true }: { visible?: boolean }) {
  if (!visible) return null
  return (
    <p className="mb-4 rounded border-l-4 border-[#9a6700] bg-amber-50 px-3 py-2 text-sm text-texto">
      <strong>Datos de demostración.</strong> Los elevadores, rampas y sus estados son
      simulados para el piloto de las Líneas 2 y 3; no los uses para planear un viaje real.
    </p>
  )
}
