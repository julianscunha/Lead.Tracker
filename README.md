# Lead.Tracker

[![Release](https://img.shields.io/github/v/release/julianscunha/Lead.Tracker)](https://github.com/julianscunha/Lead.Tracker/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tech.Forge module](https://img.shields.io/badge/Tech.Forge-module-6366f1)](https://github.com/julianscunha/Tech.Forge)
[![Python](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)](backend/requirements.txt)
[![React](https://img.shields.io/badge/frontend-React%2FTypeScript-61DAFB?logo=react&logoColor=white)](frontend/package.json)

## Suas melhores oportunidades de venda já estão no seu CRM — só ninguém olhou

Lead.Tracker cruza o que você já sabe sobre seus clientes (CRM, website,
portfólio técnico) com o que você vende, e aponta onde tem dinheiro na mesa:
cliente com Veeam mas sem DR, prospect crescendo sem produto X, conta que
vale reavaliação de preço. Tudo com evidência, nunca um palpite.

Regras determinísticas fazem o trabalho pesado; IA é opcional e só entra
pra interpretar, correlacionar e redigir — nunca decide sozinha, nunca
inventa produto fora do seu portfólio.

Módulo instalável do [Tech.Forge](https://github.com/julianscunha/Tech.Forge).

## O que ele faz

- **Encontra oportunidades de verdade** — cross-sell, up-sell, serviços,
  otimização de custo e modernização, cada uma com motivo e evidência.
- **Prioriza por impacto** — score de aderência, potencial financeiro e
  confiança são números separados, nunca misturados num só.
- **Mostra o panorama** — dashboard executivo com KPIs e gráficos, tudo
  vindo de dado real.
- **Poupa seu tempo** — exporta PDF/Excel com um clique e gera rascunho de
  e-mail comercial pronto pra revisar e enviar.
- **Funciona com ou sem IA** — o motor de oportunidades roda inteiro sem
  nenhuma chave de API configurada.

## Arquitetura

Backend em Python/FastAPI, frontend em React/TypeScript, persistência em
SQLite local, providers desacoplados de fonte de dado, IA plugável por
provider, empacotado como `.mod` do Tech.Forge.

## De onde vêm os dados

Lead.Tracker não é preso a nenhuma fonte específica — Salesforce é só uma
integração opcional entre várias.

Hoje: Salesforce, website da empresa, importação manual.
No radar: HubSpot, Pipedrive, LinkedIn, Google Maps, CSV e outros conectores.

## Portfólio

Você informa o website da sua empresa uma vez, e o Lead.Tracker monta a
partir dele um portfólio estruturado — fabricantes, produtos, subprodutos,
serviços e as relações entre eles. Você revisa e ajusta o resultado antes
de valer pra qualquer oportunidade.

## A tela de Oportunidades

Uma planilha viva: filtre por cliente ou prospect, por produto ou serviço,
ordene por score ou potencial financeiro, expanda qualquer empresa pra ver
as fontes por trás do número. Copie o que precisar ou gere um rascunho de
e-mail comercial direto dali.

## Papel da IA

Regras determinísticas são a base — a IA entra depois, só pra interpretar
contexto, correlacionar sinais, enriquecer justificativa e redigir texto.
Ela nunca decide sozinha que uma oportunidade existe, e nunca inventa
produto ou serviço fora do portfólio configurado.

## Desenvolvimento

### Comandos

```bash
# Backend — testes (scripts standalone, sem pytest instalado no projeto)
python tests/test_models.py
python tests/test_config.py
python tests/test_providers.py
python tests/test_portfolio.py
python tests/test_normalization.py
python tests/test_opportunity_engine.py
python tests/test_ai.py
python tests/test_dashboard_metrics.py
python tests/test_exports.py
python tests/test_email_draft.py
python tests/test_routes_exports.py
python tests/test_errors.py
python tests/test_export_errors.py
python tests/test_persistence.py
python tests/test_db_table_registration.py
pip install -r backend/requirements.txt   # antes de rodar os testes

# Frontend
cd frontend
npm install
npm run build   # gera frontend/index.js (build output, gitignored)
npm run test    # vitest — lógica pura (filtros/ordenação/paleta)
```

### Testar contra o Tech.Forge Core de verdade

Não faz parte do projeto (é uma dependência de desenvolvimento, gitignored):

```bash
git clone https://github.com/julianscunha/Tech.Forge .techforge-dev
# copiar manifest.yaml, backend/, frontend/index.js, core/, providers/, exports/, ai/,
# assets/, docs/ e tests/ para .techforge-dev/modules/installed/lead_tracker/
cd .techforge-dev/core/backend && python run.py   # sobe o Core em :8000
```

`install()`/`enable()`/`health_check()` do módulo só são chamados de verdade
via `POST /api/v1/marketplace/activate/{id}` e `/deactivate/{id}` — o
endpoint `/api/v1/health` é um stub do Core que não invoca o `ModuleContract`
diretamente, só reflete o status do registry.

## Tech.Forge

O Lead.Tracker é um módulo do ecossistema Tech.Forge e deve respeitar seu contrato de módulo, SDK, frontend host e empacotamento.

- Core da plataforma: [`Tech.Forge`](https://github.com/julianscunha/Tech.Forge)
- Catálogo oficial de módulos: [`Tech.Forge.Modules`](https://github.com/julianscunha/Tech.Forge.Modules)

Este repositório é o desenvolvimento do módulo — a distribuição pro catálogo oficial acontece a partir do `.mod` publicado em cada [release](https://github.com/julianscunha/Lead.Tracker/releases).

## Contribuindo

Contribuições são bem-vindas. Veja [`CONTRIBUTING.md`](CONTRIBUTING.md) para as regras de domínio que todo PR precisa respeitar, como rodar o projeto localmente e o fluxo de contribuição.

## Licença

[MIT](LICENSE).
