# Critérios de qualificação de oportunidade

Este documento explica **o que cada critério significa e por que o número
é esse** — não é uma spec de implementação (essas ficam em
`docs/specs/`), é a referência de negócio pra quem configura, audita ou
questiona por que uma oportunidade recebeu determinado score ou banda.

Todo critério aqui é uma **regra determinística configurável**, nunca uma
estimativa de IA (`CLAUDE.md` — "Deterministic rules come before AI"). Os
números de corte (dias, multiplicadores, bandas) são pontos de partida
revisáveis, não constantes definitivas — cada um traz a razão de ter sido
escolhido e quando revisitar.

## Recência de atividade → multiplicador de `confidence_score`

**O que é:** proxy de "quão viva está a conversa com essa conta". Uma
oportunidade tecnicamente idêntica vale menos confiança se a conta está
em silêncio há muito tempo — não porque a oportunidade deixou de existir,
mas porque a chance de avançar agora é menor.

**De onde vem o dado:** `LastActivityDate` do Salesforce (`Company.last_activity_at`).
Fontes sem esse conceito (Manual, CSV) não alimentam este campo — nesse
caso a empresa é tratada como "muito fria" (ver abaixo), nunca como um
terceiro estado "não sei".

**Os 3 níveis:**

| Nível | Janela | Multiplicador |
|---|---|---|
| Quente | até 120 dias desde a última atividade | ×1.0 (sem penalidade) |
| Morno | 121 a 270 dias | ×0.85 |
| Muito frio | mais de 270 dias, **ou nunca registrado** | ×0.5 |

**Por que esses números:** a primeira versão usava um corte binário de 90
dias (quente/frio, ×1.0/×0.7). Consultamos o agente especialista Pipeline
Analyst antes de confirmar esse desenho em produção, e o retorno apontou
dois problemas reais:

1. **90 dias é curto demais** pra ciclo de venda de infraestrutura B2B
   (tipicamente 90-180+ dias) — uma conta parada 60-90 dias entre reuniões
   por causa de aprovação de budget/licitação é normal, não "esfriou". O
   corte de 90 dias penalizava esse ritmo normal como se fosse
   desengajamento.
2. **Corte único trata "91 dias sem atividade" igual a "700 dias"** —
   duas populações com risco de morte do deal muito diferentes,
   distorção perceptível pelo vendedor que usa o sistema.

A correção adicionou o nível intermediário "morno" e moveu o corte
quente/morno pra 120 dias. **Isso ainda não está calibrado com dado real
de vocês** — o ideal (segundo o próprio especialista consultado) é usar a
mediana de intervalo-entre-atividades dos deals fechados (`won`) do seu
histórico de Salesforce, não uma régua genérica de mercado. Revisitar
quando esse dado existir.

**Nunca acontece:** a ausência de `last_activity_at` nunca vira um
terceiro estado "desconhecido" — conta sem essa informação é tratada como
muito fria (regra de negócio deliberada, não lacuna de implementação).

## Nível hierárquico do contato (`seniority_tier`)

**O que é:** proxy de autoridade — o contato registrado é quem decide
(Economic Buyer) ou só um influenciador técnico? Uma oportunidade forte
com um contato só operacional tem risco de nunca chegar em quem aprova.

**De onde vem o dado:** inferido automaticamente do cargo (`Title` no
Salesforce) por palavra-chave, **sem IA** — é busca de substring em
português, case-insensitive, primeiro match vence:

| Categoria | Palavras-chave |
|---|---|
| `decisor` | gestor, diretor, gerente, head, ceo, cto, cio |
| `influenciador_tecnico` | arquiteto, especialista |
| `operacional` | técnico, analista, suporte |

Cargo sem nenhuma palavra-chave reconhecida fica **sem classificação**
(`None`) — o sistema nunca inventa um nível quando não tem certeza.

**Edição manual:** ainda não existe (rota de edição de contato é um item
futuro do roadmap, "Fatia 4b") — hoje a classificação automática é a
única fonte, mesmo sabendo que pode errar (ex.: "Diretor de Operações"
sendo confundido, cargos em outro idioma, etc.). Quando a edição manual
existir, ela sempre poderá corrigir o valor inferido.

## Quantificação de gap por severidade

*(Em implementação — esta seção será preenchida com o desenho final:
Alcance × Criticidade → banda de severidade, ambos preenchidos
manualmente pelo vendedor, revisado com o agente especialista Deal
Strategist antes de shipar.)*

## Por que consultar especialistas antes de fixar um número

Nenhuma pessoa na equipe de desenvolvimento deste módulo é especialista
em metodologia de vendas ou em diagnóstico de pipeline — por isso, toda
decisão de threshold/fórmula que afeta como uma oportunidade é priorizada
passa por um agente especialista (Pipeline Analyst, Deal Strategist, etc.)
antes de ser confirmada, e o motivo da escolha fica registrado aqui, não
só o número. Se um critério parecer estranho na prática, este documento
é o lugar pra entender a lógica original antes de mudar.
