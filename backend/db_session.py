"""
Engine/session factory únicos do módulo — extraído de main.py pra rotas
novas (backend/routes_sync.py) poderem acessar o banco sem criar uma
segunda engine apontando pro mesmo arquivo SQLite.
"""
from __future__ import annotations

from pathlib import Path

from core.db import create_engine, make_session_factory

_MODULE_ROOT = Path(__file__).parent.parent
DB_PATH = _MODULE_ROOT / "data" / "lead_tracker.db"

engine = create_engine(DB_PATH)
session_factory = make_session_factory(engine)
