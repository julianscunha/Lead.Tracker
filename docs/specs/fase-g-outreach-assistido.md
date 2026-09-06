# Fase G — Outreach assistido (e-mail mais persuasivo + cadência sugerida)

Depende só da Fase C (evidência/`justification` determinística já
existe em `Opportunity.justification`). Pode rodar em paralelo às
Fases D/E/F, não depende delas.

## Mapa de capacidades (confirmado pelo usuário)

| Ordem | Módulo | Responsabilidade | Consulta a especialista |
|---|---|---|---|
| 1 | `primary-reason-field` | `primary_reason` no rascunho de e-mail é eco/validação do `Opportunity.justification` já existente — nunca gerado livremente pela IA. | Não (mecânico) |
| 2 | `differentiator-and-ps-fields` | `differentiator`/`ps` opcionais, com validação determinística pós-resposta que rejeita qualquer um sem evidência de origem em evidence/portfolio. | Sales Engineer |
| 3 | `tone-by-customer-status` | `if is_customer` no prompt — texto dos dois tons (cliente vs. frio). | Outbound Strategist |
| 4 | `prompt-prohibition-guards` | Proibições de urgência falsa e "clientes como você" genérico — checagem determinística pós-resposta (heurística de palavras-gatilho), testável sem IA real. | Sales Coach |
| 5 | `outreach-touch-model` | `OutreachTouch` insert-only (mesmo padrão de `OpportunityStatusChange`) — persiste só o fato consumado. | Não (mecânico) |
| 6 | `suggested-cadence-engine` | Função pura `compute_next_suggested_touch` — 3 toques cliente / cap por rep/dia prospecção fria, nunca persiste "próximo passo". | Outbound Strategist |
| 7 | `next-action-line-and-mark-sent-ui` | 1 linha + botão "marcar como enviado" (exige copiar o rascunho antes de habilitar — decisão confirmada). Nunca fila de disparo, nunca "% de sequência completa". | Sales Engineer |
| 8 | `silence-to-qualified-notification` | `is_cadence_silent` (função pura) — sinaliza sugestão de voltar pra `qualified`, nunca muda status sozinha. | Sales Coach (threshold) |

**Decisão confirmada (botão "marcar como enviado")**: só habilita
depois que o usuário copiar/exportar o rascunho gerado — reforça que
o envio de verdade aconteceu fora do sistema, evita virar disparo
semi-automático.

**Riscos de arquitetura identificados no planejamento**:
- `primary_reason` de saída = eco do `primary_reason`/`justification`
  de ENTRADA, nunca geração livre — mesma blindagem que `_build_opportunity`
  já tem contra a IA inventar `justification` (Fase C).
- `differentiator` é o ponto mais fácil de escorregar pra "fato novo"
  — precisa de teste determinístico que rejeite qualquer termo/número
  ausente de evidence+portfolio combinados, não só instrução de prompt.
- Cap por rep/dia e janela de silêncio são regras de TEMPO — nunca
  podem chamar `update_opportunity_status` automaticamente (mesmo
  princípio de `is_zombie_opportunity`/`is_aging_opportunity`, que só
  alimentam métrica/notificação, nunca gravam status sozinhos).
- `OutreachTouch` nunca persiste "próximo passo planejado" — sempre
  derivado na leitura (mesmo padrão de `compute_qbr_suggested_days`).

## Módulo 1 — `primary-reason-field`

Classificado como mecânico no mapa de capacidades (sem consulta a
especialista) — é a blindagem central de toda a fase, então merece o
mesmo rigor mesmo sem consulta de negócio.

**Decisão**: `EmailDraft.primary_reason` é sempre ECO do valor de
ENTRADA (`justification`/`Opportunity.justification`, hoje o único
motivo determinístico existente), nunca lido da resposta da IA
(`structured`). A IA só é instruída a REFORÇAR esse motivo já dado em
subject/body/cta (`motivo_principal` no contexto enviado à IA), nunca
a decidir ou reescrever qual é o motivo principal — mesma blindagem
que `_build_opportunity` já tem contra a IA inventar `justification`
(Fase C, CLAUDE.md "Deterministic rules come before AI").

`generate_email_draft`/`build_email_request`/`parse_email_draft`
ganharam parâmetro opcional `primary_reason` (default: usa
`justification` se não informado) — retrocompatível, nenhuma chamada
existente quebra.

**Achado da revisão de código** (1 Importante, corrigido): o teste
que provava a blindagem sempre passava um `primary_reason` explícito
truthy — não pegaria uma regressão plausível tipo `primary_reason or
structured.get("motivo_principal")` (um "fallback de conveniência"
que reabriria a porta pra IA decidir o motivo). Adicionado
`test_parse_email_draft_never_falls_back_to_structured_when_no_primary_reason_given`:
sem `primary_reason` explícito, o campo fica `None` mesmo que
`structured` tenha um `motivo_principal` envenenado.

### Não objetivo deste módulo

- Consumo do campo `primary_reason` na UI — `frontend/src/api.ts`
  ainda não declara o campo; fica pendente pra quando algum módulo
  futuro da fase precisar exibi-lo.
- Um novo campo dedicado em `Opportunity` pra "motivo principal" —
  `justification` já cumpre esse papel hoje; criar um campo novo
  seria especulativo sem um caso de uso concreto que o exija.

### Teste

- `build_email_request`: `primary_reason` explícito vai pro contexto
  (`motivo_principal`); ausente, usa `justification` como default.
- `parse_email_draft`: eco fiel do parâmetro de entrada; nunca lido de
  `structured`, mesmo com `structured` envenenado, com OU sem
  `primary_reason` explícito informado (os dois cenários, achado da
  revisão); `None` por padrão quando nada é informado.
- `generate_email_draft`: fluxo ponta a ponta com provider mockado
  (sem chamada de rede real) confirma o eco e o fallback.

### Critério de sucesso

- [x] Nenhum caminho onde a resposta da IA alimente `primary_reason`
      de saída — provado por teste, não só por inspeção.
- [x] Retrocompatível — nenhuma chamada existente quebra.
- [x] Revisão de código sem achados Críticos pendentes.
