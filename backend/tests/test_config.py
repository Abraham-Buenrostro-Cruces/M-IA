import pytest
from pydantic import ValidationError

from app.config import Configuracion


def test_modo_por_defecto_es_local(monkeypatch):
    monkeypatch.delenv("RA_MODO", raising=False)
    assert Configuracion(_env_file=None).modo == "local"


def test_modo_se_lee_de_variable_de_entorno(monkeypatch):
    monkeypatch.setenv("RA_MODO", "gcp")
    assert Configuracion(_env_file=None).modo == "gcp"


@pytest.mark.parametrize("valor", ["GCP", "nube", "", "local "])
def test_modo_invalido_detiene_el_arranque(monkeypatch, valor):
    # Un modo mal escrito no debe degradarse en silencio a "local" (ver app/config.py).
    monkeypatch.setenv("RA_MODO", valor)
    with pytest.raises(ValidationError):
        Configuracion(_env_file=None)
