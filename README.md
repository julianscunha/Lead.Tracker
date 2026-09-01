# Lead.Tracker

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

## Desenvolvimento

A implementação deve seguir estritamente os arquivos numerados em `docs/fases/`.

Começar em:

`01-ARQUITETURA.md`

e terminar em:

`15-EMPACOTAMENTO-RELEASE.md`

## Tech.Forge

O Lead.Tracker é um módulo do ecossistema Tech.Forge e deve respeitar seu contrato de módulo, SDK, frontend host e empacotamento.

## Licença

A licença definitiva deve ser definida antes da primeira release pública.
