"""Pruebas del puntaje s (F4-3)."""

import pytest

from app.dominio.validacion import (
    AnalisisImagen,
    clasificar,
    puntaje,
    reputacion,
    termino_corroboracion,
    termino_geo,
)

ELEVADOR_FUERA = AnalisisImagen("elevador", "fuera_de_servicio", ("FUERA DE SERVICIO",), 0.88)
RAMPA_LIBRE = AnalisisImagen("rampa", "sin_problema", (), 0.9)
INDETERMINADA = AnalisisImagen("ninguno", "indeterminado", (), 0.5)


def test_flujo_2_con_buena_reputacion_se_verifica_solo():
    """Doc 06, flujo 2: foto clara, dentro de la geocerca, reputación alta -> VERIFICADO_AUTO."""
    d = puntaje("fuera_de_servicio", ELEVADOR_FUERA, 40, reputacion=0.9)
    assert d.s == pytest.approx(0.45 * 0.88 + 0.25 + 0.15 * 0.9)
    assert d.estado_validacion == "VERIFICADO_AUTO"


def test_persona_nueva_con_la_misma_foto_queda_en_zona_gris():
    d = puntaje("fuera_de_servicio", ELEVADOR_FUERA, 40, reputacion=0.5)
    assert d.estado_validacion == "PENDIENTE_CORROBORACION"


def test_sin_foto_nunca_se_verifica_solo():
    d = puntaje("fuera_de_servicio", None, 0, reputacion=1.0, votos_confirma=0)
    assert d.s == pytest.approx(0.25 + 0.15)
    assert d.estado_validacion == "PENDIENTE_CORROBORACION"
    assert "sin foto" in d.motivos


def test_foto_que_contradice_el_reporte_no_suma():
    d = puntaje("fuera_de_servicio", RAMPA_LIBRE, 40, reputacion=0.5)
    assert d.visual == 0 and "la foto no respalda el reporte" in d.motivos


def test_funciona_con_foto_de_equipo_sin_problema_suma():
    assert puntaje("funciona", RAMPA_LIBRE, 40, reputacion=0.9).visual == 0.9


def test_foto_indeterminada_aporta_la_mitad():
    assert puntaje("fuera_de_servicio", INDETERMINADA, 40, 0.5).visual == pytest.approx(0.25)


def test_foto_duplicada_penaliza():
    limpia = puntaje("fuera_de_servicio", ELEVADOR_FUERA, 40, 0.9)
    dup = puntaje("fuera_de_servicio", ELEVADOR_FUERA, 40, 0.9, duplicada=True)
    assert dup.s == pytest.approx(limpia.s - 0.5)
    assert dup.estado_validacion == "BAJA_CONFIANZA"


def test_contenido_inapropiado_se_rechaza():
    mala = AnalisisImagen("ninguno", "indeterminado", (), 0.9, contenido_apropiado=False)
    assert puntaje("fuera_de_servicio", mala, 10, 1.0).estado_validacion == "RECHAZADO"


@pytest.mark.parametrize(
    ("distancia", "geo"), [(None, 0), (0, 1), (150, 1), (325, 0.5), (500, 0), (900, 0)]
)
def test_geocerca(distancia, geo):
    assert termino_geo(distancia) == pytest.approx(geo)


@pytest.mark.parametrize(("si", "no", "valor"), [(0, 0, 0), (1, 0, 0.5), (2, 0, 1), (3, 1, 0.75)])
def test_corroboracion(si, no, valor):
    assert termino_corroboracion(si, no) == pytest.approx(valor)


def test_corroboracion_sube_un_reporte_de_zona_gris():
    sin = puntaje("fuera_de_servicio", ELEVADOR_FUERA, 40, 0.5)
    con = puntaje("fuera_de_servicio", ELEVADOR_FUERA, 40, 0.5, votos_confirma=2)
    assert sin.estado_validacion == "PENDIENTE_CORROBORACION"
    assert con.estado_validacion == "VERIFICADO_AUTO"


@pytest.mark.parametrize(
    ("s", "estado"),
    [
        (0.75, "VERIFICADO_AUTO"),
        (0.74, "PENDIENTE_CORROBORACION"),
        (0.40, "PENDIENTE_CORROBORACION"),
        (0.39, "BAJA_CONFIANZA"),
    ],
)
def test_umbrales(s, estado):
    assert clasificar(s) == estado


def test_reputacion_beta():
    assert reputacion(0, 0) == 0.5
    assert reputacion(8, 0) == pytest.approx(0.9)
    assert reputacion(0, 3) == pytest.approx(0.2)
