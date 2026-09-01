# Changelog

## [0.1.0] - 2026-09-01

Primeira release.

### Adicionado

- Modelos de domínio (Pydantic): `Company`, `Vendor`, `Product`, `Service`,
  `Contact`, `Opportunity`, `Portfolio`.
- Sincronização `.env`/`env-model`: adiciona chaves ausentes, nunca
  sobrescreve ou remove valores existentes.
- Contrato `DataProvider` + `ManualProvider` de referência (in-memory, sem
  chamada externa).
- CRUD de produto/serviço no portfólio + merge Adicionar/Sobrescrever.
- Deduplicação de empresas por domínio/nome, preservando proveniência das
  fontes.
- Motor de oportunidades determinístico: regras de correlação
  (`CorrelationRule`/`evaluate_rules`) — `financial_potential`/
  `strategic_score` nunca inventados sem dado real.
- Camada de IA complementar e opcional: contrato `AIProvider` + OpenRouter
  (padrão), OpenAI, Gemini, Claude. Prompt sempre exige JSON estruturado com
  evidência e confiança, nunca inventa produto/serviço fora do portfólio.
- Frontend React/TypeScript (Vite, build próprio): tela de Oportunidades
  (filtros, ordenação, linha expansível) e Dashboard Executivo (KPIs,
  distribuição por fabricante, potencial por fabricante e por serviço,
  cliente×prospect, funil — tudo derivado de dado real, paleta categórica
  validada para acessibilidade).
- Exportação em PDF (tabela de oportunidades + executivo) e Excel.
- Rascunho de e-mail via IA — nunca envia automaticamente, nunca inventa
  campo ausente.
- Taxonomia de erro unificada (`DomainError`/`ErrorCategory`) com mapeamento
  categoria→status HTTP consistente em toda a API.
- Persistência real: SQLite via SQLAlchemy async.
- Módulo empacotado (`.mod`) e validado ponta a ponta contra o Tech.Forge
  Core real: instalação, ativação, `health_check()`, banco de dados.

### Corrigido

- Fonte core do fpdf2 quebrava a exportação em PDF com caracteres fora de
  latin-1 (travessão, aspas curvas, emoji).
- Tabelas do banco nunca eram criadas em produção (classes ORM não
  registradas antes do `create_all()`).
- SQLite descartava o timezone dos campos de data/hora na leitura.
- O builder de pacotes do Tech.Forge exclui todo arquivo começando com
  ponto — o arquivo de configuração modelo foi renomeado de `.env-model`
  para `env-model` para sobreviver ao empacotamento.

### Plano de rollback

Sem servidor de produção compartilhado (módulo local-first) — rollback é
reinstalar a versão anterior do `.mod`:

1. Manter o `.mod` da versão anterior guardado (não é sobrescrito pelo build).
2. Desinstalar a versão nova via o Package Manager do Tech.Forge.
3. Instalar o `.mod` anterior.
4. `.env` do usuário nunca é tocado por instalar/desinstalar — `sync_env()`
   só adiciona chave nova, nunca remove — dado de configuração sobrevive ao
   rollback.
5. O banco (`data/lead_tracker.db`) não é apagado ao desativar o módulo, só
   ao desinstalar explicitamente — reinstalar a versão anterior preserva os
   dados já persistidos, contanto que o schema seja compatível (sem
   migração formal ainda).
