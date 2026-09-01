# Progresso da implementação

Fonte de verdade sobre em qual fase o desenvolvimento está. Atualizar a cada
fase concluída — se a sessão cair, é este arquivo que diz de onde continuar.

## Status atual

**Fase em andamento: 12 — Exportações/E-mail** (ainda não iniciada)

> Nota: `frontend/index.js` agora é build output (gitignored) — rodar
> `npm install && npm run build` dentro de `frontend/` antes de testar o
> módulo contra o Core. `npm run test` roda os testes de lógica (vitest).

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
| 05 | Providers — `providers/base.py` (`DataProvider` ABC, `ConnectionTestResult`, `ProviderContext`, `ProviderError`), `providers/manual.py` (`ManualProvider`, referência in-memory). `core/models.py` ganhou `Contact`. Testes em `tests/test_providers.py`. | `376246a` | 2026-08-31 |
| 06 | Empresa/Portfólio — `core/portfolio.py`: CRUD de produto/serviço + `merge_portfolio` (Adicionar/Sobrescrever, DECISOES 011). Tela Empresa (UI) e extração via website/IA ficam para Fases 10/07/09. Testes em `tests/test_portfolio.py`. | `2767ee3` | 2026-08-31 |
| 07 | Coleta/Normalização — `core/normalization.py`: `normalize_domain`, `normalize_name`, `merge_companies` (dedup por domínio/nome, preserva proveniência das fontes). Fora de escopo: providers concretos (Salesforce/website reais) e sinais de enriquecimento externo. Testes em `tests/test_normalization.py`. | `10af916` | 2026-08-31 |
| — | Checkpoint de integração real: subi o Tech.Forge Core (uvicorn + SQLite + Alembic) e instalei o Lead.Tracker em `modules/installed/` de verdade — registry `INSTALLED`/`is_active`/`warnings: []`, router `/api/v1/modules/lead_tracker/ping` OK, `health_check()` chamado pelo monitor real (`is_healthy: true`). Fechou a lacuna aberta desde a Fase 04 (que só tinha testado o `ModuleContract` isolado, sem passar pelo Core). Adicionado `assets/` (subpasta opcional que faltava). | `6f89516` | 2026-09-01 |
| 08 | Motor de Oportunidades — `core/opportunity_engine.py`: `CorrelationRule` (dados, não hardcoded) + `evaluate_rules` (presença/ausência → `Opportunity` com evidência obrigatória). `financial_potential`/`strategic_score` ficam `None` (sem dado real/IA ainda). Testes em `tests/test_opportunity_engine.py`. | `203a115` | 2026-09-01 |
| 09 | Camada de IA — `ai/base.py` (`AIProvider` ABC, prompt/resposta estruturada JSON obrigatória), `ai/http_base.py` (timeout + retry só em erro transitório), providers `openrouter` (padrão)/`openai`/`gemini`/`claude`, `ai/factory.py`. `.env-model` documenta `AI_PROVIDER`. `backend/requirements.txt` criado (fastapi/pydantic/httpx). Testes com `httpx.MockTransport`, zero chamada de rede real, em `tests/test_ai.py`. | `15d8820` | 2026-09-01 |
| 10 | Interface Operacional — `frontend/` virou projeto npm React+TS (Vite lib mode, honra DECISOES 015), substituindo o esqueleto JS puro da Fase 04. Tela de Oportunidades: filtros, ordenação, linha expansível, ações copiar/gerar rascunho (placeholder honesto p/ Fase 12). Testes de lógica com vitest (6 passando). Validado contra o Core real (asset servido 200, registry sem warnings). | `824316c` | 2026-09-01 |
| 11 | Dashboard Executivo — `core/dashboard_metrics.py` (KPIs, distribuição/potencial por fabricante, oportunidades por serviço, cliente×prospect, funil — nada inventado, `None` nunca vira 0). Frontend: DonutChart/BarChart/FunnelChart/StatTile com paleta categórica validada (dataviz skill). Fora de escopo: tendência temporal (sem persistência histórica) e segmentação região/segmento (sem campo no modelo). PDF fica pra Fase 12. Validado contra o Core real. | `d5a7258` | 2026-09-01 |

## Como retomar após perda de conexão

1. Ler este arquivo para saber a última fase concluída.
2. Ler `docs/fases/<NN>-<PROXIMA-FASE>.md` para o escopo da próxima fase.
3. Conferir `git log --oneline` para confirmar que o commit da última fase concluída está em `origin/main`.
4. Rodar a skill `using-agent-skills` (obrigatório) antes de começar a codar a próxima fase.
