---
title: "Lead.Tracker — Roadmap"
order: 6
tags: [lead-tracker, roadmap, backlog]
---

# Roadmap

Só o que **ainda falta**, na ordem sugerida de execução. O que já foi entregue está em [`implementacao/`](implementacao/README.md); as regras que valem para qualquer item estão em [`principios.md`](principios.md). Cada item, quando chegar a vez, ganha a spec em `implementacao/specs/` antes de qualquer código. Esforço: P (dias), M (1–2 semanas), G (mais) — estimativa, não compromisso.

## Visão geral

| # | Item | Valor | Esforço | Depende de | Horizonte |
|---|---|---|---|---|---|
| R12 | Valor típico informado na regra | Alto: acende totais e ordenação por valor | P | — | Agora |
| R5 | Provider de enriquecimento | Médio | M | — (R1, URL da empresa, já entregue) | Depois |
| R6 | Visões salvas na lista | Médio: produtividade do vendedor | P–M | — | Depois |
| R7 | Forecast por conversão histórica | Alto, mas só com dado | G | volume de histórico (R3, auditoria, já entregue) | Condicionado |
| R8 | Autenticação e autoria confiável | Baixo hoje | M | — | Condicionado |
| R9 | Novos conectores (HubSpot, Pipedrive, Website) | Depende do cliente | M cada | — | Sob demanda |
| R10 | Entrada genérica por webhook | Médio | M | — (R4 já entregue) | Sob demanda |

Sem dependências abertas entre os itens: todos podem andar em paralelo.

## Agora

## Depois

### R12. Valor típico informado na regra (preenche o "potencial financeiro")
Spec em proposta: [`fase-o-valor-tipico-da-regra.md`](implementacao/specs/fase-o-valor-tipico-da-regra.md). Hoje `financial_potential` nunca é preenchido, então totais e ordenações por valor ficam zerados. Proposta: o usuário informa um valor típico (R$) em cada regra e o sistema só o copia, nunca calcula. Multiplicar por porte da empresa fica fora (seria o sistema calculando).

### R5. Provider de enriquecimento
Completar a empresa a partir do domínio (porte, setor, site) por API externa, como os plugins Clearbit e FullContact do Mautic. Provider só coleta e normaliza, como os demais.

### R6. Visões salvas na lista de oportunidades
O vendedor guarda combinações de filtro com nome ("renovação em 60 dias + severidade alta") e reabre com um clique; pode exportar pelo PDF/Excel que já existe. Ideia dos segmentos do Mautic. Só leitura e filtro: nada dispara sozinho.

## Condicionado

### R7. Forecast calibrado por conversão histórica
Taxa de conversão real por estágio/segmento no lugar de probabilidade estática, cruzada com velocidade no estágio, para Commit/Best Case/Upside baseado em dado. **Antes de especificar**, medir quantas transições de estágio existem (hoje: foto diária e `OpportunityStatusChange`). Com pouco histórico o forecast sai enganoso; nesse caso, aguardar volume.

### R8. Autenticação e autoria confiável
Hoje o histórico de alterações registra *quem* pelo `rep_id` que a pessoa informa na tela (autodeclarado, sem verificação), ou "não identificado". Autoria confiável exige identidade de usuário/autenticação no produto; quando existir, o `rep_id` informado vira o usuário logado e o campo deixa de ser editável.

## Sob demanda

### R9. Novos conectores de fonte
HubSpot, Pipedrive e o provider "Website" (coleta de texto do site, que aparece como "em breve" nas Configurações). Cada um quando houver cliente que precise.

### R10. Entrada genérica por webhook
Receber empresas e contatos de qualquer CRM via webhook (estilo Zapier), sem um provider novo por conector. Inferido pelo nome do plugin Zapier do Mautic; não verificado. Exige autenticação da entrada e validação estrita do payload (dado externo é não confiável).

## Fora de escopo
 (mencionado pelas personas, descartado por ora)

- Scraping de LinkedIn/job postings, sentiment analysis de e-mail — alto
  esforço, baixo ROI enquanto os sinais estruturados (CRM, Maps) ainda nem
  estão implementados.
- "Regra builder" livre (AND/OR arbitrário) — as 6 personas convergem em
  evitar isso; 3 tipos fixos de regra bastam.
- Pontuação combinada única ("deal score" agregado) — o domínio proíbe
  colapsar os 4 números; fica só como ordenação de exibição.
- Campos personalizados de `Contact` (só `Account` por ora) — mudaria o
  contrato `DataProvider` inteiro; se necessário, é spec própria.
- **Custo de inação em R$ calculado pelo sistema** — permanentemente fora de
  escopo, não só "por ora". O valor exato sempre fica como pergunta em
  aberto na justificativa (Fase C), nunca um número que a IA ou uma regra
  determinística calcula sozinha — é a mesma linha vermelha de "nunca
  inventar fato", só que fácil de escorregar porque parece útil.
- Pipeline de streaming/CDC pra atualizar o dashboard em tempo real — o
  motor de regras já roda em lote/sob demanda; snapshot diário (Fase D)
  resolve sem essa complexidade. Reconsiderar só se surgir requisito de
  dashboard "ao vivo" com o motor rodando continuamente.
- Sequenciador automático de e-mail/disparo em lote — o produto é
  explicitamente "sugestão + confirmação humana", nunca "fila de
  outreach automatizada" (Fase G).
- Sincronização bidirecional (escrever de volta no Salesforce ou em outra fonte) — os providers só coletam, nunca alteram a fonte (ideia do Mautic descartada por conflitar com esta regra).
- Relatórios agendados enviados por e-mail e automação de campanha/pontuação automática — disparo automático contraria "sugestão + confirmação humana".
