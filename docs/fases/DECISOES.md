# Lead.Tracker — Decisões Arquiteturais

## 001 — Módulo Tech.Forge

Lead.Tracker será um módulo do Tech.Forge.

## 002 — Um único módulo de negócio

Não criar inicialmente um módulo Salesforce separado.

Salesforce é um provider/integration do Lead.Tracker.

Se no futuro a integração Salesforce se tornar infraestrutura compartilhada por múltiplos módulos, poderá ser extraída.

## 003 — Abstração de providers

Fontes externas não devem aparecer como conceitos centrais do domínio.

O domínio trabalha com dados normalizados.

## 004 — Cliente é atributo

A interface utiliza `is_customer`/status de cliente.

Não existe uma tela específica chamada Salesforce.

## 005 — Fontes são metadados

Cada empresa pode ter múltiplas fontes.

Exemplo:

```json
"sources": ["salesforce", "website"]
```

## 006 — Produtos e serviços são diferentes

Produto e serviço possuem modelos próprios e podem gerar oportunidades independentes.

## 007 — Score não é valor financeiro

Score mede aderência.

Potencial financeiro mede retorno potencial.

Eles podem gerar rankings diferentes.

## 008 — IA complementar

IA não substitui regras determinísticas.

## 009 — Portfólio é autoridade comercial

A IA deve usar o portfólio configurado pela empresa como base para recomendações.

## 010 — Sincronização manual

Não existe scheduler obrigatório para o portfólio.

O usuário atualiza quando desejar.

## 011 — Atualização do portfólio

Ao encontrar dados existentes, o usuário escolhe:
- adicionar;
- sobrescrever.

## 012 — UI operacional em tabela

A tela de oportunidades prioriza tabela, filtros, ordenação e expansão.

## 013 — Dashboard separado da operação

O dashboard fornece visão executiva; a tabela fornece operação comercial.

## 014 — Local-first

O módulo deve funcionar localmente e minimizar custos de infraestrutura.

## 015 — Frontend Tech.Forge

O frontend final será React/TypeScript, compatível com o Module Host do Tech.Forge.

## 016 — Segurança

Secrets não entram no repositório, logs, prompts ou exports.

## 017 — Usuário leigo

Mensagens devem ser amigáveis e acionáveis.

## 018 — Desenvolvimento sequencial

As etapas numeradas são a ordem oficial de implementação.

## 019 — Repositório de desenvolvimento

O código será mantido no repositório `Lead.Tracker` e posteriormente empacotado como módulo do Tech.Forge.

## 020 — Open Source

O núcleo do projeto deve permanecer genérico e não depender de informações específicas de uma empresa. Portfólio, serviços, produtos, integrações e regras comerciais devem ser configuráveis.

## 021 — Camada de persistência (SQLite via SQLAlchemy async)

Nenhuma das 15 fases da ordem oficial (`00-ORDEM-DESENVOLVIMENTO.md`) cobria persistência, apesar de `01-ARQUITETURA.md` já citar SQLite como stack. As Fases 02–13 foram construídas inteiramente como funções puras/determinísticas, sem banco de dados real.

Alternativas: usar `sdk.database` do SDK do Tech.Forge (descartado — ainda é só um mock in-memory, "Phase 3", não uma sessão real); adiar persistência pra uma fase futura fora da numeração (descartado — usuário optou por fechar a lacuna antes do empacotamento).

Escolha: SQLite via SQLAlchemy async (aiosqlite), mesmo padrão do próprio Tech.Forge Core, com `core/db.py` (engine/sessão), `core/db_models.py` (tabelas) e `core/repository.py` (ponte Pydantic↔ORM). Sem Alembic por enquanto — schema simples, local-first (DECISOES 014); migração formal fica pra quando o schema evoluir de fato. Banco vive em `data/lead_tracker.db`, criado em `install()`/`enable()`, apagado em `uninstall()`.

## 022 — IA: OpenRouter como provider padrão

Decisão explícita do usuário (não do modelo de IA que implementa): `AI_PROVIDER` default é `openrouter`, com `openai`, `gemini` e `claude` como alternativas diretas via `ai/factory.py`, sem custo de troca de arquitetura — todos implementam o mesmo contrato `AIProvider`.

## 023 — Frontend do módulo: React/TypeScript com build próprio

DECISOES 015 já definia "frontend final React/TypeScript", mas o Tech.Forge Core só serve `.js`/`.mjs` estático — nunca compila `.tsx` (`module_assets.py`, whitelist de extensão). Escolha: projeto npm dentro de `frontend/` (Vite, modo lib, saída ESM única), substituindo o esqueleto JS puro da Fase 04. `frontend/index.js` (build output) é gitignored; só o código-fonte (`frontend/src/`) é versionado.

## 024 — Taxonomia de erro unificada (`DomainError`)

`ProviderError` (Fase 05) e `AIProviderError` (Fase 09) nasceram como exceções independentes, cada uma com sua própria mensagem amigável. Na Fase 13, unificadas sob `core/errors.py` (`DomainError` + `ErrorCategory`, as 9 categorias de `docs/fases/13`), mantendo compatibilidade (mesmos nomes de classe, mesma assinatura posicional). Endpoints HTTP mapeiam categoria→status via uma única tabela (`backend/routes_exports.py`), não regra por rota.
