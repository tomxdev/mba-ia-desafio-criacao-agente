"""API HTTP do assistente (FastAPI)."""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from aurora import banco, config


@asynccontextmanager
async def lifespan(_: FastAPI):
    banco.criar_schema()
    yield


app = FastAPI(title="Residencial Aurora", lifespan=lifespan)


class Reserva(BaseModel):
    codigo: str
    area: str
    data: str


class Visitante(BaseModel):
    nome: str
    data: str


# --- Rotas de verificação: leem o banco direto, sem passar pelo modelo -------


@app.get("/apartamentos/{numero}/reservas", response_model=list[Reserva])
def reservas_do_apartamento(numero: str) -> list[dict]:
    return banco.listar_reservas(numero)


@app.get("/apartamentos/{numero}/visitantes", response_model=list[Visitante])
def visitantes_do_apartamento(numero: str) -> list[dict]:
    return banco.listar_visitantes(numero)


def main() -> None:
    """Comando `aurora-api`: sobe a API em http://localhost:8000."""
    uvicorn.run(app, host=config.HOST, port=config.PORTA)
