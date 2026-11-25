// Franja de "datos de demostración" (regla 4 de CLAUDE.md): el inventario de equipos y sus
// estados son de demostración mientras no existan datos reales. Dice qué es real (las
// estaciones, las líneas y la accesibilidad general del GTFS) y qué no (D-19, D-25).
export function AvisoDemo({ visible = true }: { visible?: boolean }) {
  if (!visible) return null
  return (
    <p className="mb-4 rounded border-l-4 border-[#9a6700] bg-amber-50 px-3 py-2 text-sm text-texto">
      <strong>Datos de demostración.</strong> Las estaciones, las líneas y qué estaciones son
      accesibles vienen de los datos oficiales (GTFS), pero los elevadores, rampas y escaleras de
      cada estación son simulados y sus estados, sintéticos; no los uses para planear un viaje real.
    </p>
  )
}
