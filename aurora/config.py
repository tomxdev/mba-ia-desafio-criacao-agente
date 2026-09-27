"""Configuração: variáveis do .env e caminhos do projeto."""

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
VAR = RAIZ / "var"

load_dotenv(RAIZ / ".env")

MODELO = os.environ.get("AURORA_MODEL") or "gemini-flash-latest"

BANCO_DOMINIO = VAR / "aurora.db"
BANCO_SESSOES = VAR / "sessoes.db"

HOST = "127.0.0.1"
PORTA = 8000


def url_banco_sessoes() -> str:
    """URL SQLAlchemy (async) do banco de sessões do ADK."""
    return f"sqlite+aiosqlite:///{BANCO_SESSOES.as_posix()}"
