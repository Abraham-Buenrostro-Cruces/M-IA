// Mi perfil (F3-2). Se guarda sólo en este dispositivo (uso anónimo, D-16).
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  Button,
  Checkbox,
  Group,
  Input,
  Label,
  NumberField,
  Radio,
  RadioGroup,
  Text,
} from 'react-aria-components'
import { api, type PerfilEntrada, type PerfilPredefinido, type TipoMovilidad } from '../api/cliente'
import { usePerfil } from '../estado/almacen'

const boton =
  'inline-flex min-h-11 items-center justify-center rounded px-4 font-semibold outline-none data-[focus-visible]:outline-3 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-[var(--color-foco)]'

function Numero(props: {
  etiqueta: string
  valor: number
  min: number
  max: number
  paso?: number
  alCambiar: (n: number) => void
  descripcion: string
}) {
  return (
    <NumberField
      value={props.valor}
      minValue={props.min}
      maxValue={props.max}
      step={props.paso ?? 1}
      onChange={(n) => Number.isFinite(n) && props.alCambiar(n)}
      className="flex flex-col gap-1"
    >
      <Label className="font-semibold">{props.etiqueta}</Label>
      <Group className="flex w-48">
        <Button slot="decrement" className="min-h-11 min-w-11 rounded-l border border-gray-500">
          −
        </Button>
        <Input className="min-h-11 w-full border-y border-gray-500 text-center" />
        <Button slot="increment" className="min-h-11 min-w-11 rounded-r border border-gray-500">
          +
        </Button>
      </Group>
      <Text slot="description" className="text-sm text-texto-suave">
        {props.descripcion}
      </Text>
    </NumberField>
  )
}

export function Perfil() {
  const [guardado, guardar] = usePerfil()
  const { data: perfiles, isError } = useQuery({ queryKey: ['perfiles'], queryFn: api.perfiles, staleTime: Infinity })
  const [tipo, setTipo] = useState<TipoMovilidad | null>(guardado?.tipo_movilidad ?? null)
  const base: PerfilPredefinido | undefined = perfiles?.find((p) => p.tipo_movilidad === tipo)
  const [ediciones, setEdiciones] = useState<Partial<PerfilEntrada>>({})
  const [mensaje, setMensaje] = useState('')

  // Valores efectivos: los del predefinido, sobrescritos por el perfil guardado (si es del
  // mismo tipo) y por lo que la persona está editando. Se derivan en el render.
  const previo = guardado?.tipo_movilidad === tipo ? guardado : null
  const ajustes = {
    escalones_max: ediciones.escalones_max ?? previo?.escalones_max ?? base?.escalones_max,
    distancia_pie_max_m:
      ediciones.distancia_pie_max_m ?? previo?.distancia_pie_max_m ?? base?.distancia_pie_max_m,
    puede_escalera_electrica:
      ediciones.puede_escalera_electrica ?? previo?.puede_escalera_electrica ?? base?.puede_escalera_electrica,
  }
  const setAjustes = (f: (a: Partial<PerfilEntrada>) => Partial<PerfilEntrada>) => setEdiciones(f)

  function alGuardar() {
    if (!base || !tipo) return
    // Sólo se guardan los valores que difieren del predefinido.
    const perfil: PerfilEntrada = { tipo_movilidad: tipo }
    if (ajustes.escalones_max !== base.escalones_max) perfil.escalones_max = ajustes.escalones_max
    if (ajustes.distancia_pie_max_m !== base.distancia_pie_max_m)
      perfil.distancia_pie_max_m = ajustes.distancia_pie_max_m
    if (ajustes.puede_escalera_electrica !== base.puede_escalera_electrica)
      perfil.puede_escalera_electrica = ajustes.puede_escalera_electrica
    guardar(perfil)
    setMensaje('Perfil guardado en este dispositivo.')
  }

  return (
    <>
      <h1 className="text-3xl font-bold text-marca-oscuro">Mi perfil de movilidad</h1>
      <p className="mt-2">
        Describe lo que necesitas para moverte, no un diagnóstico. Se guarda <strong>sólo en este
        dispositivo</strong> y se usa únicamente para calcular tus rutas.
      </p>

      {isError && (
        <p role="alert" className="mt-4 rounded bg-red-50 p-3 text-[#b42318]">
          No pudimos cargar los perfiles. Revisa tu conexión.
        </p>
      )}

      {perfiles && (
        <RadioGroup
          value={tipo}
          onChange={(v) => {
            setTipo(v as TipoMovilidad)
            setEdiciones({})
            setMensaje('')
          }}
          className="mt-6 flex flex-col gap-2"
        >
          <Label className="text-xl font-bold">¿Cómo te mueves?</Label>
          {perfiles.map((p) => (
            <Radio
              key={p.tipo_movilidad}
              value={p.tipo_movilidad}
              className="flex min-h-11 cursor-pointer items-center gap-3 rounded border border-gray-400 px-3 data-[selected]:border-2 data-[selected]:border-marca data-[selected]:bg-blue-50 data-[focus-visible]:outline-3 data-[focus-visible]:outline-[var(--color-foco)]"
            >
              {({ isSelected }) => (
                <>
                  <span aria-hidden="true" className="text-xl">
                    {isSelected ? '◉' : '○'}
                  </span>
                  {p.nombre}
                </>
              )}
            </Radio>
          ))}
        </RadioGroup>
      )}

      {base && (
        <section aria-labelledby="titulo-ajustes" className="mt-6 space-y-4">
          <h2 id="titulo-ajustes" className="text-xl font-bold">
            Ajustes (opcional)
          </h2>
          <Numero
            etiqueta="Escalones que puedes subir seguidos"
            valor={ajustes.escalones_max ?? 0}
            min={0}
            max={60}
            alCambiar={(n) => setAjustes((a) => ({ ...a, escalones_max: n }))}
            descripcion="Una escalera típica del Metro tiene unos 24 escalones."
          />
          <Numero
            etiqueta="Distancia máxima a pie (metros)"
            valor={ajustes.distancia_pie_max_m ?? 800}
            min={100}
            max={3000}
            paso={100}
            alCambiar={(n) => setAjustes((a) => ({ ...a, distancia_pie_max_m: n }))}
            descripcion="Por tramo: de tu origen a la estación y de la estación a tu destino."
          />
          <Checkbox
            isSelected={ajustes.puede_escalera_electrica ?? false}
            onChange={(v) => setAjustes((a) => ({ ...a, puede_escalera_electrica: v }))}
            className="flex min-h-11 cursor-pointer items-center gap-3 data-[focus-visible]:outline-3 data-[focus-visible]:outline-[var(--color-foco)]"
          >
            {({ isSelected }) => (
              <>
                <span aria-hidden="true" className="text-xl">
                  {isSelected ? '☑' : '☐'}
                </span>
                Puedo usar escaleras eléctricas
              </>
            )}
          </Checkbox>
        </section>
      )}

      <div className="mt-6 flex flex-wrap gap-3">
        <Button onPress={alGuardar} isDisabled={!base} className={`${boton} bg-marca text-white data-[disabled]:bg-gray-400`}>
          Guardar perfil
        </Button>
        {guardado && (
          <Button
            onPress={() => {
              guardar(null)
              setTipo(null)
              setMensaje('Perfil borrado de este dispositivo.')
            }}
            className={`${boton} border border-gray-500`}
          >
            Borrar mi perfil
          </Button>
        )}
      </div>
      <p aria-live="polite" className="mt-3 font-semibold text-[#1a7f37]">
        {mensaje}
      </p>
    </>
  )
}
