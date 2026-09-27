"""Comando de restauração dos dados iniciais.

Recria o banco de reservas e visitantes a partir de `dados/` (que nunca é
alterado) e apaga o banco de sessões, para que nenhuma confirmação pendente de
uma sessão antiga possa gravar por cima do estado restaurado.
"""

from pathlib import Path

from aurora import banco, config, dominio

_SUFIXOS_SQLITE = ("", "-wal", "-shm", "-journal")


def _apagar_banco(caminho: Path) -> None:
    for sufixo in _SUFIXOS_SQLITE:
        arquivo = caminho.with_name(caminho.name + sufixo)
        try:
            arquivo.unlink(missing_ok=True)
        except PermissionError:
            raise SystemExit(
                f"Não foi possível apagar {arquivo}: pare a API (Ctrl+C) e rode de novo."
            ) from None


def restaurar() -> None:
    _apagar_banco(config.BANCO_DOMINIO)
    _apagar_banco(config.BANCO_SESSOES)
    banco.criar_schema()
    with banco.conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany(
            "INSERT INTO reservas (codigo, apartamento, area, data) VALUES (?, ?, ?, ?)",
            [
                (r["codigo"], r["apartamento"], r["area"], r["data"])
                for r in dominio.reservas_iniciais()
            ],
        )
        conn.executemany(
            "INSERT INTO visitantes (apartamento, nome, data) VALUES (?, ?, ?)",
            [(v["apartamento"], v["nome"], v["data"]) for v in dominio.visitantes_iniciais()],
        )
        conn.execute("COMMIT")


def main() -> None:
    """Comando `aurora-restaurar`: volta reservas e visitantes ao estado de `dados/`."""
    restaurar()
    print(
        f"Dados restaurados: {len(dominio.reservas_iniciais())} reservas e "
        f"{len(dominio.visitantes_iniciais())} visitantes; sessões apagadas."
    )
