"""Endpoint ``POST /rutas/plan`` (F2-5)."""

from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.adaptadores import fabrica
from app.dominio.planificador import Alternativa, ResultadoPlan
from app.dominio.red import Perfil, Punto
from app.ingesta.perfiles import PERFILES_SEMILLA
from app.modulos.rutas.esquemas import (
    AlternativaSalida,
    DescartadaSalida,
    EquipoCritico,
    ObstaculoSalida,
    OtraOpcionSalida,
    PasoSalida,
    PeticionPlan,
    PlanBSalida,
    RespuestaPlan,
    TramoSalida,
    Ubicacion,
)
from app.modulos.rutas.servicio import EstacionDesconocidaError, ServicioRutas

router = APIRouter(prefix="/rutas", tags=["rutas"])

_SEMILLA = {p["tipo_movilidad"]: p for p in PERFILES_SEMILLA}
_CAMPOS_PERFIL = ("escalones_max", "pendiente_max_pct", "puede_escalera_electrica",
                  "distancia_pie_max_m", "peso_seguridad_vs_tiempo")  # fmt: skip


@lru_cache
def obtener_servicio_rutas() -> ServicioRutas:
    """Se construye en la primera petición (no al importar), así la app arranca sin base."""
    from app.bd.sesion import fabrica_sesiones
    from app.modulos.rutas import repositorio

    sesiones = fabrica_sesiones()
    with sesiones() as s:
        red, demo = repositorio.cargar_red(s)

    def estados():
        with sesiones() as s:
            return repositorio.cargar_estados(s)

    return ServicioRutas(red, estados, fabrica.caminata(), datos_demostracion=demo)


def perfil_desde(peticion: PeticionPlan) -> Perfil:
    base = _SEMILLA[peticion.perfil.tipo_movilidad]
    valores = {
        c: getattr(peticion.perfil, c) if getattr(peticion.perfil, c) is not None else base[c]
        for c in _CAMPOS_PERFIL
    }
    return Perfil(tipo_movilidad=peticion.perfil.tipo_movilidad,
                  max_transbordos=peticion.max_transbordos, **valores)  # fmt: skip


def _punto(servicio: ServicioRutas, u: Ubicacion) -> Punto:
    if u.clave_estacion is not None:
        return servicio.punto_de_estacion(u.clave_estacion)
    return Punto(u.lat, u.lon)


def _alternativa(a: Alternativa, orden: int, recomendada: bool) -> AlternativaSalida:
    return AlternativaSalida(
            orden=orden,
            recomendada=recomendada,
            resumen=a.resumen,
            iar=a.iar,
            categoria_iar=a.categoria,
            tiempo_total_min=round(a.tiempo_total_s / 60, 1),
            distancia_pie_m=round(a.distancia_pie_m),
            transbordos=a.transbordos,
            pasos=[PasoSalida(tipo=p.tipo, descripcion=p.descripcion,
                              duracion_s=round(p.duracion_s), estacion=p.estacion,
                              equipo=p.equipo, asistencia=p.asistencia) for p in a.pasos],
            equipos_criticos=[EquipoCritico(
                codigo=e.codigo, tipo=e.tipo, referencia=e.referencia, estacion=e.estacion,
                nombre_estacion=e.nombre_estacion, estado=e.estado,
                prob_operativo=e.prob_operativo, ultima_verificacion=e.actualizado_en,
                horas_desde_verificacion=e.horas_desde_verificacion) for e in a.equipos],
            planes_b=[PlanBSalida(equipo=b.equipo, descripcion=b.descripcion)
                      for b in a.planes_b],
            explicacion=a.explicacion,
            advertencias=a.advertencias,
            trazo=a.puntos,
            tramos=[TramoSalida(tipo=t.tipo, puntos=t.puntos, route_id=t.route_id,
                                linea=t.linea, desde=t.desde, hasta=t.hasta) for t in a.tramos],
        )  # fmt: skip


def a_respuesta(r: ResultadoPlan, datos_demo: bool, ahora: datetime) -> RespuestaPlan:
    alternativas = [
        _alternativa(a, i + 1, recomendada=(i == 0 and r.hay_ruta_segura))
        for i, a in enumerate(r.alternativas)
    ]
    otras = [
        OtraOpcionSalida(
            tipo=o.tipo,
            titulo=o.titulo,
            descripcion=o.descripcion,
            # Numeradas aparte de las alternativas y nunca recomendadas (D-26).
            ruta=_alternativa(o.ruta, i + 1, recomendada=False),
            distancia_restante_m=(
                None if o.distancia_restante_m is None else round(o.distancia_restante_m)
            ),
            equipos_a_reparar=o.equipos_a_reparar,
            puntos_asistencia=[
                ObstaculoSalida(estacion=p.estacion, descripcion=p.descripcion)
                for p in o.puntos_asistencia
            ],
        )
        for i, o in enumerate(r.otras_opciones)
    ]
    return RespuestaPlan(
        hay_ruta_segura=r.hay_ruta_segura,
        aviso=r.aviso,
        alternativas=alternativas,
        otras_opciones=otras,
        descartadas=[DescartadaSalida(resumen=d.resumen, motivo=d.motivo) for d in r.descartadas],
        obstaculos=[
            ObstaculoSalida(estacion=o.estacion, descripcion=o.descripcion) for o in r.obstaculos
        ],  # fmt: skip
        sugerencias=r.sugerencias,
        datos_demostracion=datos_demo,
        calculado_en=ahora,
    )


@router.post("/plan", response_model=RespuestaPlan)
def plan(
    peticion: PeticionPlan,
    servicio: Annotated[ServicioRutas, Depends(obtener_servicio_rutas)],
) -> RespuestaPlan:
    """Calcula hasta 3 alternativas accesibles para el perfil indicado.

    Si no hay ruta segura, ``hay_ruta_segura`` es falso y se explican los obstáculos
    (regla de seguridad 5). El perfil no se registra en logs (regla 6).
    """
    try:
        origen, destino = _punto(servicio, peticion.origen), _punto(servicio, peticion.destino)
    except EstacionDesconocidaError as e:
        raise HTTPException(404, f"Estación desconocida o fuera de la red: {e}") from None
    resultado = servicio.planear(origen, destino, perfil_desde(peticion))
    return a_respuesta(resultado, servicio.datos_demostracion, datetime.now(UTC))
