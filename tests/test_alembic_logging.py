"""Regressão: a migração do startup (alembic/env.py) não pode silenciar loggers da aplicação.

`logging.config.fileConfig` desliga por padrão todo logger já existente
(`disable_existing_loggers=True`). Como `init_db` roda `upgrade_head` no boot, isso apagava os
logs de módulos importados antes (ex.: `ai.business_case_prose`, que registra só motivo e
fonte da prosa, nunca texto de CRM)."""
import asyncio
import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db import create_engine, init_db


def test_init_db_nao_desliga_loggers_ja_existentes():
    logger = logging.getLogger("lead_tracker.regressao_alembic")
    logger.disabled = False

    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            await init_db(create_engine(Path(tmp) / "test.db"))

    asyncio.run(run())

    assert logger.disabled is False
