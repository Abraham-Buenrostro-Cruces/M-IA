import { ToggleButton, ToggleButtonGroup } from 'react-aria-components'

export type Vista = 'lista' | 'mapa'

/** Selector Lista/Mapa. La lista es la vista por defecto y siempre equivalente al mapa. */
export function SelectorVista({ vista, alCambiar }: { vista: Vista; alCambiar: (v: Vista) => void }) {
  const clase =
    'min-h-11 px-4 font-semibold border border-marca text-marca outline-none data-[selected]:bg-marca data-[selected]:text-white data-[focus-visible]:outline-3 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-[var(--color-foco)]'
  return (
    <ToggleButtonGroup
      aria-label="Vista"
      selectionMode="single"
      disallowEmptySelection
      selectedKeys={[vista]}
      onSelectionChange={(s) => alCambiar([...s][0] as Vista)}
      className="inline-flex"
    >
      <ToggleButton id="lista" className={`${clase} rounded-l`}>
        Lista
      </ToggleButton>
      <ToggleButton id="mapa" className={`${clase} rounded-r border-l-0`}>
        Mapa
      </ToggleButton>
    </ToggleButtonGroup>
  )
}
