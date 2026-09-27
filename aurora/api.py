"""API HTTP do assistente (FastAPI)."""

import logging
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from aurora import banco, config, dominio
from aurora.runtime import Resultado, Runtime, serializar_eventos

logger = logging.getLogger("aurora.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    banco.criar_schema()
    app.state.runtime = Runtime()
    yield
    await app.state.runtime.fechar()


app = FastAPI(title="Residencial Aurora", lifespan=lifespan)


def _runtime(request: Request) -> Runtime:
    return request.app.state.runtime


# --- Modelos do contrato -----------------------------------------------------


class NovaSessao(BaseModel):
    apartamento: str


class SessaoCriada(BaseModel):
    session_id: str


class Mensagem(BaseModel):
    texto: str


class ConfirmacaoPendente(BaseModel):
    id: str
    acao: str
    detalhes: dict[str, Any]


class RespostaConversa(BaseModel):
    resposta: str
    confirmacoes_pendentes: list[ConfirmacaoPendente]


class Reserva(BaseModel):
    codigo: str
    area: str
    data: str


class Visitante(BaseModel):
    nome: str
    data: str


# --- Rotas de conversa -------------------------------------------------------


async def _sessao_ou_404(runtime: Runtime, session_id: str):
    sessao = await runtime.obter_sessao(session_id)
    if sessao is None:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    return sessao


def _resposta(resultado: Resultado) -> RespostaConversa:
    return RespostaConversa(
        resposta=resultado.resposta,
        confirmacoes_pendentes=[ConfirmacaoPendente(**c) for c in resultado.confirmacoes_pendentes],
    )


@app.post("/sessoes", status_code=201, response_model=SessaoCriada)
async def criar_sessao(corpo: NovaSessao, request: Request) -> SessaoCriada:
    if corpo.apartamento not in dominio.apartamentos():
        raise HTTPException(status_code=422, detail="Apartamento inexistente.")
    session_id = await _runtime(request).criar_sessao(corpo.apartamento)
    return SessaoCriada(session_id=session_id)


@app.post("/sessoes/{session_id}/mensagens", response_model=RespostaConversa)
async def enviar_mensagem(session_id: str, corpo: Mensagem, request: Request) -> RespostaConversa:
    runtime = _runtime(request)
    async with runtime.trava(session_id):
        await _sessao_ou_404(runtime, session_id)
        try:
            resultado = await runtime.enviar_texto(session_id, corpo.texto)
        except Exception as erro:
            logger.exception("Falha ao processar mensagem da sessão %s", session_id)
            raise HTTPException(
                status_code=503, detail="O assistente está indisponível no momento. Tente novamente."
            ) from erro
    return _resposta(resultado)


@app.get("/sessoes/{session_id}/eventos")
async def listar_eventos(session_id: str, request: Request) -> list[dict[str, Any]]:
    sessao = await _sessao_ou_404(_runtime(request), session_id)
    return serializar_eventos(sessao)


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
