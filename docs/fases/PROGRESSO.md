# Progresso da implementação

Fonte de verdade sobre em qual fase o desenvolvimento está. Atualizar a cada
fase concluída — se a sessão cair, é este arquivo que diz de onde continuar.

## Status atual

**Fase em andamento: 05 — Providers** (ainda não iniciada)

> Nota: a Fase 04 foi implementada antes das Fases 02/03 por engano, quebrando
> a ordem estrita do CLAUDE.md. Corrigido voltando e implementando 02 e 03
> antes de seguir para 05 — ver `[[feedback_mandatory_skill_invocation]]` na
> memória para o incidente relacionado (skill obrigatória pulada na Fase 04).

## Fases concluídas

| Fase | Descrição | Commit | Data |
|---|---|---|---|
| 04 | Esqueleto do Módulo Tech.Forge — `manifest.yaml`, `backend/main.py` (ModuleContract), `frontend/index.js`, diretórios `core/providers/ai/exports/data/tests/`. Ciclo de vida (install/enable/health_check/disable/uninstall) validado contra o SDK real do Tech.Forge Core (`.techforge-dev/`, não versionado). | `8e52989` | 2026-08-31 |
| 02 | Modelo de Dados — `core/models.py`: `Company`, `SourceRef`, `Vendor`, `Product`, `Service`, `Opportunity` (com `OpportunityStatus`), `Portfolio`. Testes em `tests/test_models.py`. | `0f44e83` | 2026-08-31 |
| 03 | Configuração — `.env-model` versionado, `core/config.py` (`sync_env`: adiciona chaves ausentes, nunca sobrescreve/remove), integrado a `install()`/`enable()` do módulo. Testes em `tests/test_config.py`. | `0f44e83` | 2026-08-31 |

## Como retomar após perda de conexão

1. Ler este arquivo para saber a última fase concluída.
2. Ler `docs/fases/<NN>-<PROXIMA-FASE>.md` para o escopo da próxima fase.
3. Conferir `git log --oneline` para confirmar que o commit da última fase concluída está em `origin/main`.
4. Rodar a skill `using-agent-skills` (obrigatório) antes de começar a codar a próxima fase.
