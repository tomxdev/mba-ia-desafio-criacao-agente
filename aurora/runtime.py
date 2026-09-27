"""Runtime do ADK por trás da API: Runner, sessões persistidas e confirmações.

- Sessões ficam em SQLite (`DatabaseSessionService`), então conversas e
  eventos sobrevivem ao reinício da API (Garantia 3).
- As confirmações pendentes são sempre recalculadas a partir dos eventos
  gravados na sessão: uma chamada `adk_request_confirmation` sem a function
  response de mesmo id ainda está pendente.
- Mensagens e confirmações da mesma sessão são processadas uma de cada vez.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService, Session
from google.genai import types

from aurora import config
from aurora.agent import app
from aurora.tools._sessao import CHAVE_APARTAMENTO

CONFIRMACAO = "adk_request_confirmation"

# As rotas identificam a sessão só pelo id; o apartamento fica no state.
USER_ID = "morador"


@dataclass
class Resultado:
    resposta: str
    confirmacoes_pendentes: list[dict[str, Any]]


class Runtime:
    def __init__(self) -> None:
        config.VAR.mkdir(parents=True, exist_ok=True)
        self.sessoes = DatabaseSessionService(db_url=config.url_banco_sessoes())
        self.runner = Runner(app=app, session_service=self.sessoes)
        self._travas: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def fechar(self) -> None:
        await self.runner.close()

    def trava(self, session_id: str) -> asyncio.Lock:
        return self._travas[session_id]

    async def criar_sessao(self, apartamento: str) -> str:
        """O apartamento é gravado no state aqui, uma única vez (Garantia 2)."""
        sessao = await self.sessoes.create_session(
            app_name=app.name, user_id=USER_ID, state={CHAVE_APARTAMENTO: apartamento}
        )
        return sessao.id

    async def obter_sessao(self, session_id: str) -> Session | None:
        return await self.sessoes.get_session(
            app_name=app.name, user_id=USER_ID, session_id=session_id
        )

    async def enviar_texto(self, session_id: str, texto: str) -> Resultado:
        mensagem = types.Content(role="user", parts=[types.Part(text=texto)])
        return await self._executar(session_id, mensagem)

    async def _executar(self, session_id: str, mensagem: types.Content) -> Resultado:
        textos: list[str] = []
        async for evento in self.runner.run_async(
            user_id=USER_ID, session_id=session_id, new_message=mensagem
        ):
            if evento.author == "user" or evento.partial or not evento.content:
                continue
            for parte in evento.content.parts or []:
                if parte.text and not parte.thought:
                    textos.append(parte.text.strip())
        sessao = await self.obter_sessao(session_id)
        return Resultado(
            resposta="\n\n".join(t for t in textos if t),
            confirmacoes_pendentes=confirmacoes_pendentes(sessao),
        )


def confirmacoes_pendentes(sessao: Session) -> list[dict[str, Any]]:
    """Pedidos de confirmação da sessão que ainda não receberam resposta."""
    pedidos: dict[str, dict[str, Any]] = {}
    respondidos: set[str] = set()
    for evento in sessao.events:
        for chamada in evento.get_function_calls():
            if chamada.name == CONFIRMACAO and chamada.id:
                pedidos[chamada.id] = chamada.args or {}
        for resposta in evento.get_function_responses():
            if resposta.name == CONFIRMACAO and resposta.id:
                respondidos.add(resposta.id)
    pendentes = []
    for id_confirmacao, args in pedidos.items():
        if id_confirmacao in respondidos:
            continue
        original = args.get("originalFunctionCall") or {}
        confirmacao = args.get("toolConfirmation") or {}
        pendentes.append(
            {
                "id": id_confirmacao,
                "acao": original.get("name", ""),
                "detalhes": confirmacao.get("payload") or original.get("args") or {},
            }
        )
    return pendentes


def serializar_eventos(sessao: Session) -> list[dict[str, Any]]:
    return [serializar_evento(evento) for evento in sessao.events]


def serializar_evento(evento: Event) -> dict[str, Any]:
    return evento.model_dump(mode="json", exclude_none=True, by_alias=True)
