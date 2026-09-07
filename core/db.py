"""
Persistência.

SQLite via SQLAlchemy async (aiosqlite) — mesmo padrão do Tech.Forge Core.
`sdk.database` do SDK ainda é só um mock in-memory ("Phase 3"), por isso o
módulo rola a própria camada de persistência em vez de depender dele.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.dialects import sqlite
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

_logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def create_engine(db_path: Path) -> AsyncEngine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_async_engine(f"sqlite+aiosqlite:///{db_path}")


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """Cria as tabelas se não existirem e adiciona colunas novas às que já
    existem. Sem Alembic aqui — schema simples, local-first; migração formal
    só se/quando o schema evoluir de um jeito que ALTER TABLE ADD COLUMN não
    resolva (renomear/remover coluna, mudar tipo).

    Import tardio e aparentemente não-usado é proposital: as classes ORM só
    se registram em Base.metadata quando o módulo que as define é importado.
    Sem isso, create_all roda contra metadata vazio e não cria tabela nenhuma
    — sem erro, sem aviso (bug real encontrado na backend/main.py
    nunca importava core.db_models, então nenhuma tabela era criada em produção)."""
    import core.db_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


def _add_missing_columns(sync_conn: Connection) -> None:
    """Evolução leve de schema — mesmo espírito de `sync_env` (`.env` vs
    `.env-model` do config.py): adiciona só a coluna que falta numa tabela
    que JÁ existe, nunca remove/renomeia/sobrescreve dado existente.
    `create_all` (chamado antes desta função) só cria tabela inteira nova —
    uma coluna nova adicionada a um model cuja tabela já existia numa
    instalação anterior nunca aparecia sozinha (bug real: `Company.deal_size_hint`,
    Fase F, encontrado ao verificar o módulo 7 da Fase G ao vivo — qualquer
    instalação que já tinha passado da Fase F antes desta função existir
    quebrava com "no such column" no primeiro SELECT).

    Coluna nullable (ou com server_default) é adicionada direto. Coluna NOT
    NULL sem server_default tenta traduzir o default Python-side (`default=`
    do mapped_column, ex. `default=False`/`default=list`) num literal SQL
    pra preencher as linhas já existentes — achado da revisão de código: a
    maioria das colunas NOT NULL deste schema usa só default Python-side
    (nunca `server_default`), então "pular sempre que não é nullable" teria
    reproduzido o mesmo bug que esta função existe pra fechar, só que mais
    silencioso (quebra numa query bem mais tarde, não no startup). Só quando
    não dá pra derivar um literal com segurança (ex. `type`/`status`
    obrigatório sem default nenhum) é que pula com aviso em vez de arriscar
    um valor errado."""
    inspector = inspect(sync_conn)
    existing_tables = set(inspector.get_table_names())
    dialect = sqlite.dialect()
    for table in Base.metadata.tables.values():
        if table.name not in existing_tables:
            continue  # tabela nova — create_all já cuidou dela nesta mesma chamada
        existing_columns = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_columns:
                continue
            column_type = column.type.compile(dialect=dialect)
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}'
            if not column.nullable and column.server_default is None:
                literal = _server_default_literal(column)
                if literal is None:
                    _logger.warning(
                        "init_db: coluna '%s.%s' está faltando, é NOT NULL e não tem "
                        "default derivável — pulei a migração leve (precisa de migração manual).",
                        table.name, column.name,
                    )
                    continue
                ddl += f" NOT NULL DEFAULT {literal}"
            sync_conn.execute(text(ddl))


def _server_default_literal(column) -> str | None:
    """Traduz um default Python-side (`default=` do mapped_column) num
    literal SQL seguro pro `ALTER TABLE ... DEFAULT`. Só cobre as formas
    realmente usadas neste schema — bool escalar (`default=False`) e
    factory zero-arg de lista/dict (`default=list`) — qualquer outra forma
    devolve `None` (chamador pula com aviso) em vez de arriscar um literal
    que não reflita o default real."""
    default = column.default
    if default is None:
        return None
    if default.is_scalar and isinstance(default.arg, bool):
        return "1" if default.arg else "0"
    if default.is_callable:
        try:
            value = default.arg(None)
        except Exception:
            return None
        if isinstance(value, (list, dict)):
            return "'" + json.dumps(value).replace("'", "''") + "'"
    return None
