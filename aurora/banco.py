"""Armazenamento de reservas e visitantes em SQLite.

As regras que não podem depender do modelo moram aqui, no banco:

- exclusividade da reserva (regra 1 / Garantia 5): índice único parcial
  `ux_reserva_ativa` em (area, data) só para reservas ativas. Duas gravações
  simultâneas para a mesma área e data não passam juntas: a segunda recebe
  `IntegrityError` no próprio INSERT, que vira o resultado de negócio "ocupada";
- códigos que nunca se repetem (regra 5): `codigo` é PRIMARY KEY e o
  cancelamento é lógico (`ativa = 0`), então nenhum código volta a ser usado;
- execução única de uma ação confirmada: `operacao_id` UNIQUE guarda o id da
  chamada de tool que gravou; se o ADK reexecutar a mesma chamada, o registro
  existente é devolvido em vez de duplicado.
"""

import secrets
import sqlite3
import string
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Literal

from aurora import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS reservas (
    codigo      TEXT PRIMARY KEY,
    apartamento TEXT NOT NULL,
    area        TEXT NOT NULL,
    data        TEXT NOT NULL,
    ativa       INTEGER NOT NULL DEFAULT 1,
    operacao_id TEXT UNIQUE
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_reserva_ativa
    ON reservas (area, data) WHERE ativa = 1;
CREATE INDEX IF NOT EXISTS ix_reservas_apartamento ON reservas (apartamento);

CREATE TABLE IF NOT EXISTS visitantes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    apartamento TEXT NOT NULL,
    nome        TEXT NOT NULL,
    data        TEXT NOT NULL,
    operacao_id TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS ix_visitantes_apartamento ON visitantes (apartamento);
"""

_ALFABETO_CODIGO = string.ascii_uppercase + string.digits


@dataclass(frozen=True)
class ResultadoReserva:
    status: Literal["criada", "ocupada"]
    codigo: str | None = None


@contextmanager
def conectar() -> Iterator[sqlite3.Connection]:
    """Conexão curta por operação, em modo autocommit (transações explícitas)."""
    config.VAR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.BANCO_DOMINIO, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA journal_mode = WAL")
        yield conn
    finally:
        conn.close()


@contextmanager
def _transacao_escrita(conn: sqlite3.Connection) -> Iterator[None]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def criar_schema() -> None:
    with conectar() as conn:
        conn.executescript(SCHEMA)


def _novo_codigo() -> str:
    return "RSV-" + "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(6))


def _violou(erro: sqlite3.IntegrityError, *colunas: str) -> bool:
    return str(erro) == "UNIQUE constraint failed: " + ", ".join(colunas)


# --- Leitura -----------------------------------------------------------------


def listar_reservas(apartamento: str) -> list[dict]:
    with conectar() as conn:
        linhas = conn.execute(
            "SELECT codigo, area, data FROM reservas"
            " WHERE apartamento = ? AND ativa = 1 ORDER BY data, codigo",
            (apartamento,),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def listar_visitantes(apartamento: str) -> list[dict]:
    with conectar() as conn:
        linhas = conn.execute(
            "SELECT nome, data FROM visitantes WHERE apartamento = ? ORDER BY data, id",
            (apartamento,),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def area_ocupada(area: str, data: str) -> bool:
    """Diz só se a data está ocupada, nunca por quem (Garantia 2)."""
    with conectar() as conn:
        linha = conn.execute(
            "SELECT 1 FROM reservas WHERE area = ? AND data = ? AND ativa = 1",
            (area, data),
        ).fetchone()
    return linha is not None


# --- Escrita -----------------------------------------------------------------


def criar_reserva(
    apartamento: str, area: str, data: str, operacao_id: str | None = None
) -> ResultadoReserva:
    """Grava a reserva; a exclusividade é decidida pelo índice único no INSERT."""
    with conectar() as conn, _transacao_escrita(conn):
        if operacao_id is not None:
            existente = conn.execute(
                "SELECT codigo FROM reservas WHERE operacao_id = ?", (operacao_id,)
            ).fetchone()
            if existente is not None:
                return ResultadoReserva("criada", existente["codigo"])
        while True:
            codigo = _novo_codigo()
            try:
                conn.execute(
                    "INSERT INTO reservas (codigo, apartamento, area, data, operacao_id)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (codigo, apartamento, area, data, operacao_id),
                )
            except sqlite3.IntegrityError as erro:
                if _violou(erro, "reservas.codigo"):
                    continue  # código já emitido (ativo ou cancelado): sorteia outro
                if _violou(erro, "reservas.area", "reservas.data"):
                    return ResultadoReserva("ocupada")
                raise
            return ResultadoReserva("criada", codigo)


def cancelar_reservas(
    apartamento: str,
    *,
    codigo: str | None = None,
    area: str | None = None,
    data: str | None = None,
) -> list[dict]:
    """Cancela reservas ativas do próprio apartamento que casam com os filtros.

    O filtro por apartamento é sempre aplicado: reservas de outro apartamento
    nunca são alteradas nem reveladas. Devolve as reservas canceladas.
    """
    if codigo is None and area is None and data is None:
        return []
    condicoes = ["apartamento = ?", "ativa = 1"]
    parametros: list[str] = [apartamento]
    for coluna, valor in (("codigo", codigo), ("area", area), ("data", data)):
        if valor is not None:
            condicoes.append(f"{coluna} = ?")
            parametros.append(valor)
    onde = " AND ".join(condicoes)
    with conectar() as conn, _transacao_escrita(conn):
        linhas = conn.execute(
            f"SELECT codigo, area, data FROM reservas WHERE {onde}", parametros
        ).fetchall()
        conn.executemany(
            "UPDATE reservas SET ativa = 0 WHERE codigo = ?",
            [(linha["codigo"],) for linha in linhas],
        )
    return [dict(linha) for linha in linhas]


def autorizar_visitante(
    apartamento: str, nome: str, data: str, operacao_id: str | None = None
) -> None:
    with conectar() as conn, _transacao_escrita(conn):
        if operacao_id is not None:
            existente = conn.execute(
                "SELECT 1 FROM visitantes WHERE operacao_id = ?", (operacao_id,)
            ).fetchone()
            if existente is not None:
                return
        conn.execute(
            "INSERT INTO visitantes (apartamento, nome, data, operacao_id) VALUES (?, ?, ?, ?)",
            (apartamento, nome, data, operacao_id),
        )
