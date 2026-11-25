import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Button } from 'react-aria-components'
import { Link, useNavigate } from 'react-router'
import { api, type PerfilEntrada } from '../api/cliente'
import { BuscadorLugar } from '../componentes/BuscadorLugar'
import { ConsultaVoz, type ResultadoVoz } from '../componentes/ConsultaVoz'
import { usePerfil } from '../estado/almacen'
import { puntoDesdeLugar, ubicacionApi, useBusqueda, type PuntoElegido } from '../estado/plan'

// "Caminar poco" dicho por voz: tope de distancia a pie para esa búsqueda (m).
const CAMINAR_POCO_M = 300

const boton =
  'inline-flex min-h-11 items-center justify-center rounded px-4 font-semibold outline-none data-[focus-visible]:outline-3 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-[var(--color-foco)]'

function ResumenPerfil({ perfil }: { perfil: PerfilEntrada }) {
  const { data: perfiles } = useQuery({ queryKey: ['perfiles'], queryFn: api.perfiles, staleTime: Infinity })
  const nombre = perfiles?.find((p) => p.tipo_movilidad === perfil.tipo_movilidad)?.nombre
  return (
    <p>
      Perfil: <strong>{nombre ?? perfil.tipo_movilidad}</strong>
      {Object.values(perfil).filter((v) => v !== undefined && v !== null).length > 1 && ' (ajustado)'}.{' '}
      <Link to="/perfil" className="text-marca underline">
        Cambiar perfil
      </Link>
    </p>
  )
}

export function Planear() {
  const [perfil] = usePerfil()
  const { busqueda, guardar } = useBusqueda()
  const navegar = useNavigate()
  const [origen, setOrigen] = useState<PuntoElegido | null>(busqueda?.origen ?? null)
  const [destino, setDestino] = useState<PuntoElegido | null>(busqueda?.destino ?? null)
  const [errorUbicacion, setErrorUbicacion] = useState<string | null>(null)

  type Viaje = {
    origen: PuntoElegido
    destino: PuntoElegido
    max_transbordos?: number | null
    caminar_poco?: boolean
    porVoz?: boolean
  }
  const plan = useMutation({
    mutationFn: (v: Viaje) =>
      api.planear({
        origen: ubicacionApi(v.origen),
        destino: ubicacionApi(v.destino),
        // "Caminar poco" (dicho por voz) baja la distancia a pie sólo para esta búsqueda.
        perfil: v.caminar_poco
          ? { ...perfil!, distancia_pie_max_m: Math.min(perfil!.distancia_pie_max_m ?? CAMINAR_POCO_M, CAMINAR_POCO_M) }
          : perfil!,
        max_transbordos: v.max_transbordos ?? undefined,
      }),
    onSuccess: (respuesta, v) => {
      guardar({ origen: v.origen, destino: v.destino, respuesta, porVoz: v.porVoz })
      navegar('/resultados')
    },
  })

  function obtenerUbicacion(alObtener: (p: PuntoElegido) => void) {
    setErrorUbicacion(null)
    if (!('geolocation' in navigator)) {
      setErrorUbicacion('Tu navegador no permite obtener la ubicación.')
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => alObtener({ nombre: 'Mi ubicación', lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => setErrorUbicacion('No pudimos obtener tu ubicación. Escribe el origen.'),
      { enableHighAccuracy: true, timeout: 10_000 },
    )
  }

  function usarMiUbicacion() {
    obtenerUbicacion(setOrigen)
  }

  /** La voz ya resolvió origen y destino: se llenan los campos y se busca de inmediato. */
  function buscarPorVoz(r: ResultadoVoz) {
    const destinoVoz = puntoDesdeLugar(r.destino)
    setDestino(destinoVoz)
    const buscar = (o: PuntoElegido) => {
      setOrigen(o)
      if (perfil) plan.mutate({ origen: o, destino: destinoVoz, max_transbordos: r.max_transbordos, caminar_poco: r.caminar_poco, porVoz: true })
    }
    if (r.origen) buscar(puntoDesdeLugar(r.origen))
    else obtenerUbicacion(buscar)
  }

  return (
    <>
      <h1 className="text-3xl font-bold text-marca-oscuro">Planea un viaje accesible</h1>
      <p className="mt-2">
        Buscamos rutas en Metro, Metrobús, Tren Ligero y trenes suburbanos que priorizan llegar sin barreras. El tiempo es secundario.
      </p>

      <div className="mt-4 rounded bg-gray-50 p-3">
        {perfil ? (
          <ResumenPerfil perfil={perfil} />
        ) : (
          <p>
            Primero elige tu perfil de movilidad: así sabemos qué tramos puedes recorrer.{' '}
            <Link to="/perfil" className="font-semibold text-marca underline">
              Elegir perfil
            </Link>
          </p>
        )}
      </div>

      <form
        className="mt-6 space-y-5"
        aria-label="Buscar ruta"
        onSubmit={(e) => {
          e.preventDefault()
          if (origen && destino && perfil) plan.mutate({ origen, destino })
        }}
      >
        <div>
          <BuscadorLugar etiqueta="Origen" valor={origen} alElegir={(l) => setOrigen(l && puntoDesdeLugar(l))} />
          <Button onPress={usarMiUbicacion} className={`${boton} mt-2 border border-marca text-marca`}>
            <span aria-hidden="true">⌖ </span>Usar mi ubicación
          </Button>
          {origen?.nombre === 'Mi ubicación' && <p className="mt-1 text-sm">Origen: tu ubicación actual.</p>}
          {errorUbicacion && (
            <p role="alert" className="mt-1 text-sm text-[#b42318]">
              {errorUbicacion}
            </p>
          )}
        </div>
        <BuscadorLugar etiqueta="Destino" valor={destino} alElegir={(l) => setDestino(l && puntoDesdeLugar(l))} />

        <Button
          type="submit"
          isDisabled={!origen || !destino || !perfil || plan.isPending}
          className={`${boton} w-full bg-marca text-white data-[disabled]:bg-gray-400`}
        >
          {plan.isPending ? 'Buscando rutas…' : 'Buscar rutas accesibles'}
        </Button>
        {!perfil && <p className="text-sm text-texto-suave">Necesitas elegir un perfil para buscar.</p>}
        {plan.isError && (
          <p role="alert" className="rounded bg-red-50 p-3 text-[#b42318]">
            {plan.error.message}
          </p>
        )}
      </form>

      {perfil && <ConsultaVoz alListo={buscarPorVoz} />}
    </>
  )
}
