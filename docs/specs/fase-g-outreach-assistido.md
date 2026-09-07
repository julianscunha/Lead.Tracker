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

## Módulo 2 — `differentiator-and-ps-fields`

Consulta ao agente Sales Engineer antes de implementar (decisões
abaixo confirmadas, não reabrir). Dois campos opcionais no rascunho
de e-mail: `differentiator` (releitura persuasiva de um fato já
presente em evidence/portfolio) e `ps` (P.S. reforçando o ponto mais
forte do corpo).

**5 guard-rails determinísticos** (`ai/email_guardrails.py`, função
pura `validate_persuasive_field`, nunca chama IA, testável com assert
simples):
1. Limite de 1 frase por campo.
2. Blocklist de termos absolutos/superlativos ("líder de mercado",
   "comprovad-", "garantid-", "sempre", "nunca", "100%", ...).
3. Todo número/percentual citado precisa ter match literal
   (normalizando vírgula/ponto decimal) em evidence+portfolio.
4. Comparativo ("mais"/"melhor"/"maior"/...) sem número âncora no
   mesmo texto é rejeitado.
5. Menção a fonte externa não citada ("segundo", "estudo", "pesquisa
   mostra", "fonte:", "dados indicam") é rejeitada.

**Comportamento na reprovação**: descarta só o campo (fica `None`),
nunca a geração inteira — `differentiator`/`ps` são opcionais, o
e-mail já é funcional sem eles.

**Decisão de escopo consciente**: uma 6ª camada ("whitelist de
entidades de portfólio" — garantir que produto citado está no
portfólio DESTA oportunidade, não em qualquer produto do catálogo
geral) ficou de fora — exigiria threading do catálogo completo através
da cadeia de chamadas, que hoje só recebe um `portfolio: dict` opaco.
As 5 camadas acima já dão cobertura sem essa complexidade extra.

**Achados da revisão de código** (2 Importantes, ambos corrigidos; 1
bug adicional encontrado durante o próprio ciclo de correção, também
corrigido):
1. `_flatten_strings` descartava silenciosamente número nativo
   (`int`/`float`) dentro do portfolio — como o `portfolio: dict`
   chega via JSON real (Pydantic deserializa número como `int`/`float`
   nativo, não string), um `differentiator` citando corretamente um
   preço real (`{"price": 1500}`) seria rejeitado como "número não
   encontrado", um falso positivo que quebra a feature no caminho mais
   comum. Corrigido: `_flatten_strings` converte `int`/`float`
   (excluindo `bool`, que é subclasse de `int` em Python) pra string
   antes de descartar.
2. `_flatten_strings` era recursiva sem limite de profundidade, e
   `_validated` (`ai/email_draft.py`) não tinha `try/except` ao redor
   do guard-rail — um portfolio anormalmente aninhado podia estourar
   `RecursionError` e derrubar a geração INTEIRA do e-mail (violando a
   garantia central: "campo reprovado é descartado, nunca a geração
   inteira"). Corrigido: guard de profundidade em `_flatten_strings`
   (corta em 20 níveis) + `try/except Exception` em `_validated` que
   trata qualquer falha do guard-rail como reprovação do campo, nunca
   como erro fatal.
3. **Bug adicional** (encontrado testando o fix acima, não pela
   revisão): o split de "frases" (`re.split(r"[.!?]+", text)`) contava
   o ponto decimal de um número (`"4.5"`) como fim de frase — todo
   `differentiator`/`ps` legítimo citando um número com ponto decimal
   seria rejeitado como "mais de uma frase". Corrigido com lookaround
   (`(?<!\d)[.!?]+(?!\d)`) que nunca conta um ponto entre dígitos como
   fim de frase.

### Não objetivo deste módulo

- Whitelist de entidades de portfólio (6ª camada) — decisão consciente
  de escopo, documentada acima.
- Normalização de separador de milhar (`"1.500"` vs `"1500"`) —
  limitação aceita e testada explicitamente
  (`test_decimal_point_in_number_never_counts_as_sentence_boundary`
  cobre o caso de ponto decimal; separador de milhar continua rejeitando,
  intencional, não corrigir sem um caso de uso real que o exija).

### Teste

- `validate_persuasive_field` (`tests/test_email_guardrails.py`, 15
  testes): as 5 checagens cobertas individualmente; normalização de
  vírgula/ponto decimal; número nativo (`int`/`float`) e `bool`
  explicitamente excluído; profundidade de recursão nunca derruba;
  ponto decimal nunca conta como fim de frase.
- `parse_email_draft`/`generate_email_draft` (`tests/test_email_draft.py`,
  9 testes novos): campo que passa é mantido; campo reprovado é
  descartado mantendo o resto do rascunho intacto; número inventado é
  rejeitado; ausência dos campos não quebra nada; exceção não tratada
  no guard-rail descarta só o campo (regressão do achado 2); fluxo
  ponta a ponta com provider mockado nos dois sentidos (aceita/rejeita).

### Critério de sucesso

- [x] Nenhum caminho onde `differentiator`/`ps` cite fato ausente de
      evidence/portfolio sem ser descartado.
- [x] Falha no guard-rail (qualquer exceção) nunca derruba a geração
      inteira — provado por teste, não só por inspeção.
- [x] Revisão de código sem achados Importantes pendentes.

## Módulo 3 — `tone-by-customer-status`

Consulta ao agente Outbound Strategist antes de implementar (texto
das duas instruções confirmado, não reabrir). Tom do e-mail varia
conforme `is_customer` (bool) — sempre uma das duas variações fixas,
nunca uma terceira genérica.

**Cliente ativo**: abre citando uso já existente do portfólio como
fato concreto (nunca elogio genérico); proíbe explicitamente mencionar
produto que o cliente NÃO usa na abertura (só pode entrar no CTA);
CTA de continuidade/expansão de baixo atrito.

**Prospecção fria**: abre pelo achado externo como observação factual,
proíbe explicitamente "percebemos que..." (descreve o FATO, nunca o
ATO de observar); CTA exploratório de baixíssimo compromisso, proíbe
explicitamente pedir demonstração/orçamento/apresentação da empresa.

`_build_instruction(is_customer)` é um dispatcher binário simples
(ternário entre duas constantes) — estruturalmente à prova de uma
terceira variante. Default `is_customer=False` preserva o
comportamento anterior a este módulo (instrução única, sem distinção
de tom), sem quebrar nenhum teste dos módulos 1/2.

**Achados da revisão de código** (2 Importantes, ambos corrigidos —
lacunas de teste, não bugs de produção):
1. O teste que prometia cobrir a proibição de CTA de demo/orçamento
   só verificava a palavra genérica "proibido", não as cláusulas
   específicas — um editor futuro podia apagar só a proibição de
   demo/orçamento mantendo a palavra "proibido" em outro lugar da
   frase, e o teste continuaria verde. Corrigido: asserções diretas
   por "demonstração"/"orçamento"/"apresentação da empresa".
2. Faltava um teste travando a exclusividade mútua das duas
   instruções (garantida hoje pela estrutura do código, mas sem teste
   que a trave contra uma refatoração futura). Adicionado
   `test_tone_instructions_are_mutually_exclusive`.

### Não objetivo deste módulo

- Terceiro tom/variação intermediária — `is_customer` é binário no
  domínio, sem meio-termo especulativo.
- Validação de tipo em runtime pra `is_customer` — já validado pelo
  Pydantic na única entrada externa (`EmailDraftRequest`).

### Teste

- `build_email_request`: default é tom de prospecção fria;
  `is_customer=True` usa tom de cliente; cada instrução contém suas
  proibições específicas (não só uma palavra genérica); as duas
  instruções são mutuamente exclusivas (nunca uma contém o texto
  característico da outra).
- `generate_email_draft`: `is_customer` passa ponta a ponta sem
  quebrar o fluxo com provider mockado.

### Critério de sucesso

- [x] Sempre exatamente uma das duas variações de tom, nunca ambas
      nem nenhuma.
- [x] Texto das proibições específicas travado por teste, não só por
      inspeção.
- [x] Revisão de código sem achados Importantes pendentes.

## Módulo 4 — `prompt-prohibition-guards`

Consulta ao agente Sales Coach antes de implementar (listas de
gatilhos e regras de "dado real"/"caso concreto" confirmadas, não
reabrir). Duas proibições que valem pro corpo INTEIRO do e-mail
(subject/greeting/body/cta — campos obrigatórios, diferente do
módulo 2 que só validava `differentiator`/`ps` opcionais):

1. Nunca mencionar prazo/urgência sem dado temporal real (data no
   formato DD/MM/AAAA ou AAAA-MM-DD) em evidence/portfolio.
2. Nunca generalizar "clientes como você"/"empresas do seu porte"
   sem caso concreto (número real, proxy de resultado mensurável) em
   evidence/portfolio.

Nunca bloqueia a palavra isolada ("prazo", "cliente") — só a
combinação gatilho+ausência do dado que legitimaria.

**Comportamento na reprovação — DIFERENTE do módulo 2**: como
subject/body/cta são obrigatórios (não dá pra "descartar" um corpo de
e-mail), reprovação vira `AIProviderError` (mesmo tratamento já usado
pra campo obrigatório ausente), pedindo pra tentar de novo — nunca
retorna e-mail malformado nem derruba silenciosamente.

**Decisão de escopo consciente** (Sales Coach concordou): "caso
concreto" é aproximado por número real, nunca detecção de nome de
empresa citado — exigiria NLP, fora do nível de regex/string que
todos os guard-rails desta fase usam.

**Achados da revisão de código** (3 Importantes, todos corrigidos):
1. `_has_concrete_reference` contava fragmentos de DATA (dia/mês/ano)
   como "número real" — qualquer evidência com data de renovação
   (comum) legitimava uma generalização vazia sem nenhum resultado
   mensurável de verdade associado. Corrigido: remove trechos de data
   antes de contar números.
2. Gatilho `"corra e"` colidia com verbos comuns em português
   ("recorra e", "socorra e", "discorra e", "percorra e") — uma frase
   legítima e inofensiva seria rejeitada. Corrigido: removido da
   lista (outros gatilhos já cobrem a intenção "aja agora").
3. Concatenação de subject+greeting+body+cta com espaço (`" ".join`)
   permitia uma frase proibida se "formar" na fronteira entre dois
   campos (ex.: subject terminando em "por tempo" + body começando
   com "limitado") sem aparecer de fato em nenhum campo isolado.
   Corrigido: junção com quebra de linha (`"\n".join`) — nenhum
   gatilho contém quebra de linha, então a fronteira nunca mais
   "cola" acidentalmente.

### Não objetivo deste módulo

- Detecção de nome de empresa citado como "caso concreto" — decisão
  consciente de escopo (Sales Coach), exigiria NLP.
- Normalização de separador de milhar em datas — mesma limitação já
  aceita no módulo 2 pra números em geral.

### Teste

- `validate_email_body` (`tests/test_email_guardrails.py`, 9 testes
  novos): texto limpo passa; urgência sem data real rejeitada;
  urgência COM data real em evidence aceita; generalização sem caso
  concreto rejeitada; generalização COM número real aceita; texto
  vazio sempre passa; palavra isolada nunca dispara sozinha; data em
  evidence nunca legitima generalização (regressão do achado 1);
  verbo comum com "corra e" nunca é flagado (regressão do achado 2).
- `parse_email_draft`/`generate_email_draft` (`tests/test_email_draft.py`,
  4 testes novos): rejeita urgência sem data real via `AIProviderError`;
  aceita urgência com data real; nunca junta frase proibida na
  fronteira entre campos (regressão do achado 3); rejeita
  generalização ponta a ponta com provider mockado.

### Critério de sucesso

- [x] Reprovação em subject/body/cta sempre vira `AIProviderError`,
      nunca e-mail malformado nem descarte silencioso.
- [x] Data real nunca é confundida com "caso concreto" (números
      distintos, sem overlap).
- [x] Nenhum gatilho colide com palavra/verbo comum do português —
      provado por teste, não só por inspeção.
- [x] Revisão de código sem achados Importantes pendentes.

## Módulo 5 — `outreach-touch-model`

Classificado como mecânico no mapa de capacidades (sem consulta a
especialista). `OutreachTouch` — registro insert-only do fato
consumado "toque marcado como enviado" (canal, motivo, quando), mesmo
padrão de `OpportunityStatusChange` (histórico imutável). Nunca guarda
"próximo passo planejado" — isso é sempre derivado na leitura pelo
módulo 6 (`compute_next_suggested_touch`), nunca persistido, mesmo
princípio de `compute_qbr_suggested_days` (Fase C).

`channel`/`reason_label` ficam string livre, sem enum — decisão
consciente: canal de outreach não é regra de negócio do domínio de
oportunidades, é detalhe de apresentação que os módulos 6/7 vão
normalizar na camada de UI se precisarem (ex.: ícone por canal), sem
tocar o modelo de persistência. Fechar um enum aqui, antes de ver o
módulo 6/7 usá-lo, seria especulação que YAGNI existe pra evitar.

`save_outreach_touch` usa `session.add`+`commit` direto (não o helper
`_upsert`/`session.merge` usado pelas outras entidades) — deliberado:
é a primeira função deste arquivo pensada como caminho de escrita real
de uma entidade insert-only; `session.add` levanta erro numa colisão
de id em vez de silenciosamente fazer merge sobre uma linha de
histórico existente, que seria o comportamento errado aqui.

`count_outreach_touches_today` já nasce usando
`datetime.now(timezone.utc).date()` como contrato esperado do
chamador — aprendendo do bug já cometido uma vez em
`count_geo_discoveries_today` (Fase E, módulo 6), com o teste de
regressão escrito ANTES de qualquer código de negócio depender dele.

**Revisão de código**: aprovada sem achados Críticos/Importantes.
Sugestão aplicada: `count_outreach_touches_today` carrega todo o
histórico do rep e filtra em Python (mesmo padrão de
`count_geo_discoveries_today`) — mas aqui a suposição de volume é
mais frágil (outreach não tem cota própria que limite o total
acumulado ao longo da vida da oportunidade). Documentado com
`ponytail:` no código, nomeando o teto e o upgrade (`WHERE sent_at >=
início do dia UTC` + índice composto `(rep_id, sent_at)` se o volume
justificar) — nunca resolvido especulativamente agora.

### Não objetivo deste módulo

- Enum fechado pra `channel` — decisão consciente de escopo, não
  esquecimento.
- Índice composto em `(rep_id, sent_at)` — prematuro pro volume atual,
  documentado como upgrade futuro (`ponytail:`), não implementado.
- Qualquer lógica de negócio (motor de cadência, UI) — é só o modelo
  de dados; módulo 6 consome isso.

### Teste

- `tests/test_persistence.py` (5 testes novos): round-trip; múltiplos
  toques nunca se sobrescrevem (garantia central do insert-only);
  filtro por oportunidade; contagem só do rep certo hoje; contrato
  UTC travado com caso de borda real (5 minutos após meia-noite UTC).
- `tests/test_db_table_registration.py`: contagem bumped de 14→15
  (`outreach_touches`).

### Critério de sucesso

- [x] Nenhum "próximo passo planejado" persistido — sempre derivado.
- [x] Múltiplos toques da mesma oportunidade nunca se sobrescrevem.
- [x] Contrato UTC correto desde o nascimento da função, sem repetir
      o bug já corrigido uma vez na Fase E.
- [x] Revisão de código sem achados Críticos/Importantes.
