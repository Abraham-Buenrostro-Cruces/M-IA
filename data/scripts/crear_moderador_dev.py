"""Crea (o reutiliza) el moderador de DESARROLLO e imprime su token (D-23).

Sólo para RA_MODO=local: en la nube los roles los asigna Identity Platform (Fase 6).

Uso (desde la raíz del repositorio):
    backend/.venv/Scripts/python data/scripts/crear_moderador_dev.py
Pega el token en la PWA (pantalla Moderación) o úsalo como "Authorization: Bearer <token>".
"""

from sqlalchemy import select

from app.bd.modelos import Usuario
from app.bd.sesion import fabrica_sesiones
from app.modulos.usuarios.identidad import emitir_token

UID = "dev:moderador"


def main() -> None:
    with fabrica_sesiones().begin() as s:
        mod = s.scalar(select(Usuario).where(Usuario.uid_identidad == UID))
        if mod is None:
            mod = Usuario(uid_identidad=UID, alias="Moderador de desarrollo", rol="moderador")
            s.add(mod)
            s.flush()
        token = emitir_token(mod.id_usuario, mod.rol)
    print(token)


if __name__ == "__main__":
    main()
