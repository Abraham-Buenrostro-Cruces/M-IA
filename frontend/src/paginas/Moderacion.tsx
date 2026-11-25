// Consola mínima de moderación (F4-6). El rol se verifica en el servidor: el token sólo
// identifica; quien no es moderador recibe 403 aunque abra esta página.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Button, Input, Label, Text, TextField } from 'react-aria-components'
import { api, CLAVE_TOKEN_MODERACION, type ReporteModeracion } from '../api/cliente'
import { FotoEvidencia } from '../componentes/FotoEvidencia'
import { fechaHora, haceCuanto, NOMBRE_TIPO_PROBLEMA } from '../util/formato'

const boton =
  'inline-flex min-h-11 items-center justify-center rounded px-4 font-semibold outline-none data-[focus-visible]:outline-3 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-[var(--color-foco)]'

function Desglose({ d }: { d: ReporteModeracion['desglose'] }) {
  if (!d) return null
  const fila = (nombre: string, valor: unknown) => (
    <div key={nombre} className="flex justify-between gap-4">
      <dt>{nombre}</dt>
      <dd className="font-mono">{typeof valor === 'number' ? valor.toFixed(2) : String(valor)}</dd>
    </div>
  )
  return (
    <dl className="mt-2 max-w-xs text-sm">
      {fila('Visual', d.visual)}
      {fila('Ubicación', d.geo)}
      {fila('Reputación', d.reputacion)}
      {fila('Corroboración', d.corroboracion)}
      {fila('Penalizaciones', d.penalizaciones)}
      {fila('Puntaje s', d.s)}
    </dl>
  )
}

function Tarjeta({ r }: { r: ReporteModeracion }) {
  const qc = useQueryClient()
  const decidir = useMutation({
    mutationFn: (decision: 'CONFIRMAR' | 'RECHAZAR') => api.decidir(r.id_reporte, decision),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['moderacion'] }),
  })
  const id = `rep-${r.id_reporte}`
  return (
    <article aria-labelledby={id} className="rounded-lg border border-gray-300 p-4">
      <h2 id={id} className="text-lg font-bold">
        {NOMBRE_TIPO_PROBLEMA[r.tipo_problema]} · {r.nombre_estacion}
      </h2>
      <p>{r.referencia_equipo ?? 'Sin equipo identificado'}</p>
      <p className="text-sm text-texto-suave" title={fechaHora(r.creado_en)}>
        Enviado {haceCuanto(r.creado_en)} · votos: {r.votos_confirma} confirman, {r.votos_niega} niegan
      </p>
      {r.descripcion && <p className="mt-2 italic">“{r.descripcion}”</p>}
      {r.motivos.length > 0 && (
        <ul className="mt-2 list-disc pl-6 text-sm">
          {r.motivos.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      )}
      <Desglose d={r.desglose} />
      {r.id_evidencia ? (
        <div className="mt-3">
          <FotoEvidencia id={r.id_evidencia} moderacion alt={`Foto del reporte en ${r.nombre_estacion}, ya saneada`} />
        </div>
      ) : (
        <p className="mt-3">Sin foto.</p>
      )}
      <div className="mt-4 flex flex-wrap gap-3">
        <Button onPress={() => decidir.mutate('CONFIRMAR')} isDisabled={decidir.isPending} className={`${boton} bg-[#1a7f37] text-white`}>
          Confirmar<span className="sr-only"> el reporte de {r.nombre_estacion}</span>
        </Button>
        <Button onPress={() => decidir.mutate('RECHAZAR')} isDisabled={decidir.isPending} className={`${boton} border border-[#b42318] text-[#b42318]`}>
          Rechazar<span className="sr-only"> el reporte de {r.nombre_estacion}</span>
        </Button>
      </div>
      {decidir.isError && (
        <p role="alert" className="mt-2 text-[#b42318]">
          {decidir.error.message}
        </p>
      )}
    </article>
  )
}

export function Moderacion() {
  const [token, setToken] = useState(() => localStorage.getItem(CLAVE_TOKEN_MODERACION))
  const [texto, setTexto] = useState('')
  const yo = useQuery({ queryKey: ['moderacion', 'yo', token], queryFn: api.yoModerador, enabled: !!token, retry: false })
  const esModerador = yo.data?.rol === 'moderador' || yo.data?.rol === 'admin'
  const cola = useQuery({
    queryKey: ['moderacion', 'cola'],
    queryFn: api.colaModeracion,
    enabled: esModerador,
    refetchInterval: 20_000,
  })

  if (!token || yo.isError || (yo.data && !esModerador)) {
    return (
      <>
        <h1 className="text-3xl font-bold text-marca-oscuro">Moderación</h1>
        {(yo.isError || (yo.data && !esModerador)) && (
          <p role="alert" className="mt-4 rounded bg-red-50 p-3 text-[#b42318]">
            Ese token no tiene rol de moderación.
          </p>
        )}
        <form
          className="mt-4 space-y-3"
          onSubmit={(e) => {
            e.preventDefault()
            localStorage.setItem(CLAVE_TOKEN_MODERACION, texto.trim())
            setToken(texto.trim())
          }}
        >
          <TextField value={texto} onChange={setTexto} type="password" isRequired className="flex flex-col gap-1">
            <Label className="font-semibold">Token de moderación</Label>
            <Input className="min-h-11 rounded border border-gray-500 px-3" autoComplete="off" />
            <Text slot="description" className="text-sm text-texto-suave">
              En desarrollo se obtiene con data/scripts/crear_moderador_dev.py.
            </Text>
          </TextField>
          <Button type="submit" className={`${boton} bg-marca text-white`}>
            Entrar
          </Button>
        </form>
      </>
    )
  }

  return (
    <>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-3xl font-bold text-marca-oscuro">Moderación</h1>
        <Button
          onPress={() => {
            localStorage.removeItem(CLAVE_TOKEN_MODERACION)
            setToken(null)
          }}
          className={`${boton} border border-gray-500`}
        >
          Salir
        </Button>
      </div>
      <p className="mt-2">Reportes en zona gris: el sistema no pudo verificarlos solo.</p>
      {cola.isPending && <p className="mt-4">Cargando…</p>}
      <p aria-live="polite" className="mt-4 font-semibold">
        {cola.data && (cola.data.length === 0 ? 'No hay reportes por revisar.' : `${cola.data.length} por revisar.`)}
      </p>
      <div className="mt-4 space-y-4">
        {cola.data?.map((r) => (
          <Tarjeta key={r.id_reporte} r={r} />
        ))}
      </div>
    </>
  )
}
