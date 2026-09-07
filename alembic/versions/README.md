# Migrações Alembic

Este diretório fica vazio até que exista uma mudança de schema real que
`ALTER TABLE ADD COLUMN` não resolva — **renomear coluna, remover coluna,
mudar tipo de coluna existente**.

**Adicionar coluna nova NÃO precisa de migração aqui.** `core/db.py`
(`init_db` → `_add_missing_columns`) já cuida disso automaticamente toda vez
que o módulo inicializa: qualquer coluna que exista no model
(`core/db_models.py`) mas não na tabela física é adicionada, com backfill do
default real quando ele existe. Escrever uma migração pra esse caso seria
duplicar o que já roda sozinho.

## Quando escrever uma migração de verdade

Só quando a mudança for uma das que a reconciliação automática não cobre:

```bash
alembic revision -m "descrição da mudança"
```

Escreva `upgrade()` de forma defensiva/idempotente (mesmo padrão do Tech.Forge
Core) — checando se a coluna/tabela já está no estado alvo antes de agir —
porque `create_all()` roda ANTES do Alembic em toda inicialização: uma
instalação nova já nasce com o schema atual completo, então a migração só
precisa fazer alguma coisa em bancos que vêm de ANTES da mudança.

**Nunca mova `_add_missing_columns` (`core/db.py`) pra antes do Alembic no
`init_db`.** A ordem hoje é `create_all` → Alembic → `_add_missing_columns`,
de propósito: se o reconciliador genérico rodasse antes de uma migração de
RENOMEAR coluna, ele veria a coluna nova do rename como "campo novo" (não
tem como saber que é rename) e criaria ela vazia — orfanizando o dado que a
migração devia mover, e fazendo a migração falhar depois com coluna
duplicada, permanentemente (achado real de revisão de código, coberto por
`tests/test_persistence.py::test_init_db_runs_alembic_before_add_missing_columns`).

```python
def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("nome_da_tabela")}
    if "coluna_antiga" not in existing:
        return  # tabela já nasceu sem ela (instalação nova) — nada a fazer
    with op.batch_alter_table("nome_da_tabela") as batch:
        batch.alter_column("coluna_antiga", new_column_name="coluna_nova")
```
