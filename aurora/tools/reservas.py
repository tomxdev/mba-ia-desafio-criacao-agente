"""Tools de reservas das áreas comuns.

Nenhuma tool aceita apartamento como parâmetro: o apartamento vem sempre da
sessão. Os retornos só trazem reservas do próprio apartamento; sobre a agenda
dos outros, o máximo que chega à conversa é "livre" ou "ocupada".
"""

from typing import Any, Optional

from google.adk.tools import ToolContext

from aurora import banco, dominio
from aurora.tools._confirmacao import exigir_confirmacao
from aurora.tools._sessao import ERRO_SEM_APARTAMENTO, apartamento_da_sessao


def _validar_area_e_data(area: str, data: str) -> dict[str, Any] | None:
    if area not in dominio.areas():
        return {
            "status": "erro",
            "mensagem": f"Área desconhecida: {area!r}. Use listar_areas para ver os ids válidos.",
        }
    if not dominio.data_valida(data):
        return {"status": "erro", "mensagem": "Data inválida. Use o formato AAAA-MM-DD."}
    return None


def listar_areas() -> dict[str, Any]:
    """Lista as áreas comuns que podem ser reservadas, com id, nome e taxa em reais.

    Taxa 0 significa área sem cobrança.
    """
    return {
        "areas": [
            {"id": a.id, "nome": a.nome, "taxa": a.taxa, "gera_cobranca": a.gera_cobranca}
            for a in dominio.areas().values()
        ]
    }


def listar_minhas_reservas(tool_context: ToolContext) -> dict[str, Any]:
    """Lista as reservas ativas do apartamento do morador."""
    apartamento = apartamento_da_sessao(tool_context)
    if apartamento is None:
        return ERRO_SEM_APARTAMENTO
    return {"reservas": banco.listar_reservas(apartamento)}


def verificar_disponibilidade(area: str, data: str, tool_context: ToolContext) -> dict[str, Any]:
    """Informa se uma área comum está livre ou ocupada numa data.

    Args:
        area: id da área (ex.: salao-de-festas, churrasqueira, quadra).
        data: data no formato AAAA-MM-DD.
    """
    if apartamento_da_sessao(tool_context) is None:
        return ERRO_SEM_APARTAMENTO
    if erro := _validar_area_e_data(area, data):
        return erro
    situacao = "ocupada" if banco.area_ocupada(area, data) else "livre"
    return {"area": area, "data": data, "situacao": situacao}


def reservar_area(area: str, data: str, tool_context: ToolContext) -> dict[str, Any]:
    """Reserva uma área comum para o apartamento do morador numa data.

    Áreas com taxa geram cobrança e ficam pendentes até o morador confirmar
    pelo aplicativo; áreas sem taxa são reservadas na hora.

    Args:
        area: id da área (ex.: salao-de-festas, churrasqueira, quadra).
        data: data no formato AAAA-MM-DD.
    """
    apartamento = apartamento_da_sessao(tool_context)
    if apartamento is None:
        return ERRO_SEM_APARTAMENTO
    if erro := _validar_area_e_data(area, data):
        return erro
    ocupada = {
        "status": "ocupada",
        "mensagem": "A área já está reservada nessa data. Escolha outra data.",
        "area": area,
        "data": data,
    }
    if tool_context.tool_confirmation is None and banco.area_ocupada(area, data):
        return ocupada  # não vale a pena pedir confirmação para data já ocupada

    obj_area = dominio.areas()[area]
    if obj_area.gera_cobranca:  # regra de negócio 2: decidida pela taxa, no código
        pendente = exigir_confirmacao(
            tool_context,
            hint=f"Reservar {obj_area.nome} em {data} gera cobrança de R$ {obj_area.taxa:.2f}.",
            detalhes={"area": area, "data": data, "taxa": obj_area.taxa},
        )
        if pendente is not None:
            return pendente

    # A exclusividade é decidida pelo banco no instante da gravação (Garantia 5).
    resultado = banco.criar_reserva(
        apartamento, area, data, operacao_id=tool_context.function_call_id
    )
    if resultado.status == "ocupada":
        return ocupada
    return {"status": "reservada", "codigo": resultado.codigo, "area": area, "data": data}


def cancelar_reserva(
    tool_context: ToolContext,
    codigo: Optional[str] = None,
    area: Optional[str] = None,
    data: Optional[str] = None,
) -> dict[str, Any]:
    """Cancela uma reserva do próprio apartamento, sem pedir confirmação.

    Informe o código da reserva, ou a área e/ou a data. Só reservas do
    apartamento do morador podem ser canceladas.

    Args:
        codigo: código da reserva (ex.: RSV-1234), se o morador souber.
        area: id da área (ex.: salao-de-festas, churrasqueira, quadra).
        data: data da reserva no formato AAAA-MM-DD.
    """
    apartamento = apartamento_da_sessao(tool_context)
    if apartamento is None:
        return ERRO_SEM_APARTAMENTO
    if codigo is None and area is None and data is None:
        return {"status": "erro", "mensagem": "Informe o código, a área ou a data da reserva."}

    candidatas = [
        r
        for r in banco.listar_reservas(apartamento)
        if (codigo is None or r["codigo"] == codigo)
        and (area is None or r["area"] == area)
        and (data is None or r["data"] == data)
    ]
    if not candidatas:
        return {
            "status": "nao_encontrada",
            "mensagem": "Não há reserva ativa do seu apartamento com esses dados. Nada foi alterado.",
        }
    if len(candidatas) > 1:
        return {
            "status": "ambigua",
            "mensagem": "Mais de uma reserva sua corresponde ao pedido. Pergunte qual cancelar.",
            "reservas": candidatas,
        }
    canceladas = banco.cancelar_reservas(apartamento, codigo=candidatas[0]["codigo"])
    if not canceladas:
        return {"status": "nao_encontrada", "mensagem": "A reserva já não está ativa."}
    return {"status": "cancelada", "reserva": canceladas[0]}
