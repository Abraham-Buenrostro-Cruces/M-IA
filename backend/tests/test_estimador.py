"""Pruebas del estimador (F4-4): una por transición de la tabla de 04 §7.4 + D-22."""

from datetime import datetime, timedelta

import pytest

from app.dominio.estimador import (
    AVISO,
    FALLA,
    FUNCIONA,
    VIGENCIA,
    Evidencia,
    estimar,
)

T0 = datetime(2026, 11, 24, 8, 0, 0)


def h(horas: float) -> datetime:
    return T0 + timedelta(hours=horas)


def aviso(estado: str, horas: float = 0, fuente: str = "oficial") -> Evidencia:
    return Evidencia(AVISO, h(horas), estado_aviso=estado, causa=fuente)


def falla(horas: float, persona: str, s: float = 0.6, foto: bool = False) -> Evidencia:
    return Evidencia(FALLA, h(horas), s, persona, con_foto_verificada=foto)


def funciona(horas: float, persona: str, s: float = 0.8, foto: bool = True) -> Evidencia:
    return Evidencia(FUNCIONA, h(horas), s, persona, con_foto_verificada=foto)


def estado(evidencias, en_horas: float = 30) -> str:
    return estimar(evidencias, h(en_horas)).estado


# --------------------------------------------------------------------------- tabla de transiciones


def test_sin_evidencia_es_desconocido():
    r = estimar([], h(0))
    assert r.estado == "DESCONOCIDO"
    assert r.prob_operativo == pytest.approx(0.95)  # sólo el prior


@pytest.mark.parametrize("estado_aviso", ["OPERATIVO", "FALLA_CONFIRMADA", "MANTENIMIENTO"])
def test_un_aviso_fija_el_estado(estado_aviso):
    assert estado([aviso(estado_aviso)], 1) == estado_aviso


def test_operativo_a_falla_probable_con_un_reporte_s_040():
    assert estado([aviso("OPERATIVO"), falla(2, "luis", s=0.40)], 3) == "FALLA_PROBABLE"


def test_reporte_con_s_bajo_no_cambia_nada():
    assert estado([aviso("OPERATIVO"), falla(2, "luis", s=0.39)], 3) == "OPERATIVO"


def test_falla_probable_a_confirmada_dos_personas_una_con_foto():
    ev = [aviso("OPERATIVO"), falla(2, "luis", foto=True, s=0.8), falla(5, "ana")]
    assert estado(ev, 6) == "FALLA_CONFIRMADA"


def test_dos_personas_sin_foto_verificada_no_confirman():
    ev = [aviso("OPERATIVO"), falla(2, "luis"), falla(5, "ana")]
    assert estado(ev, 6) == "FALLA_PROBABLE"


def test_la_misma_persona_dos_veces_no_cuenta_como_dos():
    ev = [
        aviso("OPERATIVO"),
        falla(2, "luis", foto=True, s=0.8),
        falla(3, "luis", foto=True, s=0.9),
    ]
    assert estado(ev, 4) == "FALLA_PROBABLE"


def test_corroboracion_fuera_de_24_h_no_confirma():
    ev = [aviso("OPERATIVO"), falla(2, "luis", foto=True, s=0.8), falla(27, "ana")]
    assert estado(ev, 28) == "FALLA_PROBABLE"


def test_voto_de_otra_persona_cuenta_como_corroboracion():
    voto = Evidencia(FALLA, h(4), 0.5, "ana", causa="voto")
    ev = [aviso("OPERATIVO"), falla(2, "luis", foto=True, s=0.8), voto]
    r = estimar(ev, h(5))
    assert r.estado == "FALLA_CONFIRMADA" and r.causa == "voto"


def test_aviso_de_falla_confirma_directamente():
    assert estado([aviso("OPERATIVO"), falla(2, "luis"), aviso("FALLA_CONFIRMADA", 3)], 4) == (
        "FALLA_CONFIRMADA"
    )


def test_falla_confirmada_a_operativo_con_aviso():
    assert estado([aviso("FALLA_CONFIRMADA"), aviso("OPERATIVO", 10)], 11) == "OPERATIVO"


def test_falla_confirmada_a_operativo_con_dos_personas_con_foto():
    ev = [aviso("FALLA_CONFIRMADA"), funciona(10, "ana"), funciona(12, "beto")]
    assert estado(ev, 13) == "OPERATIVO"


def test_falla_probable_a_operativo_con_un_funciona_con_foto():
    ev = [aviso("OPERATIVO"), falla(2, "luis"), funciona(4, "ana")]
    assert estado(ev, 5) == "OPERATIVO"


def test_desconocido_a_operativo_con_un_funciona_con_foto():
    assert estado([funciona(1, "ana")], 2) == "OPERATIVO"


def test_desconocido_a_falla_probable_con_un_reporte():
    assert estado([falla(1, "luis")], 2) == "FALLA_PROBABLE"


def test_mantenimiento_solo_cambia_con_aviso():
    ev = [aviso("MANTENIMIENTO"), funciona(2, "ana"), funciona(3, "beto"), falla(4, "luis")]
    assert estado(ev, 5) == "MANTENIMIENTO"
    assert estado([*ev, aviso("OPERATIVO", 6)], 7) == "OPERATIVO"


def test_cualquier_estado_a_desconocido_tras_la_vigencia():
    ev = [aviso("OPERATIVO")]
    horas = VIGENCIA.total_seconds() / 3600
    assert estado(ev, horas - 1) == "OPERATIVO"
    r = estimar(ev, h(horas + 1))
    assert r.estado == "DESCONOCIDO" and r.causa == "decaimiento"


def test_hueco_de_evidencia_mayor_a_la_vigencia_reinicia_en_desconocido():
    # Falla confirmada hace mucho; luego un solo "funciona" sin foto: no debe volver a OPERATIVO
    # por arrastre, ni quedarse en falla: se reinicia en DESCONOCIDO y sin foto no sube.
    ev = [aviso("FALLA_CONFIRMADA"), funciona(24 * 10, "ana", foto=False)]
    assert estado(ev, 24 * 10 + 1) == "DESCONOCIDO"


# --------------------------------------------------------------------------- asimetría (regla 2)


def test_asimetria_fallar_es_mas_facil_que_recuperarse():
    """Un solo reporte basta para salir de OPERATIVO; un solo reporte nunca regresa a
    OPERATIVO desde FALLA_CONFIRMADA."""
    assert estado([aviso("OPERATIVO"), falla(1, "luis", s=0.45)], 2) == "FALLA_PROBABLE"
    assert estado([aviso("FALLA_CONFIRMADA"), funciona(1, "ana", s=1.0)], 2) == "FALLA_CONFIRMADA"


def test_funciona_sin_foto_no_saca_de_falla_probable():
    ev = [aviso("OPERATIVO"), falla(2, "luis"), funciona(3, "ana", foto=False)]
    assert estado(ev, 4) == "FALLA_PROBABLE"


def test_rechazar_el_reporte_y_reproducir_regresa_a_operativo():
    """El moderador rechaza el único reporte: se reproduce sin él (D-22)."""
    con = [aviso("OPERATIVO"), falla(2, "luis")]
    assert estado(con, 3) == "FALLA_PROBABLE"
    assert estado(con[:1], 3) == "OPERATIVO"


def test_orden_de_llegada_no_importa():
    ev = [aviso("OPERATIVO"), falla(2, "luis", foto=True, s=0.8), falla(5, "ana")]
    assert estimar(ev, h(6)) == estimar(list(reversed(ev)), h(6))


def test_evidencia_futura_se_ignora():
    assert estado([aviso("OPERATIVO"), falla(10, "luis")], 5) == "OPERATIVO"


# --------------------------------------------------------------------------- probabilidad


def test_probabilidad_baja_con_reportes_de_falla_y_se_recupera_con_el_tiempo():
    base = [aviso("OPERATIVO")]
    p_ok = estimar(base, h(1)).prob_operativo
    con_falla = [*base, falla(1, "luis", s=0.9)]
    p_falla = estimar(con_falla, h(1)).prob_operativo
    assert p_falla < p_ok
    # La evidencia de "funciona" (aviso) se olvida más rápido que la de falla:
    # con el tiempo, la probabilidad sigue bajando hacia lo que dice la falla.
    assert estimar(con_falla, h(48)).prob_operativo < p_falla


def test_escenario_demo_reproduce_probabilidades_del_flujo_1():
    """Aviso DEMO verificado hace 3 h -> p ≈ 0.99; hace 30 h -> p ≈ 0.98 (02 §4.2)."""
    assert estimar([aviso("OPERATIVO")], h(3)).prob_operativo == pytest.approx(0.99, abs=0.01)
    assert estimar([aviso("OPERATIVO")], h(30)).prob_operativo == pytest.approx(0.98, abs=0.01)
    r = estimar([aviso("FALLA_CONFIRMADA")], h(20))
    assert r.estado == "FALLA_CONFIRMADA" and r.prob_operativo < 0.3
