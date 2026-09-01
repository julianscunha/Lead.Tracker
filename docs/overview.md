# Lead.Tracker

Módulo de Opportunity Intelligence para o Tech.Forge. Transforma dados de
clientes, prospects, portfólio tecnológico, produtos e serviços em
oportunidades comerciais priorizadas (cross-sell, up-sell, modernização,
otimização de custos).

## O que o módulo faz

- Consolida empresas vindas de múltiplas fontes (Salesforce, website, manual)
  numa única `Company`, sem duplicação (dedup por domínio/nome).
- Detecta oportunidades por regras determinísticas de correlação de
  portfólio (presença/ausência de produto/serviço), sempre com evidência.
- Complementa com IA (opcional — OpenRouter, OpenAI, Gemini ou Claude) pra
  interpretar, correlacionar, enriquecer e gerar rascunho de e-mail. A IA
  nunca decide sozinha nem inventa produto fora do portfólio configurado.
- Dashboard executivo com KPIs e gráficos, todos derivados de dado real.
- Exportação em PDF e Excel.

## Arquitetura

- Backend: Python/FastAPI, persistência SQLite (SQLAlchemy async).
- Frontend: React/TypeScript, compilado via Vite (ESM único, sem framework
  compartilhado com o Core).
- Domínio determinístico primeiro, IA depois: `core/opportunity_engine.py`
  gera oportunidades completas sem depender de nenhuma chamada de IA.

## Configuração

Ver tela de Configurações do módulo (ou `.env` durante desenvolvimento) para
`AI_PROVIDER`/`AI_API_KEY` (opcional), `SALESFORCE_*` e `GOOGLE_MAPS_*`
(integrações opcionais, desligadas por padrão).

## Documentação completa

Ver `README.md` e `CONTRIBUTING.md` neste repositório para arquitetura,
comandos de desenvolvimento e regras de domínio.
