"""API HTTP do assistente (FastAPI)."""

import uvicorn
from fastapi import FastAPI

from aurora import config

app = FastAPI(title="Residencial Aurora")


def main() -> None:
    """Comando `aurora-api`: sobe a API em http://localhost:8000."""
    uvicorn.run(app, host=config.HOST, port=config.PORTA)
