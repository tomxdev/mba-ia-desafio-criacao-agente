"""Apartamento do morador autenticado, lido da sessão (Garantia 2).

O apartamento é gravado no state uma única vez, na criação da sessão
(`POST /sessoes`). Nenhuma tool recebe o apartamento como parâmetro e nenhuma
tool escreve esta chave: o modelo não tem como escolher outro apartamento,
não importa o que o morador escreva na conversa.
"""

from google.adk.tools import ToolContext

from aurora import dominio

CHAVE_APARTAMENTO = "apartamento"

ERRO_SEM_APARTAMENTO = {
    "status": "erro",
    "mensagem": "Sessão sem apartamento válido. Não é possível acessar reservas ou visitantes.",
}


def apartamento_da_sessao(tool_context: ToolContext) -> str | None:
    """Devolve o apartamento da sessão, ou None se ausente ou inválido."""
    apartamento = tool_context.state.get(CHAVE_APARTAMENTO)
    if isinstance(apartamento, str) and apartamento in dominio.apartamentos():
        return apartamento
    return None
