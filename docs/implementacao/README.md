---
title: "Lead.Tracker — Implementação"
order: 7
tags: [lead-tracker, implementacao, indice]
---

# Implementação

Tudo que **já foi construído**. O que falta está em [`../roadmap.md`](../roadmap.md); as regras do produto, em [`../principios.md`](../principios.md). Histórico narrativo das fases: [`fases.md`](fases.md). Uma spec por fase, em `specs/`.

| Fase | O que entregou | Spec |
|---|---|---|
| 0 | Configurações de fontes (tela de credenciais, toggle, teste de conexão) | [`fase0-configuracoes-fontes.md`](specs/fase0-configuracoes-fontes.md) |
| A | Ingestão ampliada do Salesforce (campos padrão e personalizados) | [`salesforce-account-standard-fields.md`](specs/salesforce-account-standard-fields.md) |
| A | ↳ contexto de campos personalizados | [`salesforce-custom-fields-context.md`](specs/salesforce-custom-fields-context.md) |
| B | Fundação do modelo de dados | [`fase-b-fundacao-modelo-dados.md`](specs/fase-b-fundacao-modelo-dados.md) |
| B.1 | Ligação real: ingestão → banco → API → frontend | [`fase-b1-ligacao-real.md`](specs/fase-b1-ligacao-real.md) |
| C | Motor de regras ampliado (sinais de expansão, severidade, discovery prompt) | [`fase-c-motor-de-regras.md`](specs/fase-c-motor-de-regras.md) |
| D | Dashboard acionável (aging, zumbi, metas, histórico de status) | [`fase-d-dashboard-acionavel.md`](specs/fase-d-dashboard-acionavel.md) |
| E | Prospecção geográfica (Google Maps) | [`fase-e-prospeccao-geografica.md`](specs/fase-e-prospeccao-geografica.md) |
| F | Mapeamento configurável de campo personalizado | [`fase-f-mapeamento-campo-personalizado.md`](specs/fase-f-mapeamento-campo-personalizado.md) |
| G | Outreach assistido (e-mail e cadência sugerida) | [`fase-g-outreach-assistido.md`](specs/fase-g-outreach-assistido.md) |
| H | Cobertura de stakeholder e risco de single-thread | [`fase-h-cobertura-stakeholder.md`](specs/fase-h-cobertura-stakeholder.md) |
| I | Funil por representante × categoria | [`fase-i-funil-rep-categoria.md`](specs/fase-i-funil-rep-categoria.md) |
| J | Gate de discovery completa antes de qualificar | [`fase-j-gate-discovery.md`](specs/fase-j-gate-discovery.md) |
| K | URL da empresa (captura no Maps, reconciliação da promoção geo, link na tela) | [`fase-k-url-da-empresa.md`](specs/fase-k-url-da-empresa.md) |
| L | Lista de "não contatar" (bloqueio por empresa/contato/canal, aplicado na sugestão, no toque e no rascunho) | [`fase-l-lista-nao-contatar.md`](specs/fase-l-lista-nao-contatar.md) |
| — | Business case por oportunidade (PDF de 1 página) | [`business-case-por-oportunidade.md`](specs/business-case-por-oportunidade.md) |
