// Reportar un problema (F4-1, flujo 2): estación, equipo, tipo de problema, foto opcional.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Button, Checkbox, Label, Radio, RadioGroup, Text, TextArea, TextField } from 'react-aria-components'
import { useNavigate } from 'react-router'
import { api, type Lugar, type TipoProblema } from '../api/cliente'
import { BuscadorLugar } from '../componentes/BuscadorLugar'
import { Estado, SIMBOLO_EQUIPO } from '../componentes/Simbolo'
import { puntoDesdeLugar, type PuntoElegido } from '../estado/plan'
import { NOMBRE_TIPO_PROBLEMA } from '../util/formato'
import { distanciaM } from '../util/geo'

const boton =
  'inline-flex min-h-11 items-center justify-center rounded px-4 font-semibold outline-none data-[focus-visible]:outline-3 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-[var(--color-foco)]'
const opcion =
  'flex min-h-11 cursor-pointer items-center gap-3 rounded border border-gray-400 px-3 py-2 data-[selected]:border-2 data-[selected]:border-marca data-[selected]:bg-blue-50 data-[focus-visible]:outline-3 data-[focus-visible]:outline-[var(--color-foco)]'
const SIN_EQUIPO = 'ninguno'

function ubicacionActual(): Promise<GeolocationPosition> {
  return new Promise((ok, mal) => {
    if (!('geolocation' in navigator)) return mal(new Error('sin geolocalización'))
    navigator.geolocation.getCurrentPosition(ok, mal, { enableHighAccuracy: true, timeout: 10_000 })
  })
}

function Seleccion({ marcado, children }: { marcado: boolean; children: React.ReactNode }) {
  return (
    <>
      <span aria-hidden="true" className="text-xl">
        {marcado ? '◉' : '○'}
      </span>
      {children}
    </>
  )
}

export function Reportar() {
  const navegar = useNavigate()
  const [estacion, setEstacion] = useState<PuntoElegido | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [equipo, setEquipo] = useState<string | null>(null)
  const [tipo, setTipo] = useState<TipoProblema | null>(null)
  const [foto, setFoto] = useState<File | null>(null)
  const [vistaPrevia, setVistaPrevia] = useState<string | null>(null)
  const [descripcion, setDescripcion] = useState('')
  const [compartirUbicacion, setCompartirUbicacion] = useState(true)

  const clave = estacion?.clave_estacion ?? null
  const { data: detalle, isPending: cargandoEquipos } = useQuery({
    queryKey: ['estado-estacion', clave],
    queryFn: () => api.estadoEstacion(clave!),
    enabled: !!clave,
  })
  const qc = useQueryClient()

  function elegirEstacion(l: Lugar | null) {
    setEquipo(null)
    if (l && !l.clave_estacion) {
      setEstacion(null)
      setAviso('Elige una estación (no un lugar).')
      return
    }
    setAviso(null)
    setEstacion(l && puntoDesdeLugar(l))
  }

  async function estacionCercana() {
    setAviso(null)
    try {
      // Se espera el catálogo si aún no está: pulsar el botón al abrir la página no debe
      // buscar sobre una lista vacía.
      const [pos, catalogo] = await Promise.all([
        ubicacionActual(),
        qc.fetchQuery({ queryKey: ['estaciones'], queryFn: api.estaciones }),
      ])
      const conDatos = catalogo.estaciones.filter((e) => e.accesibilidad !== 'SIN_DATOS')
      const p = { lat: pos.coords.latitude, lon: pos.coords.longitude }
      const cercana = conDatos.reduce<(typeof conDatos)[number] | null>(
        (m, e) => (!m || distanciaM(p, e) < distanciaM(p, m) ? e : m),
        null,
      )
      if (!cercana || distanciaM(p, cercana) > 1000) {
        setAviso('No hay una estación con equipos registrados a menos de 1 km. Búscala por nombre.')
        return
      }
      setEquipo(null)
      setEstacion({ nombre: cercana.nombre, lat: cercana.lat, lon: cercana.lon, clave_estacion: cercana.clave })
    } catch {
      setAviso('No pudimos obtener tu ubicación. Busca la estación por nombre.')
    }
  }

  const enviar = useMutation({
    mutationFn: async () => {
      let ubicacion = null
      if (compartirUbicacion) {
        try {
          const pos = await ubicacionActual()
          ubicacion = {
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            precision_m: Math.round(pos.coords.accuracy),
          }
        } catch {
          ubicacion = null // sin ubicación el reporte igual se recibe (con menor puntaje)
        }
      }
      const id_subida = foto ? await api.subirFoto(foto) : null
      return api.crearReporte({
        clave_estacion: clave!,
        codigo_equipo: equipo && equipo !== SIN_EQUIPO ? equipo : null,
        tipo_problema: tipo!,
        descripcion: descripcion.trim() || null,
        ubicacion,
        id_subida,
      })
    },
    onSuccess: (r) => navegar(`/reportes/${r.id_reporte}`),
  })

  const listo = !!clave && !!equipo && !!tipo

  return (
    <>
      <h1 className="text-3xl font-bold text-marca-oscuro">Reportar un problema</h1>
      <p className="mt-2">
        Tu reporte ayuda a que otras personas no lleguen a un elevador o una rampa que no
        funciona. No necesitas cuenta.
      </p>

      <form
        className="mt-6 space-y-6"
        aria-label="Reportar un problema"
        onSubmit={(e) => {
          e.preventDefault()
          if (listo) enviar.mutate()
        }}
      >
        <section aria-labelledby="paso-estacion" className="space-y-2">
          <h2 id="paso-estacion" className="text-xl font-bold">
            1. ¿En qué estación?
          </h2>
          <BuscadorLugar etiqueta="Estación" valor={estacion} alElegir={elegirEstacion} />
          <Button onPress={estacionCercana} className={`${boton} border border-marca text-marca`}>
            <span aria-hidden="true">⌖ </span>Usar la estación más cercana
          </Button>
          {aviso && (
            <p role="alert" className="text-sm text-[#b42318]">
              {aviso}
            </p>
          )}
        </section>

        {clave && (
          <section aria-labelledby="paso-equipo">
            <h2 id="paso-equipo" className="text-xl font-bold">
              2. ¿Qué equipo?
            </h2>
            {cargandoEquipos ? (
              <p className="mt-2">Cargando equipos…</p>
            ) : (
              <RadioGroup aria-labelledby="paso-equipo" value={equipo} onChange={setEquipo} className="mt-2 flex flex-col gap-2">
                {detalle?.equipos.map((e) => (
                  <Radio key={e.codigo} value={e.codigo} className={opcion}>
                    {({ isSelected }) => (
                      <Seleccion marcado={isSelected}>
                        <span className="flex flex-col">
                          <span>
                            {e.referencia[0].toUpperCase() + e.referencia.slice(1)}
                          </span>
                          <Estado s={SIMBOLO_EQUIPO[e.estado] ?? SIMBOLO_EQUIPO.DESCONOCIDO} className="text-sm" />
                        </span>
                      </Seleccion>
                    )}
                  </Radio>
                ))}
                <Radio value={SIN_EQUIPO} className={opcion}>
                  {({ isSelected }) => <Seleccion marcado={isSelected}>Otro problema / no sé cuál</Seleccion>}
                </Radio>
              </RadioGroup>
            )}
          </section>
        )}

        {clave && (
          <RadioGroup value={tipo} onChange={(v) => setTipo(v as TipoProblema)} className="flex flex-col gap-2">
            <Label className="text-xl font-bold">3. ¿Qué pasa?</Label>
            {Object.entries(NOMBRE_TIPO_PROBLEMA).map(([valor, texto]) => (
              <Radio key={valor} value={valor} className={opcion}>
                {({ isSelected }) => <Seleccion marcado={isSelected}>{texto}</Seleccion>}
              </Radio>
            ))}
          </RadioGroup>
        )}

        {clave && (
          <section aria-labelledby="paso-foto" className="space-y-2">
            <h2 id="paso-foto" className="text-xl font-bold">
              4. Foto (opcional)
            </h2>
            <label htmlFor="foto" className="block">
              Una foto permite verificar el reporte más rápido. Antes de mostrarla a alguien
              borramos sus datos de ubicación y difuminamos los rostros.
            </label>
            <input
              id="foto"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              capture="environment"
              className="block min-h-11 w-full rounded border border-gray-500 p-2"
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null
                setFoto(f)
                if (vistaPrevia) URL.revokeObjectURL(vistaPrevia)
                setVistaPrevia(f ? URL.createObjectURL(f) : null)
              }}
            />
            {vistaPrevia && <img src={vistaPrevia} alt="Vista previa de la foto que vas a enviar" className="max-h-60 rounded border" />}
          </section>
        )}

        {clave && (
          <>
            <TextField value={descripcion} onChange={setDescripcion} maxLength={500} className="flex flex-col gap-1">
              <Label className="font-semibold">Comentario (opcional)</Label>
              <TextArea rows={3} className="rounded border border-gray-500 p-2" />
              <Text slot="description" className="text-sm text-texto-suave">
                Máximo 500 caracteres. No incluyas datos personales.
              </Text>
            </TextField>
            <Checkbox
              isSelected={compartirUbicacion}
              onChange={setCompartirUbicacion}
              className="flex min-h-11 cursor-pointer items-start gap-3 data-[focus-visible]:outline-3 data-[focus-visible]:outline-[var(--color-foco)]"
            >
              {({ isSelected }) => (
                <>
                  <span aria-hidden="true" className="text-xl">
                    {isSelected ? '☑' : '☐'}
                  </span>
                  <span>
                    Enviar mi ubicación actual para comprobar que estoy en la estación. Sólo se
                    usa para validar este reporte.
                  </span>
                </>
              )}
            </Checkbox>
          </>
        )}

        <Button type="submit" isDisabled={!listo || enviar.isPending} className={`${boton} w-full bg-marca text-white data-[disabled]:bg-gray-400`}>
          {enviar.isPending ? 'Enviando…' : 'Enviar reporte'}
        </Button>
        {enviar.isError && (
          <p role="alert" className="rounded bg-red-50 p-3 text-[#b42318]">
            {enviar.error.message}
          </p>
        )}
      </form>
    </>
  )
}
