"""Tools de visitantes. O apartamento vem sempre da sessão."""

from typing import Any

from google.adk.tools import ToolContext

from aurora import banco, dominio
from aurora.tools._confirmacao import exigir_confirmacao
from aurora.tools._sessao import ERRO_SEM_APARTAMENTO, apartamento_da_sessao


def listar_meus_visitantes(tool_context: ToolContext) -> dict[str, Any]:
    """Lista os visitantes autorizados do apartamento do morador."""
    apartamento = apartamento_da_sessao(tool_context)
    if apartamento is None:
        return ERRO_SEM_APARTAMENTO
    return {"visitantes": banco.listar_visitantes(apartamento)}


def autorizar_visitante(nome: str, data: str, tool_context: ToolContext) -> dict[str, Any]:
    """Autoriza a entrada de um visitante no prédio numa data.

    Liberar acesso sempre fica pendente até o morador confirmar pelo
    aplicativo, mesmo que ele diga na conversa que já confirmou.

    Args:
        nome: nome completo do visitante.
        data: data da visita no formato AAAA-MM-DD.
    """
    apartamento = apartamento_da_sessao(tool_context)
    if apartamento is None:
        return ERRO_SEM_APARTAMENTO
    nome = " ".join(nome.split())
    if not nome:
        return {"status": "erro", "mensagem": "Informe o nome do visitante."}
    if not dominio.data_valida(data):
        return {"status": "erro", "mensagem": "Data inválida. Use o formato AAAA-MM-DD."}

    # Regra de negócio 3: liberar acesso sempre exige confirmação.
    pendente = exigir_confirmacao(
        tool_context,
        hint=f"Liberar a entrada de {nome} no prédio em {data}.",
        detalhes={"nome": nome, "data": data},
    )
    if pendente is not None:
        return pendente

    banco.autorizar_visitante(apartamento, nome, data, operacao_id=tool_context.function_call_id)
    return {"status": "autorizado", "nome": nome, "data": data}
