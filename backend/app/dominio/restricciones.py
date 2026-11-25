"""Restricciones duras por perfil (F2-2, regla de seguridad 3, D-20).

Una arista excluida **no existe** para esa persona: ningún costo, modelo o ranking
puede devolver una ruta que la use. Cada exclusión lleva su motivo para poder
explicar rutas descartadas y el caso "sin ruta segura".
"""

from dataclasses import dataclass

from app.dominio.red import ESTADO_SIN_DATO, EstadoEquipo, Perfil

# D-20: estados que eliminan las aristas que dependen del equipo.
ESTADOS_BLOQUEANTES = frozenset({"FALLA_CONFIRMADA", "MANTENIMIENTO", "DESCONOCIDO"})

NOMBRE_ESTADO = {
    "FALLA_CONFIRMADA": "falla confirmada",
    "MANTENIMIENTO": "en mantenimiento",
    "DESCONOCIDO": "sin información reciente",
    "FALLA_PROBABLE": "posible falla reportada",
    "OPERATIVO": "operativo",
}

NOMBRE_TIPO = {
    "ELEVADOR": "elevador",
    "RAMPA": "rampa",
    "SALVAESCALERAS": "salvaescaleras",
    "ESCALERA_ELECTRICA": "escalera eléctrica",
    "ACCESO_A_NIVEL": "acceso a nivel",
    "PASILLO": "pasillo",
    "ESCALERA_FIJA": "escalera",
}


@dataclass(frozen=True)
class Exclusion:
    clase: str  # "fisica" | "estado"
    motivo: str
    equipo: str | None = None


def estado_de(codigo: str | None, estados: dict[str, EstadoEquipo]) -> EstadoEquipo:
    return estados.get(codigo, ESTADO_SIN_DATO) if codigo else ESTADO_SIN_DATO


def exclusion(arista: dict, perfil: Perfil, estados: dict[str, EstadoEquipo]) -> Exclusion | None:
    """Motivo por el que ``perfil`` no puede recorrer la arista, o ``None`` si puede.

    Se revisan primero las restricciones físicas: si la persona no puede usar una
    escalera eléctrica, que además esté descompuesta es irrelevante.
    """
    clase = arista["clase"]
    if clase == "CAMINAR" and arista["longitud_m"] > perfil.distancia_pie_max_m:
        return Exclusion("fisica", f"caminata de {arista['longitud_m']:.0f} m")
    if clase != "CONEXION":
        return None

    c = arista["conexion"]
    if c.escalones > perfil.escalones_max:
        return Exclusion("fisica", f"{NOMBRE_TIPO.get(c.tipo, c.tipo)} con {c.escalones} escalones")
    if c.pendiente_pct > perfil.pendiente_max_pct:
        return Exclusion("fisica", f"{NOMBRE_TIPO[c.tipo]} con pendiente de {c.pendiente_pct:g} %")
    if c.tipo == "ESCALERA_ELECTRICA" and not perfil.puede_escalera_electrica:
        return Exclusion("fisica", "escalera eléctrica")
    if c.equipo:
        estado = estado_de(c.equipo, estados).estado
        if estado in ESTADOS_BLOQUEANTES:
            return Exclusion("estado", NOMBRE_ESTADO[estado], equipo=c.equipo)
    return None
