// Campo de origen/destino con autocompletado (F3-1). React Aria ComboBox resuelve el patrón
// ARIA combobox: navegación con flechas, Enter para elegir, Escape para cerrar y anuncios
// para lectores de pantalla.
import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import {
  Button,
  ComboBox,
  Input,
  Label,
  ListBox,
  ListBoxItem,
  Popover,
  Text,
} from 'react-aria-components'
import { api, type Lugar } from '../api/cliente'
import type { PuntoElegido } from '../estado/plan'

function useRetardado<T>(valor: T, ms: number): T {
  const [v, setV] = useState(valor)
  useEffect(() => {
    const t = setTimeout(() => setV(valor), ms)
    return () => clearTimeout(t)
  }, [valor, ms])
  return v
}

type Opcion = { id: string; lugar: Lugar }

type Props = {
  etiqueta: string
  valor: PuntoElegido | null
  alElegir: (l: Lugar | null) => void
  descripcion?: string
}

export function BuscadorLugar({ etiqueta, valor, alElegir, descripcion }: Props) {
  const [texto, setTexto] = useState(valor?.nombre ?? '')
  // Si el padre cambia el valor (p. ej. "Usar mi ubicación"), el texto se ajusta durante el
  // render en vez de en un efecto: evita un render extra con el texto viejo.
  const [valorPrevio, setValorPrevio] = useState(valor)
  if (valor !== valorPrevio) {
    setValorPrevio(valor)
    setTexto(valor?.nombre ?? '')
  }
  const consulta = useRetardado(texto.trim(), 250)
  const { data: lugares = [], isFetching, isError } = useQuery({
    queryKey: ['lugares', consulta],
    queryFn: ({ signal }) => api.lugares(consulta, signal),
    enabled: consulta.length >= 2 && consulta !== valor?.nombre,
    staleTime: 5 * 60_000,
  })
  const items: Opcion[] = lugares.map((l, i) => ({ id: String(i), lugar: l }))

  return (
    <ComboBox
      className="flex flex-col gap-1"
      items={items}
      inputValue={texto}
      onInputChange={(t) => {
        setTexto(t)
        if (valor && t !== valor.nombre) alElegir(null)
      }}
      onSelectionChange={(id) => {
        const elegido = items.find((x) => x.id === id)?.lugar ?? null
        alElegir(elegido)
        if (elegido) setTexto(elegido.nombre)
      }}
      menuTrigger="input"
      allowsEmptyCollection
    >
      <Label className="font-semibold">{etiqueta}</Label>
      <div className="flex">
        <Input
          className="min-h-11 w-full rounded-l border border-gray-500 px-3 text-base"
          placeholder="Estación o lugar, p. ej. Zócalo"
        />
        <Button
          aria-label={`Mostrar sugerencias de ${etiqueta.toLowerCase()}`}
          className="min-h-11 min-w-11 rounded-r border border-l-0 border-gray-500 bg-gray-50"
        >
          <span aria-hidden="true">▾</span>
        </Button>
      </div>
      {descripcion && (
        <Text slot="description" className="text-sm text-texto-suave">
          {descripcion}
        </Text>
      )}
      <Popover className="w-(--trigger-width) overflow-auto rounded border border-gray-400 bg-white shadow-lg">
        <ListBox
          className="max-h-72 outline-none"
          renderEmptyState={() => (
            <p className="px-3 py-2 text-texto-suave">
              {isError
                ? 'No pudimos buscar. Revisa tu conexión.'
                : isFetching || consulta.length < 2
                  ? 'Buscando…'
                  : 'Sin coincidencias.'}
            </p>
          )}
        >
          {(item: Opcion) => (
            <ListBoxItem
              id={item.id}
              textValue={item.lugar.nombre}
              className="cursor-pointer px-3 py-2 outline-none data-[focused]:bg-blue-50 data-[selected]:font-semibold"
            >
              <span className="block">{item.lugar.nombre}</span>
              <span className="block text-sm text-texto-suave">
                {item.lugar.tipo === 'estacion' ? 'Estación · ' : ''}
                {item.lugar.detalle}
              </span>
            </ListBoxItem>
          )}
        </ListBox>
      </Popover>
    </ComboBox>
  )
}
