"""Tools de consulta ao regulamento: índice de capítulos e um capítulo por vez."""

from typing import Any

from aurora import regulamento


def listar_capitulos() -> dict[str, Any]:
    """Lista os capítulos do regulamento interno, só com número e tema."""
    return {
        "capitulos": [
            {"capitulo": c.romano, "numero": c.numero, "tema": c.tema}
            for c in regulamento.capitulos()
        ]
    }


def consultar_capitulo(capitulo: str) -> dict[str, Any]:
    """Devolve o texto de um único capítulo do regulamento interno.

    Args:
        capitulo: número do capítulo em romano (ex.: "IV") ou arábico (ex.: "4").
    """
    encontrado = regulamento.buscar_capitulo(capitulo)
    if encontrado is None:
        return {
            "status": "erro",
            "mensagem": "Capítulo não encontrado. Use listar_capitulos para ver os capítulos.",
        }
    return {"capitulo": encontrado.romano, "tema": encontrado.tema, "texto": encontrado.texto}
