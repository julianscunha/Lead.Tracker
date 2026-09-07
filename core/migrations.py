"""Runner fino sobre o Alembic — mesmo padrão do Tech.Forge Core
(.techforge-dev/core/backend/app/db/migrations.py). Só entra em jogo pra
mudança de schema que `ALTER TABLE ADD COLUMN` não resolve (renomear/
remover coluna, mudar tipo) — adicionar coluna continua automático via
`core/db.py::_add_missing_columns`, sem precisar de arquivo de migração
nenhum (ver `alembic/versions/README.md`)."""
from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

_ALEMBIC_DIR = Path(__file__).resolve().parent.parent / "alembic"
_ALEMBIC_INI = _ALEMBIC_DIR.parent / "alembic.ini"


def _config(database_url: str) -> Config:
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def upgrade_head(database_url: str) -> None:
    command.upgrade(_config(database_url), "head")
