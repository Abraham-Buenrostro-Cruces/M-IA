"""Motor y sesiones de SQLAlchemy."""

from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

from app.config import obtener_configuracion


def url_bd() -> str:
    url = obtener_configuracion().bd_url
    if not url:
        raise RuntimeError("Falta RA_BD_URL (ver .env.example).")
    return url


@lru_cache
def obtener_motor() -> Engine:
    # pool_pre_ping: Cloud SQL y Docker cierran conexiones inactivas;
    # así no falla la primera consulta tras un rato sin uso.
    return create_engine(url_bd(), pool_pre_ping=True, pool_size=5, max_overflow=5)


def fabrica_sesiones() -> sessionmaker:
    return sessionmaker(bind=obtener_motor(), expire_on_commit=False)
