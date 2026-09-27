"""Dados fixos do condomínio lidos de `dados/` (somente leitura)."""

import json
from dataclasses import dataclass
from datetime import date
from functools import cache

from aurora import config


@dataclass(frozen=True)
class Area:
    id: str
    nome: str
    taxa: float

    @property
    def gera_cobranca(self) -> bool:
        """Regra de negócio 2: taxa maior que zero gera cobrança."""
        return self.taxa > 0


def _ler_json(nome: str) -> list[dict]:
    with open(config.DADOS / nome, encoding="utf-8") as arquivo:
        return json.load(arquivo)


@cache
def areas() -> dict[str, Area]:
    return {a["id"]: Area(a["id"], a["nome"], float(a["taxa"])) for a in _ler_json("areas.json")}


@cache
def apartamentos() -> frozenset[str]:
    return frozenset(a["numero"] for a in _ler_json("apartamentos.json"))


def reservas_iniciais() -> list[dict]:
    return _ler_json("reservas.json")


def visitantes_iniciais() -> list[dict]:
    return _ler_json("visitantes.json")


def data_valida(texto: str) -> bool:
    """Aceita somente datas reais no formato AAAA-MM-DD."""
    try:
        return date.fromisoformat(texto).isoformat() == texto
    except (TypeError, ValueError):
        return False
