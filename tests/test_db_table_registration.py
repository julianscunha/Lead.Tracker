"""
regressão: init_db() precisa criar tabela mesmo quando o chamador
só importa core.db (nunca core.db_models/core.repository diretamente).

Bug real: backend/main.py só importava core.db, nunca core.db_models — as
classes ORM não se registravam em Base.metadata, create_all() rodava vazio,
nenhuma tabela era criada em produção (só não aparecia nos outros testes
porque eles importam core.repository, que importa core.db_models, e isso
"vazava" o registro pra dentro do mesmo processo de teste).

Roda em subprocesso isolado de propósito — sys.modules limpo é a única forma
de reproduzir o bug de verdade.
"""
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent

_SCRIPT = """
import asyncio, sqlite3, sys, tempfile
sys.path.insert(0, r"{repo_root}")
from pathlib import Path
from core.db import create_engine, init_db  # NUNCA importa core.db_models/core.repository

async def run():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "regression.db"
        engine = create_engine(db_path)
        await init_db(engine)
        conn = sqlite3.connect(db_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        conn.close()
        await engine.dispose()
        print(len(tables))

asyncio.run(run())
"""


def test_init_db_creates_tables_even_without_explicit_db_models_import():
    script = _SCRIPT.format(repo_root=str(_REPO_ROOT))
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    table_count = int(result.stdout.strip())
    assert table_count == 7, f"esperava 7 tabelas, criou {table_count} — regressão do bug de metadata vazio"


if __name__ == "__main__":
    test_init_db_creates_tables_even_without_explicit_db_models_import()
    print("OK — regressão de registro de tabela não voltou")
