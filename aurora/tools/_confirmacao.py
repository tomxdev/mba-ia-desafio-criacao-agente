"""Confirmação de ações com cobrança ou que liberam acesso (Garantia 1).

A decisão de pedir confirmação é do código da tool, não do modelo, e a resposta
só chega pelo sistema: `tool_context.tool_confirmation` é preenchido pelo ADK
apenas quando o cliente envia a function response de `adk_request_confirmation`
(rota `POST /sessoes/{id}/confirmacoes`). Texto do morador como "já estou
confirmando" é só uma mensagem e não altera esse campo.
"""

from typing import Any

from google.adk.tools import ToolContext


def exigir_confirmacao(
    tool_context: ToolContext, hint: str, detalhes: dict[str, Any]
) -> dict[str, Any] | None:
    """Garante que a ação só siga depois de aprovada pela rota de confirmações.

    Devolve o resultado que a tool deve retornar enquanto a ação não pode
    executar (pedido de confirmação registrado, ou negado). Devolve None
    somente quando o morador aprovou pela rota de confirmações.
    """
    confirmacao = tool_context.tool_confirmation
    if confirmacao is None:
        tool_context.request_confirmation(hint=hint, payload=detalhes)
        return {
            "status": "aguardando_confirmacao",
            "mensagem": "A ação ficou pendente de confirmação do morador pelo aplicativo.",
            "detalhes": detalhes,
        }
    if not confirmacao.confirmed:
        return {
            "status": "negada",
            "mensagem": "O morador não confirmou a ação. Nada foi alterado.",
            "detalhes": detalhes,
        }
    return None
