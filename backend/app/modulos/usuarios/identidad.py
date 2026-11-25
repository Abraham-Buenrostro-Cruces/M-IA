"""Identidad local (D-23): usuario anónimo por dispositivo con token JWT firmado.

En la Fase 6 se sustituye por Identity Platform; los endpoints sólo dependen de
``usuario_actual`` y ``moderador_actual``.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select

from app.bd.modelos import Usuario
from app.config import obtener_configuracion
from app.workers.registro import obtener_sesion

VIGENCIA_TOKEN = timedelta(days=365)
PROPOSITO = "identidad"


def _secreto() -> str:
    secreto = obtener_configuracion().jwt_secreto
    if not secreto:
        raise HTTPException(503, "Falta RA_JWT_SECRETO en la configuración del servidor.")
    return secreto


def emitir_token(id_usuario: uuid.UUID, rol: str) -> str:
    ahora = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(id_usuario), "rol": rol, "uso": PROPOSITO, "iat": ahora,
         "exp": ahora + VIGENCIA_TOKEN},
        _secreto(), algorithm="HS256",
    )  # fmt: skip


def usuario_actual(
    sesion: Annotated[object, Depends(obtener_sesion)],
    authorization: Annotated[str | None, Header()] = None,
) -> Usuario:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Falta el token de identidad.")
    try:
        datos = jwt.decode(authorization[7:], _secreto(), algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token de identidad inválido o vencido.") from None
    if datos.get("uso") != PROPOSITO:
        raise HTTPException(401, "Token de identidad inválido.")
    usuario = sesion.scalar(select(Usuario).where(Usuario.id_usuario == uuid.UUID(datos["sub"])))
    if usuario is None:
        raise HTTPException(401, "El usuario ya no existe.")
    return usuario


def moderador_actual(usuario: Annotated[Usuario, Depends(usuario_actual)]) -> Usuario:
    # El rol se lee de la base, no del token: retirar el rol surte efecto de inmediato.
    if usuario.rol not in ("moderador", "admin"):
        raise HTTPException(403, "Se requiere rol de moderador.")
    return usuario
