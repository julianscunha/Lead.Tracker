# Lead.Tracker

[![Release](https://img.shields.io/github/v/release/julianscunha/Lead.Tracker)](https://github.com/julianscunha/Lead.Tracker/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tech.Forge module](https://img.shields.io/badge/Tech.Forge-module-6366f1)](https://github.com/julianscunha/Tech.Forge)
[![Python](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)](backend/requirements.txt)
[![React](https://img.shields.io/badge/frontend-React%2FTypeScript-61DAFB?logo=react&logoColor=white)](frontend/package.json)

## Módulo de Opportunity Intelligence para o Tech.Forge

Lead.Tracker é um módulo de Opportunity Intelligence para o Tech.Forge.

Seu objetivo é transformar dados de clientes, prospects, portfólio tecnológico, produtos, serviços e fontes externas em oportunidades comerciais priorizadas.

## Capacidades

- identificação de clientes e prospects;
- análise de portfólio;
- cross-sell;
- up-sell;
- oportunidades de serviços;
- otimização de custos;
- modernização tecnológica;
- correlação técnica;
- scoring;
- potencial financeiro;
- IA contextual;
- dashboard executivo;
- PDF;
- exportação tabular;
- rascunhos de e-mail.

## Arquitetura

- Python/FastAPI no backend;
- React/TypeScript no frontend;
- SQLite local;
- providers desacoplados;
- IA por provider;
- empacotamento `.mod`.

## Fontes

A plataforma não é acoplada ao Salesforce.

Iniciais:
- Salesforce;
- website;
- importação manual.

Futuras:
- HubSpot;
- Pipedrive;
- LinkedIn;
- Google Maps;
- CSV;
- outros conectores de API.

Salesforce é uma integração opcional.

## Portfólio

Cada empresa usuária informa seu website na tela Empresa.

O sistema utiliza o website para construir um portfólio estruturado de:
- fabricantes;
- produtos;
- subprodutos;
- serviços;
- relações.

O usuário pode editar o resultado.

## Oportunidades

A tela principal utiliza uma apresentação semelhante a uma planilha.

Permite:
- filtrar somente clientes;
- filtrar prospects;
- filtrar produtos;
- filtrar serviços;
- ordenar por score;
- ordenar por potencial financeiro;
- expandir empresas;
- visualizar fontes;
- copiar informações;
- gerar rascunho de e-mail.

## IA

A IA é complementar.

Regras e dados determinísticos são a base.

A IA:
- interpreta;
- correlaciona;
- enriquece;
- resume;
- gera textos.

Não decide sozinha e não inventa portfólio.

## Status

Veja `docs/fases/PROGRESSO.md` para a fase atual e o histórico de fases concluídas.

## Desenvolvimento

A implementação deve seguir estritamente os arquivos numerados em `docs/fases/`.

Começar em:

`01-ARQUITETURA.md`

e terminar em:

`15-EMPACOTAMENTO-RELEASE.md`

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
# assets/, docs/fases/ e tests/ para .techforge-dev/modules/installed/lead_tracker/
cd .techforge-dev/core/backend && python run.py   # sobe o Core em :8000
```

`install()`/`enable()`/`health_check()` do módulo só são chamados de verdade
via `POST /api/v1/marketplace/activate/{id}` e `/deactivate/{id}` — o
endpoint `/api/v1/health` é um stub do Core que não invoca o `ModuleContract`
(ver `docs/FEEDBACK-TECHFORGE-SDK.md`).

## Tech.Forge

O Lead.Tracker é um módulo do ecossistema Tech.Forge e deve respeitar seu contrato de módulo, SDK, frontend host e empacotamento.

- Core da plataforma: [`Tech.Forge`](https://github.com/julianscunha/Tech.Forge)
- Catálogo oficial de módulos: [`Tech.Forge.Modules`](https://github.com/julianscunha/Tech.Forge.Modules)

Este repositório é o desenvolvimento do módulo — a distribuição pro catálogo oficial acontece a partir do `.mod` publicado em cada [release](https://github.com/julianscunha/Lead.Tracker/releases).

## Contribuindo

Contribuições são bem-vindas. Veja [`CONTRIBUTING.md`](CONTRIBUTING.md) para as regras de domínio que todo PR precisa respeitar, como rodar o projeto localmente e o fluxo de contribuição.

## Licença

[MIT](LICENSE).
