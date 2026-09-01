# Changelog

Formato livre por fase — o projeto ainda não teve release pública (ver
`docs/fases/15-EMPACOTAMENTO-RELEASE.md`). Versão do manifest permanece
`0.1.0` até a primeira release.

## Não lançado

### Fase 14 — Testes/Decisões/Documentação
- Camada de persistência real: SQLite via SQLAlchemy async (`core/db.py`,
  `core/db_models.py`, `core/repository.py`) — lacuna da ordem oficial,
  registrada em `docs/fases/DECISOES.md` 021.
- Bug real corrigido: tabelas nunca eram criadas em produção (`core.db_models`
  não era importado antes de `create_all()`).
- Decisões retroativas registradas (021-024): persistência, OpenRouter
  padrão, frontend React/TS, taxonomia de erro unificada.
- `docs/TROUBLESHOOTING.md` criado.

### Fase 13 — Resiliência/Observabilidade
- Taxonomia de erro unificada (`core/errors.py`: `DomainError`/`ErrorCategory`).
- `ProviderError`/`AIProviderError` passam a herdar `DomainError`.
- Endpoints HTTP mapeiam categoria→status via tabela única.
- Feedback visual de operação longa nos botões de exportação.

### Fase 12 — Exportações/E-mail
- PDF (tabela de oportunidades + executivo) e Excel via `exports/`.
- Rascunho de e-mail via IA (`ai/email_draft.py`) — nunca envia, nunca
  inventa campo ausente.
- Endpoints HTTP reais, frontend ligado (botões PDF/Excel, "Gerar rascunho").
- Bug real corrigido: fonte core do fpdf2 quebrava com caractere fora de latin-1.
- Guarda de segredo em prompts de IA (`build_structured_prompt`).

### Fase 11 — Dashboard Executivo
- KPIs, distribuição por fabricante (donut), potencial por fabricante e por
  serviço (barras), cliente×prospect, funil — tudo derivado de dado real.
- Paleta categórica validada (dataviz skill).

### Fase 10 — Interface Operacional
- Frontend migrado de JS puro pra React/TypeScript (Vite, build próprio).
- Tela de Oportunidades: filtros, ordenação, linha expansível.

### Fase 09 — Camada de IA
- Contrato `AIProvider` + OpenRouter (padrão), OpenAI, Gemini, Claude.
- Prompt sempre exige JSON estruturado com evidência e confiança.

### Fase 08 — Motor de Oportunidades
- Regras de correlação determinísticas (`CorrelationRule`/`evaluate_rules`).
- `financial_potential`/`strategic_score` nunca inventados sem dado real.

### Fase 07 — Coleta/Normalização
- Deduplicação de empresas por domínio/nome, preservando proveniência.

### Fase 06 — Empresa/Portfólio
- CRUD de produto/serviço + merge Adicionar/Sobrescrever.

### Fase 05 — Providers
- Contrato `DataProvider` + `ManualProvider` de referência.

### Fase 04 — Esqueleto do Módulo
- `manifest.yaml`, `ModuleContract`, frontend mínimo, ciclo de vida validado.

### Fase 02/03 — Modelo de Dados / Configuração
- Modelos de domínio (Pydantic) e sincronização `.env`/`.env-model`.
