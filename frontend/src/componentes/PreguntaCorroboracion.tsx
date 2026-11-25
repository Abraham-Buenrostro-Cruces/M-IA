// "¿Sigue fuera de servicio?" (F4-7). Se muestra en las rutas que pasan por un equipo con
// una posible falla reportada; la respuesta cuenta como corroboración de otra persona.
import { useMutation } from '@tanstack/react-query'
import { Button } from 'react-aria-components'
import { api, ErrorApi, type EquipoCritico } from '../api/cliente'

const boton =
  'inline-flex min-h-11 items-center justify-center rounded border px-4 font-semibold outline-none data-[focus-visible]:outline-3 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-[var(--color-foco)]'

const RESPUESTA_ERROR: Record<number, string> = {
  404: 'Gracias. No hay un reporte reciente de otra persona que confirmar.',
  409: 'Ya habías respondido sobre este equipo. ¡Gracias!',
}

export function PreguntaCorroboracion({ equipo }: { equipo: EquipoCritico }) {
  const votar = useMutation({ mutationFn: (voto: 'CONFIRMA' | 'NIEGA') => api.corroborar(equipo.codigo, voto) })
  const nombre = `${equipo.referencia} de ${equipo.nombre_estacion}`
  const id = `pregunta-${equipo.codigo}`

  return (
    <section aria-labelledby={id} className="mt-3 rounded border-2 border-[#9a6700] bg-amber-50 p-3">
      <h3 id={id} className="font-semibold">
        ¿Pasaste por ahí? ¿Sigue fuera de servicio el {nombre}?
      </h3>
      {votar.isSuccess ? (
        <p role="status" className="mt-2">
          ¡Gracias! Tu respuesta ayuda a confirmar el estado del equipo.
        </p>
      ) : votar.isError ? (
        <p role="status" className="mt-2">
          {votar.error instanceof ErrorApi && RESPUESTA_ERROR[votar.error.estado]
            ? RESPUESTA_ERROR[votar.error.estado]
            : votar.error.message}
        </p>
      ) : (
        <div className="mt-2 flex flex-wrap gap-2">
          <Button onPress={() => votar.mutate('CONFIRMA')} isDisabled={votar.isPending} className={`${boton} border-[#b42318] text-[#b42318]`}>
            Sí, sigue fuera de servicio
          </Button>
          <Button onPress={() => votar.mutate('NIEGA')} isDisabled={votar.isPending} className={`${boton} border-[#1a7f37] text-[#1a7f37]`}>
            No, ya funciona
          </Button>
        </div>
      )}
    </section>
  )
}
