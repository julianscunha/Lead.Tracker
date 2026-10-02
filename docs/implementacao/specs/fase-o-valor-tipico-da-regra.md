---
title: "Fase O — Valor típico informado na regra"
order: 38
tags: [lead-tracker, implementacao, spec]
---

# Fase O — Valor típico informado na regra (preenche o "potencial financeiro")

Consulta: `ecc:architect` (princípios, âncora, riscos), antes de decidir. Status: **concluída** (entregue após a 1.3.0).

## Problema

`Opportunity.financial_potential` **nunca é preenchido**: `_build_opportunity` (`core/opportunity_engine.py`) grava sempre `None`, de propósito, para nunca inventar número. O dashboard já soma e pondera esse campo (`core/dashboard_metrics.py`), então os totais de potencial e as ordenações por potencial ficam zerados. Produto e serviço não têm preço, e a oportunidade gerada por regra nem liga a um produto (`product_id` fica vazio).

## Decisão (e o que ficou de fora)

**O valor é digitado pelo usuário na regra; o sistema só o copia.** Não calcula, não deriva e não tem valor padrão. Isso não fere "custo de inação em R$ calculado pelo sistema" (fora de escopo permanente): copiar um número configurado é o mesmo que `opportunity_score`, que já vem da regra. A linha que não cruzamos é o sistema **calcular** o valor.

- **Âncora na regra, não no produto/serviço:** a oportunidade não tem `product_id`, a regra pode ter vários itens "ausentes" e o mesmo produto vale tickets diferentes em contextos diferentes (cross-sell × up-sell).
- **Fora desta fase (v2 descartado):** multiplicar o valor por faixa de porte (`employee_count`/receita) **é o sistema calculando** e esbarra no fora de escopo. Só voltaria como decisão explícita do usuário, registrada à parte.
- **Prospecção geográfica** (`geo-discovery`) não tem regra: continua `None`; não herda valor do produto de referência.
- **Moeda:** só reais; o rótulo fixa "R$", sem campo de moeda.

## Mapa de capacidades

| Ordem | Módulo | Responsabilidade |
|---|---|---|
| 1 | `rule-deal-value` | `CorrelationRule.estimated_deal_value: float \| None` (validador `> 0`; zero e negativo rejeitados, para 0 nunca significar "desconhecido"), coluna na tabela de regras, campo no cadastro da regra (Configurações > Regras) com hint. |
| 2 | `engine-copies-value` | `_build_opportunity` copia o valor para `financial_potential` e grava `financial_potential_basis` ("Valor típico informado na regra «X»: R$ N"); sem valor = `None`. Novo campo `Opportunity.financial_potential_basis`. |
| 3 | `value-labels` | Rótulos que não parecem previsão: na linha e no detalhe, "Valor típico informado: R$ X (definido na regra «Y»)"; nos totais, "Soma dos valores típicos informados — não é previsão de receita; pode se sobrepor"; contagem de oportunidades sem valor. Nunca "potencial", "previsão" ou "receita esperada". `core/business_case.py` deixa de chamar o campo de "Porte estimado da conta". |

## Pontos de atenção

- **Dupla contagem:** duas regras na mesma empresa somam no total e no ponderado. Não deduplicamos por empresa (seria inventar regra); o rótulo "pode se sobrepor" e a contagem de oportunidades sem valor tornam isso visível.
- **Regra editada depois:** o id da oportunidade é determinístico (empresa, regra, evidência), e o re-sync sobrescreve `financial_potential`. O valor reflete a regra **no momento do sync**, e o `basis` registra o valor usado; os snapshots diários preservam o histórico. Confirmar na implementação que o upsert de `save_opportunity` atualiza o campo.
- **Business case:** continua sem R$ na versão 1 (decisão explícita); só o rótulo é corrigido.
- **Exports PDF/Excel:** passam a trazer o valor com o mesmo rótulo.

## Teste

Regra com valor → `financial_potential` igual e `basis` preenchido; regra sem valor → `None` e o total do dashboard o ignora; valor 0 ou negativo rejeitado (modelo e rota); geo → `None`; duas regras na mesma empresa → o total soma as duas (comportamento documentado); re-sync depois de editar a regra atualiza o valor; business case não usa mais o rótulo antigo. Dados fictícios.

## Critério de sucesso

- [ ] O total e a ordenação por valor deixam de ser zero quando há regras com valor informado.
- [ ] Nenhum valor aparece sem que o usuário o tenha digitado.
- [ ] Nada na tela chama a soma de previsão ou receita esperada.
