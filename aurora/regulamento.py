"""Regulamento interno dividido por capítulo (Garantia 4).

O capítulo é a unidade de assunto: nenhuma função deste módulo devolve o
regulamento inteiro, só o índice (número e tema) ou um capítulo por vez.
"""

import re
from dataclasses import dataclass
from functools import cache

from aurora import config

_CABECALHO = re.compile(r"^## Capítulo ([IVXLC]+): (.+)$", re.MULTILINE)
_ROMANOS = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


@dataclass(frozen=True)
class Capitulo:
    romano: str
    numero: int
    tema: str
    texto: str


def _romano_para_int(romano: str) -> int:
    total = 0
    for atual, seguinte in zip(romano, romano[1:] + " "):
        valor = _ROMANOS[atual]
        total += -valor if seguinte in _ROMANOS and _ROMANOS[seguinte] > valor else valor
    return total


@cache
def capitulos() -> tuple[Capitulo, ...]:
    conteudo = (config.DADOS / "regulamento.md").read_text(encoding="utf-8")
    conteudo = conteudo.replace("\r\n", "\n")
    cabecalhos = list(_CABECALHO.finditer(conteudo))
    resultado = []
    for i, cabecalho in enumerate(cabecalhos):
        fim = cabecalhos[i + 1].start() if i + 1 < len(cabecalhos) else len(conteudo)
        romano, tema = cabecalho.group(1), cabecalho.group(2).strip()
        resultado.append(
            Capitulo(romano, _romano_para_int(romano), tema, conteudo[cabecalho.start() : fim].strip())
        )
    return tuple(resultado)


def buscar_capitulo(referencia: str) -> Capitulo | None:
    """Encontra um capítulo por número romano ("IV") ou arábico ("4")."""
    chave = re.sub(r"(?i)^\s*cap[ií]tulo\s+", "", referencia or "").strip().upper()
    for capitulo in capitulos():
        if chave in (capitulo.romano, str(capitulo.numero)):
            return capitulo
    return None
