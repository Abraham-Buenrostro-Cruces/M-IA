"""Pruebas del motor de rutas sobre la red de juguete (tests/red_motor_juguete.py).

Cubren los criterios de aceptación de F2-1 a F2-4 y F2-6, y las reglas de seguridad
1, 3, 4 y 5 de CLAUDE.md.
"""

import itertools
from datetime import timedelta

import pytest

from app.dominio.grafo import DESTINO, ORIGEN, construir_topologia, grafo_para, nodo_tren
from app.dominio.planificador import Peticion, categoria_iar, planear
from app.dominio.red import EstadoEquipo, Perfil, Punto
from app.dominio.restricciones import exclusion
from app.ingesta.perfiles import PERFILES_SEMILLA
from tests.red_motor_juguete import (
    AHORA,
    DESTINO_EN_Z,
    DESTINO_PUNTO,
    ORIGEN_PUNTO,
    caminatas,
    construir_red,
    estados_ok,
    falla,
    perfil,
)

RED = construir_red()
TOPOLOGIA = construir_topologia(RED)


def plan(estados, perf=None, destino=DESTINO_PUNTO):
    pet = Peticion(perf or perfil(), ORIGEN_PUNTO, destino,
                   caminatas(RED, ORIGEN_PUNTO, destino), AHORA)  # fmt: skip
    return planear(RED, TOPOLOGIA, estados, pet)


def equipos_usados(alternativa):
    return {e.codigo for e in alternativa.equipos}


def estaciones_de_salida(resultado):
    return [a.resumen for a in resultado.alternativas]


# ------------------------------------------------------------- F2-1 grafo


def test_topologia_nodos_de_niveles_y_de_tren():
    trenes = [n for n in TOPOLOGIA if str(n).startswith("TREN|")]
    assert len(trenes) == 3 * 2 + 2 * 2  # L2: 3 estaciones × 2 direcciones; L3: 2 × 2
    assert set(RED.niveles) <= set(TOPOLOGIA.nodes)


def test_escalera_electrica_solo_de_subida():
    subida = TOPOLOGIA.get_edge_data("B/AND-2-C", "B/VES-2")
    bajada = TOPOLOGIA.get_edge_data("B/VES-2", "B/AND-2-C")
    assert any(d["conexion"].tipo == "ESCALERA_ELECTRICA" for d in subida.values())
    assert not any(d["conexion"].tipo == "ESCALERA_ELECTRICA" for d in bajada.values())


def test_abordar_cuesta_medio_intervalo_y_viajar_el_tiempo_del_gtfs():
    abordar = TOPOLOGIA.get_edge_data("A/AND-2-C", nodo_tren("R2", "C", "A"))[0]
    assert abordar["clase"] == "ABORDAR" and abordar["tiempo_s"] == 90  # 180 s / 2
    viajar = TOPOLOGIA.get_edge_data(nodo_tren("R2", "C", "A"), nodo_tren("R2", "C", "B"))[0]
    assert viajar["clase"] == "VIAJAR" and viajar["tiempo_s"] == 120


def test_aristas_paralelas_se_colapsan_en_la_mas_barata():
    g = grafo_para(TOPOLOGIA, perfil("adulto_mayor"), estados_ok(), AHORA, ())
    # Entre la salida A1 y el vestíbulo hay escalera y elevador: queda una sola arista.
    assert g.number_of_edges("A/SAL-A1", "A/VES") == 1


# ------------------------------------------------------------- F2-2 restricciones


def test_falla_confirmada_desvia_y_ninguna_ruta_usa_el_equipo():
    r = plan(estados_ok(E_C2=falla()))
    assert r.hay_ruta_segura
    assert all("E-C2" not in equipos_usados(a) for a in r.alternativas)
    assert "Estación B" in r.alternativas[0].resumen


def test_desconocido_nunca_es_accesible():
    estados = estados_ok()
    del estados["E-C2"]  # sin fila de estado = DESCONOCIDO (regla de seguridad 1)
    r = plan(estados)
    assert all("E-C2" not in equipos_usados(a) for a in r.alternativas)
    estados["E-C2"] = EstadoEquipo("DESCONOCIDO", 0.99)  # aunque su probabilidad sea alta
    assert all("E-C2" not in equipos_usados(a) for a in plan(estados).alternativas)


@pytest.mark.parametrize("estado", ["FALLA_CONFIRMADA", "MANTENIMIENTO", "DESCONOCIDO"])
def test_estados_bloqueantes_d20(estado):
    r = plan(estados_ok(E_C2=EstadoEquipo(estado, 0.5, AHORA)))
    assert all("E-C2" not in equipos_usados(a) for a in r.alternativas)


def test_falla_probable_se_permite_con_advertencia():
    r = plan(estados_ok(E_C1=EstadoEquipo("FALLA_PROBABLE", 0.97, AHORA)))
    con_c1 = [a for a in r.alternativas if "E-C1" in equipos_usados(a)]
    assert con_c1 and any("reporte reciente de falla" in w for w in con_c1[0].advertencias)


def test_adulto_mayor_puede_usar_escaleras():
    r = plan(estados_ok(E_C2=falla()), perfil("adulto_mayor"))
    assert "Estación C" in r.alternativas[0].resumen  # baja por la escalera del andén


@pytest.mark.parametrize("perfil_semilla", PERFILES_SEMILLA, ids=lambda p: p["tipo_movilidad"])
@pytest.mark.parametrize("averiado", [None, "E-C2", "E-B2", "E-C1"])
def test_ninguna_ruta_viola_restricciones_duras(perfil_semilla, averiado):
    """Propiedad (regla de seguridad 3): para cualquier perfil y avería, cada arista de cada
    alternativa devuelta es transitable para ese perfil con esos estados."""
    campos = {k: v for k, v in perfil_semilla.items() if k not in ("nombre", "requiere_elevador")}
    perf = Perfil(**campos)
    estados = estados_ok(**({averiado.replace("-", "_"): falla()} if averiado else {}))
    for destino in (DESTINO_PUNTO, DESTINO_EN_Z):
        r = plan(estados, perf, destino)
        g = grafo_para(TOPOLOGIA, perf, estados, AHORA, caminatas(RED, ORIGEN_PUNTO, destino))
        for a in r.alternativas:
            for u, v in itertools.pairwise(a.camino):
                assert exclusion(g[u][v]["arista"], perf, estados) is None


# ------------------------------------------------------------- F2-3 costo y alternativas


def test_con_pk_bajo_gana_la_mas_rapida():
    assert "Estación C" in plan(estados_ok()).alternativas[0].resumen


def test_con_pk_alto_gana_la_mas_segura_aunque_sea_mas_lenta():
    r = plan(estados_ok(E_C2=EstadoEquipo("OPERATIVO", 0.70, AHORA)))
    mejor = r.alternativas[0]
    assert "Estación B" in mejor.resumen
    via_c = next(a for a in r.alternativas if "Estación C" in a.resumen)
    assert mejor.tiempo_total_s > via_c.tiempo_total_s  # más lenta…
    assert mejor.iar > via_c.iar  # …pero más segura


def test_incertidumbre_ordena_salidas_por_antiguedad_del_dato():
    viejo = EstadoEquipo("OPERATIVO", 0.98, AHORA - timedelta(hours=30))
    r = plan(estados_ok(E_C1=viejo))
    resumenes = estaciones_de_salida(r)
    assert resumenes.index("Línea 2 de Estación A a Estación C, salida C2") < resumenes.index(
        "Línea 2 de Estación A a Estación C, salida C1"
    )
    c1 = next(a for a in r.alternativas if a.resumen.endswith("salida C1"))
    assert any("30 h" in w for w in c1.advertencias)


def test_alternativas_distintas_y_maximo_tres():
    r = plan(estados_ok())
    assert 1 <= len(r.alternativas) <= 3
    assert len(set(estaciones_de_salida(r))) == len(r.alternativas)


def test_max_transbordos():
    r = plan(estados_ok(), perfil("adulto_mayor", max_transbordos=0), DESTINO_EN_Z)
    assert not r.alternativas  # Z sólo se alcanza con transbordo en B
    r = plan(estados_ok(), perfil("adulto_mayor", max_transbordos=1), DESTINO_EN_Z)
    assert r.alternativas[0].transbordos == 1


# ------------------------------------------------------------- F2-4 IAR, críticos, plan B


def test_iar_cuenta_cada_equipo_una_vez():
    r = plan(estados_ok(prob=0.9))
    mejor = r.alternativas[0]
    # E-A1 se usa en dos conexiones (calle→vestíbulo y vestíbulo→andén) pero cuenta una vez.
    usos_e_a1 = sum(1 for p in mejor.pasos if p.equipo == "E-A1")
    assert usos_e_a1 == 2
    assert mejor.iar == pytest.approx(100 * 0.9 ** len(mejor.equipos), abs=0.1)


@pytest.mark.parametrize(
    ("iar", "cat"), [(95, "alta"), (90, "alta"), (75, "media"), (69.9, "baja")]
)
def test_categoria_iar(iar, cat):
    assert categoria_iar(iar) == cat


def test_toda_ruta_muestra_iar_criticos_verificacion_y_plan_b():
    """Regla de seguridad 4."""
    for a in plan(estados_ok()).alternativas:
        assert 0 <= a.iar <= 100
        assert a.equipos and all(e.actualizado_en is not None for e in a.equipos)
        assert {b.equipo for b in a.planes_b} == equipos_usados(a)
        assert a.explicacion


def test_plan_b_propone_la_otra_salida():
    mejor = plan(estados_ok()).alternativas[0]
    plan_b = next(b for b in mejor.planes_b if b.equipo == "E-C1")
    assert "salida C2" in plan_b.descripcion


def test_plan_b_sin_alternativa_lo_dice():
    mejor = plan(estados_ok()).alternativas[0]
    plan_b = next(b for b in mejor.planes_b if b.equipo == "E-A1")
    assert "no hay alternativa accesible" in plan_b.descripcion


def test_ruta_descartada_con_motivo_y_explicacion():
    r = plan(estados_ok(E_C2=falla()))
    (d,) = r.descartadas
    assert "Estación C" in d.resumen and "falla confirmada" in d.motivo
    assert "Evita la ruta" in r.alternativas[0].explicacion


# ------------------------------------------------------------- F2-6 sin ruta segura


def test_sin_ruta_por_barrera_fisica():
    r = plan(estados_ok(), destino=DESTINO_EN_Z)
    assert not r.hay_ruta_segura and not r.alternativas
    assert r.aviso == "No encontramos una ruta segura para tu perfil."
    assert any("Estación Z" in o.descripcion and "escalones" in o.descripcion for o in r.obstaculos)
    assert r.sugerencias


def test_sin_ruta_por_estado_de_equipos():
    # Destino sólo alcanzable por C (lejos de B) y el elevador del andén de C en falla.
    cerca_de_c = Punto(19.3205, -99.10)
    r = plan(estados_ok(E_C2=falla()), destino=cerca_de_c)
    assert not r.hay_ruta_segura
    assert any("falla confirmada" in o.descripcion for o in r.obstaculos)
    assert any("reporta" in s for s in r.sugerencias)


def test_iar_bajo_no_se_presenta_como_ruta_segura():
    """Regla de seguridad 5: con IAR < 70 se avisa explícitamente."""
    r = plan(estados_ok(prob=0.80))  # 3 equipos × 0.8 -> IAR ≈ 51
    assert not r.hay_ruta_segura
    assert r.alternativas and r.alternativas[0].iar < 70
    assert "riesgo alto" in r.aviso
    assert r.alternativas[0].advertencias[0].startswith("Riesgo alto")


def test_origen_y_destino_virtuales_existen():
    g = grafo_para(TOPOLOGIA, perfil(), estados_ok(), AHORA, ())
    assert ORIGEN in g and DESTINO in g


def test_trazo_pasa_por_las_estaciones_intermedias():
    """El trazo del mapa sigue la línea (A -> B -> C), no una recta de A a C."""
    mejor = plan(estados_ok()).alternativas[0]
    assert "Estación C" in mejor.resumen
    lat_b = RED.niveles["B/AND-2-C"].lat
    assert any(abs(lat - lat_b) < 1e-9 for lat, _ in mejor.puntos)


def test_advertencia_conserva_mayusculas_de_la_referencia():
    viejo = EstadoEquipo("OPERATIVO", 0.98, AHORA - timedelta(hours=30))
    c1 = next(a for a in plan(estados_ok(E_C1=viejo)).alternativas if a.resumen.endswith("C1"))
    assert any(w.startswith("El elevador salida C1 de Estación C") for w in c1.advertencias)
