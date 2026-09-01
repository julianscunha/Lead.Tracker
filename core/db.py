"""
Persistência.

SQLite via SQLAlchemy async (aiosqlite) — mesmo padrão do Tech.Forge Core.
`sdk.database` do SDK ainda é só um mock in-memory ("Phase 3"), por isso o
módulo rola a própria camada de persistência em vez de depender dele.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def create_engine(db_path: Path) -> AsyncEngine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_async_engine(f"sqlite+aiosqlite:///{db_path}")


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """Cria as tabelas se não existirem. Sem Alembic aqui — schema simples,
    local-first; migração formal só se/quando o schema evoluir.

    Import tardio e aparentemente não-usado é proposital: as classes ORM só
    se registram em Base.metadata quando o módulo que as define é importado.
    Sem isso, create_all roda contra metadata vazio e não cria tabela nenhuma
    — sem erro, sem aviso (bug real encontrado na backend/main.py
    nunca importava core.db_models, então nenhuma tabela era criada em produção)."""
    import core.db_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
