# Progresso da implementação

Fonte de verdade sobre em qual fase o desenvolvimento está. Atualizar a cada
fase concluída — se a sessão cair, é este arquivo que diz de onde continuar.

## Status atual

**Ordem oficial completa (Fases 01-15).** Release pública `v0.1.0` publicada: https://github.com/julianscunha/Lead.Tracker/releases/tag/v0.1.0

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
| — | Checkpoint de integração real: subi o Tech.Forge Core (uvicorn + SQLite + Alembic) e instalei o Lead.Tracker em `modules/installed/` de verdade — registry `INSTALLED`/`is_active`/`warnings: []`, router `/api/v1/modules/lead_tracker/ping` OK. **Correção (Fase 14):** a afirmação original aqui de que "health_check() foi chamado pelo monitor real" estava errada — `/api/v1/health` é um stub que só olha `registry.status`, nunca invoca `ModuleContract.health_check()` (ver `docs/FEEDBACK-TECHFORGE-SDK.md`). O lifecycle real só foi validado de fato na Fase 14, via `POST /marketplace/activate\|deactivate`. Adicionado `assets/` (subpasta opcional que faltava). | `6f89516` | 2026-09-01 |
| 08 | Motor de Oportunidades — `core/opportunity_engine.py`: `CorrelationRule` (dados, não hardcoded) + `evaluate_rules` (presença/ausência → `Opportunity` com evidência obrigatória). `financial_potential`/`strategic_score` ficam `None` (sem dado real/IA ainda). Testes em `tests/test_opportunity_engine.py`. | `203a115` | 2026-09-01 |
| 09 | Camada de IA — `ai/base.py` (`AIProvider` ABC, prompt/resposta estruturada JSON obrigatória), `ai/http_base.py` (timeout + retry só em erro transitório), providers `openrouter` (padrão)/`openai`/`gemini`/`claude`, `ai/factory.py`. `.env-model` documenta `AI_PROVIDER`. `backend/requirements.txt` criado (fastapi/pydantic/httpx). Testes com `httpx.MockTransport`, zero chamada de rede real, em `tests/test_ai.py`. | `15d8820` | 2026-09-01 |
| 10 | Interface Operacional — `frontend/` virou projeto npm React+TS (Vite lib mode, honra DECISOES 015), substituindo o esqueleto JS puro da Fase 04. Tela de Oportunidades: filtros, ordenação, linha expansível, ações copiar/gerar rascunho (placeholder honesto p/ Fase 12). Testes de lógica com vitest (6 passando). Validado contra o Core real (asset servido 200, registry sem warnings). | `824316c` | 2026-09-01 |
| 11 | Dashboard Executivo — `core/dashboard_metrics.py` (KPIs, distribuição/potencial por fabricante, oportunidades por serviço, cliente×prospect, funil — nada inventado, `None` nunca vira 0). Frontend: DonutChart/BarChart/FunnelChart/StatTile com paleta categórica validada (dataviz skill). Fora de escopo: tendência temporal (sem persistência histórica) e segmentação região/segmento (sem campo no modelo). PDF fica pra Fase 12. Validado contra o Core real. | `d5a7258` | 2026-09-01 |
| 12 | Exportações/E-mail — `exports/pdf.py` (opportunities_pdf/executive_pdf, fpdf2), `exports/excel.py` (openpyxl), `ai/email_draft.py` (rascunho via IA, nunca envia, nunca inventa campo). Endpoints reais em `backend/routes_exports.py` (POST /exports/pdf, /exports/excel, /exports/executive-pdf, /email-draft), frontend ligado de verdade (botões PDF/Excel + "Gerar rascunho" chamando a API). Guarda de segredo em `build_structured_prompt` (root-cause, cobre todo AIProvider). Bug real encontrado e corrigido: fonte core do fpdf2 só cobre latin-1, travessão/aspas curvas/emoji derrubavam a exportação — `_pdf_safe()` + teste de regressão. Validado contra o Core real (PDF `%PDF-1.3` válido, email-draft degrada com 503 amigável sem API key). | `2510bc9` | 2026-09-01 |
| 13 | Resiliência/Observabilidade — `core/errors.py` (`DomainError`/`ErrorCategory`, 9 categorias do doc). `AIProviderError`/`ProviderError` agora herdam dele. `ai/http_base.py` mapeia cada falha HTTP pra categoria certa. `exports/errors.py` (`ExportError`/`wrap_export_errors`, rede de segurança pra falha inesperada de fpdf2/openpyxl). `backend/routes_exports.py`: tabela única categoria→status HTTP. Frontend: botões PDF/Excel com feedback "Gerando…"/disabled. Validado contra o Core real. | `9e4e913` | 2026-09-01 |
| 14 | Testes/Decisões/Documentação — **Persistência real implementada** (lacuna da ordem oficial, DECISOES 021): `core/db.py`/`db_models.py`/`repository.py`, SQLite via SQLAlchemy async. Decisões retroativas 021-024 registradas. `README.md` atualizado, `docs/TROUBLESHOOTING.md` e `CHANGELOG.md` criados. **2 bugs reais encontrados e corrigidos**: (1) tabelas nunca eram criadas em produção (`core.db_models` não importado antes de `create_all`); (2) SQLite descarta tzinfo na volta (`_ensure_utc`). **Correção importante**: descobri que `/api/v1/health` é um stub que nunca chama `health_check()` real — todos os checkpoints anteriores (Fases 04-13) validaram manifest/registry/roteamento, mas não o lifecycle do `ModuleContract`. Lifecycle real só validado agora, via `POST /marketplace/activate\|deactivate`. 15 arquivos de teste, zero regressão. | `8b9efc1` | 2026-09-01 |
| 15 | Empacotamento/Release — `docs/overview.md`/`docs/examples/basic.md` criados (Documentation First Principle, 26/27 checks do `validate-module` passam). **Bug sério encontrado no Tech.Forge (não no nosso código)**: `PackageBuilder` oficial exclui todo arquivo começando com ponto, incluindo `.env-model` (exigido pela Fase 03) — `.mod` empacotado quebrava `install()` de verdade com `FileNotFoundError`. Corrigido sem alterar o formato `.mod` via `scripts/package_mod.py` (injeta `.env-model` no zip + regenera checksum sha256). Ciclo completo validado: `.mod` real → `PackageManager.install()` real → `ModuleContract.install()`/`enable()`/`health_check()` reais → banco com as 7 tabelas. `CHANGELOG.md` com plano de rollback. Falta: decisão do usuário sobre publicar release pública (tag + GitHub Release + anexar `.mod`). | `86adcbf` | 2026-09-01 |

## Como retomar após perda de conexão

1. Ler este arquivo para saber a última fase concluída.
2. Ler `docs/fases/<NN>-<PROXIMA-FASE>.md` para o escopo da próxima fase.
3. Conferir `git log --oneline` para confirmar que o commit da última fase concluída está em `origin/main`.
4. Rodar a skill `using-agent-skills` (obrigatório) antes de começar a codar a próxima fase.
