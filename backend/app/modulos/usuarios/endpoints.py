"""Identidad local (D-23)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.bd.modelos import Usuario
from app.modulos.usuarios.identidad import emitir_token, usuario_actual
from app.workers.registro import obtener_sesion

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


class TokenSalida(BaseModel):
    token: str
    id_usuario: str
    rol: str


class YoSalida(BaseModel):
    id_usuario: str
    rol: str
    reputacion: float
    reportes_confirmados: int
    reportes_rechazados: int


@router.post("/anonimo", response_model=TokenSalida, status_code=201)
def crear_anonimo(sesion: Annotated[object, Depends(obtener_sesion)]) -> TokenSalida:
    """Crea un usuario anónimo para este dispositivo. No pide ni guarda datos personales."""
    usuario = Usuario(rol="usuario", reputacion=0.5)
    sesion.add(usuario)
    sesion.commit()
    return TokenSalida(
        token=emitir_token(usuario.id_usuario, usuario.rol),
        id_usuario=str(usuario.id_usuario),
        rol=usuario.rol,
    )


@router.get("/yo", response_model=YoSalida)
def yo(usuario: Annotated[Usuario, Depends(usuario_actual)]) -> YoSalida:
    return YoSalida(
        id_usuario=str(usuario.id_usuario),
        rol=usuario.rol,
        reputacion=usuario.reputacion,
        reportes_confirmados=usuario.reportes_confirmados,
        reportes_rechazados=usuario.reportes_rechazados,
    )
