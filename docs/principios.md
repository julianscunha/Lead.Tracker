---
title: "Lead.Tracker — Princípios"
order: 5
tags: [lead-tracker, principios, arquitetura]
---

# Princípios do Lead.Tracker

Regras que valem para todo o produto. Se uma decisão de implementação violar uma delas, repense a implementação, não o princípio. Convergência de uma sessão de planejamento com 10 personas especializadas (Salesforce Architect, Pipeline Analyst, Deal Strategist, Account Strategist, Outbound Strategist, Sales Engineer, Data Consolidation Agent, Discovery Coach, Proposal Strategist, Sales Outreach).

Isso vale mais que qualquer item de fase individual — se uma decisão de
implementação violar um destes, pare e repense a implementação, não o
princípio.

1. **Núcleo sempre genérico.** Nenhuma fase pode hardcodar nome de campo,
   fabricante, produto ou categoria específica de um cliente do Lead.Tracker.
   Tudo que varia entre instalações vira dado de configuração (papel
   semântico, categoria, `relation_type`, `signal_type` como enum aberto) —
   nunca lógica de código. Já é regra do `CLAUDE.md`; as 6 personas
   reforçaram isso de ângulos diferentes sem eu pedir.

2. **Evidência é fato + implicação de negócio + fonte + data**, sempre.
   Nunca um log técnico cru ("Produto X ausente"). Formato de referência:
   `"[FATO] ... → [RISCO/OPORTUNIDADE] ... → [FONTE] ..., sincronizado em ..."`.
   Vale para toda oportunidade nova daqui pra frente, incluindo as geradas
   por sinais de expansão (Fase C) e prospecção geográfica (Fase E).

3. **Os 4 números da oportunidade nunca colapsam em um só.**
   `opportunity_score`, `financial_potential`, `strategic_score`,
   `confidence_score` continuam distintos no modelo de dados. Onde for
   preciso desempatar/ordenar (dashboard, fila do vendedor), o critério
   é: `confidence_score` desempata antes de `financial_potential` bruto —
   mas isso é regra de **exibição/ordenação**, nunca um campo novo persistido
   tipo "deal score" agregado.

4. **Interface pensada pra operador não-técnico.** Este é um requisito
   explícito do usuário do projeto, vale para todas as fases com tela nova
   (D, E, F):
   - Nunca expor nome de campo de API (`Segmento_Cliente__c`) na UI — sempre
     rótulo em português, escolhido de uma lista/dropdown, nunca digitado.
   - Nunca pedir pro usuário entender o que é SOQL, OAuth, `signal_type` ou
     qualquer termo técnico interno — esses termos existem só no código.
   - Assistente guiado (passo a passo com confirmação) em vez de tela de
     configuração com muitos campos soltos — mesmo padrão que a tela de
     portfólio já usa (Adicionar/Sobrescrever, revisão antes de aplicar).
   - Todo número/score na tela precisa de uma explicação inline (tooltip ou
     texto de apoio) do que ele significa e de onde veio — nunca um número
     sozinho sem contexto.
   - Estado vazio/erro sempre em linguagem de negócio ("Não consegui
     confirmar os dados dessa conta no Salesforce — verifique o acesso nas
     Configurações"), nunca a mensagem técnica crua (já é regra do
     `CLAUDE.md`, reforçando aqui pro contexto de UI).

5. **Resultado visual, chamativo, sempre exportável.** Outro requisito
   explícito do usuário: quem opera é o time comercial, público muito
   visual — número solto em tabela cinza não é aceitável onde já existe
   alternativa gráfica.
   - Toda tela que mostra resultado de análise (Dashboard, Oportunidades,
     e as novas de ICP/Prospecção) usa gráfico onde fizer sentido (já é o
     padrão do Dashboard atual — donut por fabricante, barras de potencial),
     não só linha de tabela.
   - **Gerar relatório é obrigatório em toda tela de resultado, não só um
     "nice to have"**: Dashboard e Oportunidades já têm isso
     (`executive_pdf`, `opportunities_pdf`/`opportunities_excel` em
     `exports/`) — qualquer tela nova que mostre resultado de análise (ICP/
     Prospecção na Fase E, por exemplo) precisa nascer com exportação
     equivalente, seguindo o mesmo padrão, não como pendência posterior.
   - Isso não conflita com o princípio 4 — "visual e chamativo" e "número
     sempre explicado" andam juntos, não são opostos.
