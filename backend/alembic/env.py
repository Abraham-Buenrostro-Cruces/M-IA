"""Entorno de Alembic para api-core.

La URL de conexión sale de RA_BD_URL (``.env`` o variable de entorno), nunca de
alembic.ini, para no versionar credenciales. Las pruebas la sustituyen pasando
``config.attributes["url"]``.

Los ayudantes de GeoAlchemy2 evitan que la autogeneración duplique los índices
espaciales GiST (que PostGIS crea junto con la columna) o que intente borrar las
tablas internas de PostGIS (``spatial_ref_sys``).
"""

from logging.config import fileConfig

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import create_engine, pool

from app.bd.modelos import Base
from app.bd.sesion import url_bd

config = context.config
if config.config_file_name is not None and config.attributes.get("configurar_logs", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    return config.attributes.get("url") or url_bd()


def _incluir_objeto(objeto, nombre, tipo, reflejado, comparado_con) -> bool:
    """Compara sólo las tablas de nuestro modelo.

    La imagen postgis/postgis instala además TIGER (geocodificador de EE. UU.) y
    topology; sin este filtro, la autogeneración propondría borrar sus tablas.
    """
    if tipo == "table" and reflejado and comparado_con is None:
        return False
    return alembic_helpers.include_object(objeto, nombre, tipo, reflejado, comparado_con)


def _opciones() -> dict:
    return {
        "target_metadata": target_metadata,
        "include_object": _incluir_objeto,
        "process_revision_directives": alembic_helpers.writer,
        "render_item": alembic_helpers.render_item,
        "compare_type": True,
    }


def run_migrations_offline() -> None:
    context.configure(url=_url(), literal_binds=True, **_opciones())
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    motor = create_engine(_url(), poolclass=pool.NullPool)
    with motor.connect() as conexion:
        context.configure(connection=conexion, **_opciones())
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
