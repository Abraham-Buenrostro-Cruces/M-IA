"""sistemas suburbano e interurbano (D-25)

Amplía ``estacion.sistema`` y ``ruta_transporte.sistema`` (CHECK y longitud: 12 -> 20
caracteres, "TREN_INTERURBANO" tiene 16) con el Tren Suburbano y el Tren El Insurgente
(Interurbano México–Toluca).

Revision ID: 29efe3a4f5fd
Revises: 0a48379d3057
Create Date: 2026-11-25 11:46:32.136428

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "29efe3a4f5fd"
down_revision: str | Sequence[str] | None = "0a48379d3057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ANTES = ("METRO", "METROBUS", "TREN_LIGERO")
DESPUES = (*ANTES, "TREN_SUBURBANO", "TREN_INTERURBANO")
TABLAS = ("estacion", "ruta_transporte")


def _cambiar(sistemas: tuple[str, ...], largo: int) -> None:
    lista = ", ".join(f"'{s}'" for s in sistemas)
    for tabla in TABLAS:
        nombre = op.f(f"ck_{tabla}_sistema")  # op.f: el nombre ya sigue la convención
        op.drop_constraint(nombre, tabla, type_="check")
        op.alter_column(tabla, "sistema", type_=sa.String(largo), existing_nullable=False)
        op.create_check_constraint(nombre, tabla, f"sistema IN ({lista})")


def upgrade() -> None:
    _cambiar(DESPUES, 20)


def downgrade() -> None:
    # Falla si ya hay estaciones de los sistemas nuevos: hay que borrarlas antes.
    _cambiar(ANTES, 12)
