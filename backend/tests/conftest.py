"""Fixtures compartidas.

Las pruebas marcadas ``@pytest.mark.bd`` usan una base aparte,
``<RA_BD_URL>_pruebas``, que se crea si no existe y se migra con Alembic a ``head``.
Si PostGIS no está disponible se **omiten** con un aviso (no fallan): así
``pytest`` sigue funcionando sin Docker para las pruebas puras.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import obtener_configuracion

RAIZ_BACKEND = Path(__file__).resolve().parents[1]


def _url_pruebas():
    url = obtener_configuracion().bd_url
    if not url:
        return None
    base = make_url(url)
    return base.set(database=f"{base.database}_pruebas")


def config_alembic(url) -> Config:
    cfg = Config(str(RAIZ_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_BACKEND / "alembic"))
    cfg.attributes["url"] = url.render_as_string(hide_password=False)
    cfg.attributes["configurar_logs"] = False
    return cfg


@pytest.fixture(scope="session")
def url_bd_pruebas():
    url = _url_pruebas()
    if url is None:
        pytest.skip("RA_BD_URL no está definida")
    # connect_timeout: en Windows, conectar a un puerto cerrado puede tardar ~20 s por intento.
    admin = create_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": 3},
    )
    try:
        with admin.connect() as c:
            existe = c.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}
            ).scalar()
            if not existe:
                c.execute(text(f'CREATE DATABASE "{url.database}"'))
    except OperationalError:
        pytest.skip("PostGIS no está disponible (¿docker compose up -d?)")
    finally:
        admin.dispose()
    command.upgrade(config_alembic(url), "head")
    return url


@pytest.fixture
def sesion_bd(url_bd_pruebas):
    """Sesión en una transacción que se revierte al terminar: cada prueba ve la base limpia."""
    motor = create_engine(url_bd_pruebas)
    with motor.connect() as conexion:
        transaccion = conexion.begin()
        sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")
        try:
            yield sesion
        finally:
            sesion.close()
            transaccion.rollback()
    motor.dispose()
