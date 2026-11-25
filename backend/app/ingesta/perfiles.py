"""Perfiles de movilidad predefinidos (F1-5).

Son **necesidades funcionales**, nunca diagnósticos (D-16). Valores aprobados el
2026-11-24 como punto de partida razonable; cada persona puede ajustar el suyo.

- ``escalones_max``: escalones seguidos que la persona puede subir o bajar.
  Una escalera de vestíbulo a andén del inventario tiene 24.
- ``pendiente_max_pct``: 6 % es el máximo usual para rampas largas en silla manual;
  las sillas eléctricas, andaderas y carriolas toleran algo más.
- ``puede_escalera_electrica``: el reglamento del Metro no permite subir carriolas
  por escalera eléctrica, y no es segura con andadera.
- ``peso_seguridad_vs_tiempo``: cuánto domina la probabilidad de éxito sobre el
  tiempo en el costo w(e) (λ frente a α en docs/arquitectura/02, §4.2).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bd.modelos import PerfilAccesibilidad

PERFILES_SEMILLA: list[dict] = [
    {
        "tipo_movilidad": "silla_manual",
        "nombre": "Silla de ruedas manual",
        "requiere_elevador": True,
        "escalones_max": 0,
        "pendiente_max_pct": 6.0,
        "puede_escalera_electrica": False,
        "distancia_pie_max_m": 800,
        "peso_seguridad_vs_tiempo": 0.9,
    },
    {
        "tipo_movilidad": "silla_electrica",
        "nombre": "Silla de ruedas eléctrica",
        "requiere_elevador": True,
        "escalones_max": 0,
        "pendiente_max_pct": 8.0,
        "puede_escalera_electrica": False,
        "distancia_pie_max_m": 1500,
        "peso_seguridad_vs_tiempo": 0.9,
    },
    {
        "tipo_movilidad": "andadera",
        "nombre": "Andadera",
        "requiere_elevador": False,
        "escalones_max": 4,
        "pendiente_max_pct": 8.0,
        "puede_escalera_electrica": False,
        "distancia_pie_max_m": 500,
        "peso_seguridad_vs_tiempo": 0.8,
    },
    {
        "tipo_movilidad": "adulto_mayor",
        "nombre": "Persona adulta mayor",
        "requiere_elevador": False,
        "escalones_max": 30,
        "pendiente_max_pct": 10.0,
        "puede_escalera_electrica": True,
        "distancia_pie_max_m": 1000,
        "peso_seguridad_vs_tiempo": 0.7,
    },
    {
        "tipo_movilidad": "carriola",
        "nombre": "Carriola",
        "requiere_elevador": False,
        "escalones_max": 0,
        "pendiente_max_pct": 10.0,
        "puede_escalera_electrica": False,
        "distancia_pie_max_m": 1200,
        "peso_seguridad_vs_tiempo": 0.6,
    },
]


def cargar_perfiles(sesion: Session) -> int:
    """Inserta o actualiza los perfiles predefinidos (``id_usuario`` nulo), uno por tipo."""
    existentes = {
        p.tipo_movilidad: p
        for p in sesion.scalars(
            select(PerfilAccesibilidad).where(PerfilAccesibilidad.id_usuario.is_(None))
        )
    }
    for datos in PERFILES_SEMILLA:
        perfil = existentes.get(datos["tipo_movilidad"])
        if perfil is None:
            sesion.add(PerfilAccesibilidad(id_usuario=None, prefiere_voz=False, **datos))
        else:
            for campo, valor in datos.items():
                setattr(perfil, campo, valor)
    sesion.flush()
    return len(PERFILES_SEMILLA)
