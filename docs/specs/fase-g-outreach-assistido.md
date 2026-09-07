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

## Módulo 6 — `suggested-cadence-engine`

Consulta ao agente Outbound Strategist antes de implementar (números
e regras confirmados, não reabrir). Função pura
`compute_next_suggested_touch` (`core/opportunity_engine.py`) — nunca
dispara nada, nunca decide status sozinha, sempre depende do rep
marcar como enviado (módulo 5).

**Cliente ativo**: 3 toques — toque 1 (dia 0, email,
"continuidade_uso_atual"); toque 2 (+7 dias, ligação,
"gap_portfolio"); toque 3 (+7 dias após o 2º, linkedin,
"prova_social_urgencia"). Categorias mudam de ângulo (uso atual →
expansão → prova social), nunca 3 e-mails genéricos repetidos.

**Prospecção fria**: 2 toques — toque 1 (dia 0, email,
"abertura_sinal"); toque 2 (+4 dias, ligação, "reforco_angulo_novo").
Depois do 2º sem avanço, para — nunca sugere 3º toque automaticamente.

**Cap diário**: 25 toques/dia por REP (não por oportunidade), cliente
ativo + prospecção fria no MESMO contador — nunca dois caps
paralelos, senão volta a ser volume disfarçado.

**Três estados distintos**, nunca um `None` opaco:
`CadenceSuggestion(channel, reason_category)` (há toque a sugerir);
`CADENCE_AWAITING_INTERVAL` (ainda dentro do intervalo, não é estado
especial pra UI); `CADENCE_EXHAUSTED` (cadência acabou sem avanço —
sinal de decisão manual); `CADENCE_DAILY_CAP_REACHED` (cota do rep
estourada — conceito de rep, não de oportunidade).

O passo da cadência é determinado só pela CONTAGEM de toques já
feitos (`len(touches)`) — nunca por inspecionar `reason_label` (string
livre) pra adivinhar categoria. `touches_today_for_rep`/`daily_cap`
chegam como parâmetro (nunca lidos de sessão aqui), mesmo padrão de
`select_promotions` (Fase E) — função pura e testável sem sessão.

**Achado da revisão de código** (1 Importante, corrigido; 2 Sugestões
aplicadas):
1. `list_outreach_touches` (módulo 5) não garante ordem — se um
   chamador futuro passasse a lista fora de ordem, `touches[-1]`
   escolheria silenciosamente o toque ERRADO como "mais recente" pra
   calcular o próximo intervalo, sem levantar exceção nenhuma.
   Corrigido: a função ordena internamente por `sent_at` antes de
   indexar, ficando auto-defensiva independente do que o chamador
   passar (mais barato que garantir ordem em todo `ORDER BY` de quem
   consome).
2. Nenhum teste provava que `daily_cap` como parâmetro de fato
   substitui o default — todos usavam 25 (igual ao
   `OUTREACH_DAILY_CAP`). Adicionado teste com cap customizado (5).
3. Nenhum teste documentava o comportamento com lista fora de ordem.
   Adicionado teste comparando lista em ordem vs. fora de ordem,
   confirmando resultado idêntico (regressão do achado 1).

### Não objetivo deste módulo

- Aplicação em lote do cap pra múltiplas oportunidades de um rep
  (decidir QUAIS sugestões "gastam" o cap quando há mais devidas que
  vagas) — isso é módulo 7 (UI), que itera as oportunidades e aplica
  a prioridade (cliente ativo antes de prospecção fria).
- Cap configurável via tela de Configurações — `OUTREACH_DAILY_CAP` é
  constante fixa nesta fatia; configurabilidade via `.env`/UI fica
  pra quando houver necessidade real (YAGNI).

### Teste

- `tests/test_cadence_engine.py` (14 testes): cada posição das duas
  cadências (toque devido e aguardando intervalo); esgotamento das
  duas cadências; cap bloqueando toque devido; cap não bloqueando
  abaixo do limite; cap customizado via parâmetro (regressão);
  ordem de checagem cap-antes-de-esgotamento; lista fora de ordem
  nunca escolhe o anchor errado (regressão); categorias nunca se
  repetem dentro da mesma cadência (garantia estrutural).

### Critério de sucesso

- [x] Função genuinely pura — nenhum import de `core.repository`,
      nenhuma sessão/rede.
- [x] Categoria nunca se repete dentro da mesma cadência — garantido
      pela estrutura (índice na tabela), não por checagem de texto.
- [x] Lista de toques fora de ordem nunca produz resultado errado
      silenciosamente — provado por teste.
- [x] Revisão de código sem achados Importantes pendentes.

## Módulo 7 — `next-action-line-and-mark-sent-ui`

Primeiro módulo desta fase com rota exposta/UI — sync pra cópia
instalada + verificação ao vivo (curl/Playwright) exigidas, ao
contrário dos módulos 1-6 (puros, sem rota).

**Consulta ao Sales Engineer** (antes de implementar, cobrindo tradução
das 5 categorias técnicas + os 3 estados especiais + fluxo do botão +
onde a tela vive):
- **Frase por categoria** = canal + motivo em uma cláusula concreta,
  nunca o nome técnico da categoria (`gap_portfolio` nunca aparece
  como texto pro rep). Tabela de 5 frases (`CADENCE_REASON_PHRASE` no
  frontend), canal já embutido no verbo ("Ligar…", "Enviar e-mail…",
  "Mandar mensagem…").
- **`aguardando_intervalo`**: mensagem neutra, sem cor de alerta —
  "Sem ação sugerida agora — dentro do intervalo da cadência."
- **`cadencia_esgotada`**: linguagem de decisão, não de fracasso —
  aponta pro dropdown de Status já existente (`StatusTransition`) em
  vez de duplicar botões de "encerrar"/"reabrir" que já existem ali.
- **`cap_diario_atingido`**: mensagem por linha em vez do banner
  agregado único que o Sales Engineer recomendou (não existe ainda uma
  lista agregada de ações do dia por rep nesta fase — `ponytail:`
  registrado no código, upgrade quando essa superfície existir).
- **Botão copiar → enviar**: só "Copiar" (ou "Copiar rascunho" pra
  canal e-mail) visível primeiro; depois de copiar, feedback "Copiado
  ✓" por ~1,2s, então o mesmo lugar vira "Marcar como enviado" — nunca
  um botão desabilitado visível antes de copiar (decisão confirmada:
  copiar é pré-requisito pra habilitar o marcar-como-enviado).
- **Onde vive**: dentro da tela de Oportunidades já existente (painel
  de detalhe da linha), não uma aba nova — evita recriar a "fila de
  disparo" que o roadmap proíbe.

### Implementação

- `core/opportunity_engine.py` — comentário adicionado à checagem de
  cap diário explicando a ordem de precedência (cap antes de
  esgotamento é intencional, achado da revisão de código).
- `backend/routes_sync.py` — duas rotas novas:
  - `GET /opportunities/{id}/next-suggested-touch?rep_id=` — busca
    `Opportunity`/`Company`/`OutreachTouch`s/contagem-do-dia e chama
    `compute_next_suggested_touch` (nenhuma lógica de cadência na
    rota, só orquestração). 404 se a oportunidade não existe OU se a
    empresa referenciada não existe (FK obrigatória — nunca tratar
    empresa ausente como "é prospect" silenciosamente). `rep_id`
    validado como não-vazio (`Query(min_length=1)`), mesma garantia
    que o POST já tinha via `Field(min_length=1)`.
  - `POST /opportunities/{id}/outreach-touches` — grava o fato
    consumado via `save_outreach_touch` (insert-only, nunca edita/
    desfaz um toque já registrado); devolve o `OutreachTouch` salvo.
- `frontend/src/api.ts` — `getNextSuggestedTouch`, `markOutreachTouchSent`.
- `frontend/src/OpportunityTable.tsx` — `NextActionSuggestion`
  (embutido no painel de detalhe, ao lado de `StatusTransition`/
  `SeverityQualification`): busca a sugestão ao expandir a linha,
  trata os 4 estados, implementa o fluxo copiar→marcar-como-enviado.
  Um erro ao recarregar a sugestão DEPOIS de marcar como enviado com
  sucesso nunca reusa a mensagem de "falha ao registrar" (o toque já
  foi gravado no servidor nesse caso — mensagem distinta evita o rep
  achar que precisa repetir a ação).
- `frontend/src/App.tsx` — campo "Seu id de representante" no toolbar
  de Oportunidades, persistido em `localStorage` (`lt_rep_id`) — único
  lugar do módulo que rastreia "rep atual", já que não há conceito de
  usuário logado ainda.

### Achado da revisão de código (3 Importantes, corrigidos)

1. `rep_id` no GET não era validado (só o POST tinha
   `min_length=1`) — um `rep_id=""` computaria cadência/cota pro rep
   vazio silenciosamente. Corrigido com `Query(min_length=1)`.
2. Empresa ausente (`company is None`) fazia fallback silencioso pra
   `is_customer=False`, trocando a tabela de cadência sem avisar.
   Corrigido: vira 404 (mesmo tratamento de oportunidade não
   encontrada), já que `company_id` é FK obrigatória.
3. No frontend, uma falha ao recarregar a sugestão logo após marcar
   como enviado com sucesso reusava a mensagem genérica de "falha ao
   calcular a próxima ação", enganando o rep sobre se o registro
   aconteceu. Corrigido com mensagem distinta.

### Achado da verificação ao vivo (Playwright, corrigido)

A tabela de frases (`CADENCE_REASON_PHRASE`) foi transcrita a partir
do texto do Sales Engineer sem cruzar contra o canal REAL de cada
categoria em `_CUSTOMER_CADENCE` — duas frases saíram com o verbo
errado: `continuidade_uso_atual` dizia "Ligar" mas o canal real é
e-mail; `gap_portfolio` dizia "Enviar e-mail" mas o canal real é
ligação. Só apareceu testando a tela de verdade (o botão já mostrava
"Copiar" corretamente pro canal não-email, mas o TEXTO da frase
contradizia a ação — o rep copiaria um texto de "e-mail" pra fazer uma
ligação). Corrigido + regressão em `frontend/src/logic.test.ts`
(`CADENCE_REASON_PHRASE`) comparando o verbo de cada frase contra o
canal real da categoria.

### Não objetivo deste módulo

- Banner agregado único de "cap do dia batido" cobrindo todas as
  oportunidades de um rep — precisa de uma lista agregada de ações do
  dia que ainda não existe (`ponytail:` no componente).
- Botões dedicados "encerrar"/"reabrir cadência" pro estado
  `cadencia_esgotada` — o dropdown de Status já cobre isso, duplicar
  seria uma segunda superfície pra mesma decisão.
- Autenticação/identidade de usuário — `rep_id` continua sendo texto
  livre digitado pelo usuário (mesmo padrão de `GeoDiscoveryWizard`/
  `RepTargetsSection`), só ganhou persistência em `localStorage` pra
  não precisar redigitar a cada sessão.

### Teste

- `tests/test_routes_sync.py` (+8): sugestão do primeiro passo pra
  oportunidade nova; 404 pra oportunidade inexistente (GET e POST);
  registrar toque e ver a sugestão seguinte virar "aguardando
  intervalo"; `rep_id` vazio rejeitado com 422; 404 quando a empresa
  referenciada não existe; estado `cadencia_esgotada` refletido de
  ponta a ponta pela rota; estado `cap_diario_atingido` refletido de
  ponta a ponta pela rota (achados da revisão de código — os módulos
  1-6 só testavam a função pura, não a rota, pra esses dois estados).

### Critério de sucesso

- [x] Rota GET nunca decide cadência com empresa ausente ou `rep_id`
      vazio silenciosamente — ambos viram erro explícito.
- [x] `OutreachTouch` gravado só via insert (`save_outreach_touch`) —
      nenhuma rota de edição/exclusão criada.
- [x] Nenhuma transição de `Opportunity.status` acontece a partir
      deste módulo — cadência é só leitura/sugestão.
- [x] UI nunca mostra a categoria técnica (`gap_portfolio` etc.) —
      sempre a frase traduzida.
- [x] Botão "marcar como enviado" só habilita depois de copiar
      (decisão confirmada, sem regressão).
- [x] Sincronizado pra cópia instalada e verificado ao vivo.
- [x] Revisão de código sem achados Importantes pendentes.

## Módulo 8 — `silence-to-qualified-notification`

Último módulo da fase. Reaproveita a mesma rota GET do módulo 7
(`next-suggested-touch`) em vez de criar uma rota nova — o sinal de
silêncio não tem ação própria (é só leitura/alerta), e a rota já
carrega tudo que ele precisa (oportunidade, empresa, toques).

**Consulta ao Sales Coach** (limiar e enquadramento, antes de
implementar):
- **Duas causas distintas, nunca colapsadas numa**: "nunca contatado"
  (zero toques) vs. "cadência esgotada e ficou quieto" (toques
  existem, cadência rodou inteira, e passou um tempo extra sem nada).
  UI precisa dizer qual das duas é, senão esconde o diagnóstico.
- **Limiar do "nunca contatado"**: reusar o mesmo SLA de triagem que
  `is_aging_opportunity` já usa (`AGING_SLA_DAYS`, default 7) — não
  inventar um segundo threshold pro mesmo fato de "sentou sem ninguém
  mexer". Só que aqui vale tanto pra `detected` quanto pra `qualified`
  (`is_aging_opportunity` só cobre `detected`).
- **Limiar do "cadência esgotada e ficou quieto"**: contar a partir do
  ÚLTIMO toque (não do zero) e a partir do momento em que a cadência
  esgota — não do dia da detecção. Buffer proporcional ao espaçamento
  de cada cadência: 3 dias pra cliente (toques de 7 em 7), 2 dias pra
  prospecção fria (toques de 4 em 4). Isso é uma ESCALADA do sinal que
  o módulo 6 já mostra (`CADENCE_EXHAUSTED`) no dia em que a cadência
  termina — nunca um segundo sinal independente disparando no mesmo
  dia.
- **Copy**: sempre fecha em pergunta/decisão, nunca veredito —
  "Ainda faz sentido priorizá-la agora?" / "Bom momento pra decidir:
  tentar outro ângulo, escalar, ou dispensar." — nunca "você falhou"
  ou alarme genérico.

### Implementação

- `core/opportunity_engine.py` — `SilenceSignal(reason, days_silent)`,
  `SILENCE_NEVER_CONTACTED`/`SILENCE_CADENCE_EXHAUSTED`,
  `_SILENCE_BUFFER_CUSTOMER_DAYS=3`/`_SILENCE_BUFFER_PROSPECT_DAYS=2`,
  `compute_silence_signal(status, touches, first_detected_at,
  is_customer, now, sla_days) -> SilenceSignal | None` — função pura,
  nunca chama `update_opportunity_status` (mesmo princípio de
  `is_zombie_opportunity`/`is_aging_opportunity`). Só considera
  `detected`/`qualified`; qualquer outro status devolve `None` (a
  oportunidade já avançou o suficiente pra não contar como "ficou
  quieta sem ninguém decidir").
- `backend/routes_sync.py` — `GET .../next-suggested-touch` passa a
  calcular `compute_silence_signal` na mesma sessão/consulta e devolve
  `silence_reason`/`silence_days` (ambos opcionais) junto com o `state`
  já existente. Cap diário batido SUPRIME o sinal de silêncio na
  resposta (ver achado da revisão de código abaixo) — nunca as duas
  mensagens juntas puxando o rep em direções opostas.
- `frontend/src/api.ts` — `NextSuggestedTouch` ganha
  `silenceReason`/`silenceDays`.
- `frontend/src/OpportunityTable.tsx` — `NextActionSuggestion` ganha
  um parágrafo `silenceBanner` (role="alert") que aparece ADITIVAMENTE
  em cima de qualquer um dos 4 estados de cadência já existentes,
  nunca substitui o conteúdo normal — é um alerta a mais, não um
  estado novo do fluxo copiar→marcar-como-enviado.

### Achado da revisão de código (2 Importantes, corrigidos)

1. `compute_silence_signal` não tinha noção de cap diário — a rota
   podia devolver `state="cap_diario_atingido"` ("essa sugestão volta
   amanhã") JUNTO com `silence_reason="cadencia_esgotada_silencio"`
   ("bom momento pra decidir: outro ângulo, escalar, ou dispensar") na
   mesma resposta, uma dizendo "espera" e outra "decida agora".
   Corrigido: cap batido suprime o sinal de silêncio na rota (mesma
   precedência que já mascara `CADENCE_EXHAUSTED` dentro de
   `compute_next_suggested_touch`).
2. Nenhum teste provava o limite EXATO dos dois thresholds (`days ==
   sla_days`/`days == buffer_days`) — só "abaixo" e "acima". Adicionados
   2 testes de fronteira confirmando a semântica estrita (`>`, nunca
   `>=`, mesmo padrão de `is_aging_opportunity`).

Sugestão aplicada (não-bloqueante): normalização de `sent_at` de CADA
toque antes do `max()`, não só do resultado — evita `TypeError` se
algum dia um chamador semear um toque com datetime naive no meio da
lista (hoje nunca acontece, `OutreachTouch.sent_at` sempre nasce aware
via `_now()`, mas o custo da defesa é uma linha).

### Não objetivo deste módulo

- Notificação push/e-mail pro rep — o sinal só aparece quando o rep
  abre a oportunidade (mesmo padrão de aging/zumbi, que também são só
  "quando alguém olhar").
- Qualquer forma de reabrir/mudar status automaticamente — mesmo
  princípio de `is_zombie_opportunity`: puramente consultivo.
- Um terceiro threshold configurável — reusa `AGING_SLA_DAYS` de
  propósito, pra não multiplicar telas de configuração pro mesmo tipo
  de decisão.

### Teste

- `tests/test_silence_signal.py` (10 testes): as duas causas
  distintas, para cliente e prospecção fria; status fora de escopo
  (`reviewed`/`contacted`/`opportunity`/`dismissed`) nunca sinaliza;
  fronteira exata dos dois thresholds (não sinaliza ainda); ordem dos
  toques nunca importa (`max()` em vez de indexar depois de ordenar).
- `tests/test_routes_sync.py` (+3, e 4 asserts existentes atualizados
  pros novos campos): nunca contatado sinalizado pela rota; status
  `opportunity` nunca sinaliza; cap diário batido suprime o sinal de
  silêncio mesmo quando a cadência está esgotada e silenciosa (achado
  1 da revisão, ponta a ponta).

### Critério de sucesso

- [x] Nenhuma transição de `Opportunity.status` acontece a partir
      deste módulo — só leitura/sugestão, mesmo padrão de módulos 6-7.
- [x] As duas causas de silêncio nunca se confundem — `reason`
      explícito, nunca um booleano opaco.
- [x] Nunca duplica o alerta que o módulo 6 já mostra no dia em que a
      cadência esgota — buffer conta do último toque, não do zero.
- [x] Cap diário e silêncio nunca aparecem juntos puxando o rep em
      direções opostas na mesma resposta.
- [x] Sincronizado pra cópia instalada e verificado ao vivo.
- [x] Revisão de código sem achados Importantes pendentes.
