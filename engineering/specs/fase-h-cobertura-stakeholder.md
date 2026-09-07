# Fase H — Cobertura de stakeholder e risco de single-thread

Depende só da Fase A (`Contact` já existe, com `seniority_tier` inferido de
`role` desde a Fase C). Pode rodar em paralelo às demais fases, não depende
delas. Ver `engineering/roadmap.md` pro texto original dos requisitos e a
origem da escolha (convergência de Deal Strategist + Account Strategist).

## Mapa de capacidades (confirmado pelo usuário)

| Ordem | Módulo | Responsabilidade | Consulta a especialista |
|---|---|---|---|
| 1 | `outreach-touch-contact-link` | `OutreachTouch.contact_id` opcional — permite (nunca exige) atribuir um toque a um contato específico da conta. | Não (mecânico) |
| 2 | `contact-stance-field` | `Contact.stance` (enum aberto: `champion`/`neutro`/`detrator` — `None` = "não avaliado", nunca um 4º valor de string) — eixo de DISPOSIÇÃO, distinto de `seniority_tier` (eixo de AUTORIDADE). | Deal Strategist |
| 3 | `single-threaded-risk-signal` | Função pura — oportunidade qualificada+ OU conta com renovação próxima, com cobertura de contato fraca → sinaliza risco. Nunca muda status/dispara ação sozinha. | Deal Strategist + Account Strategist |
| 4 | `stakeholder-coverage-ui` | Sinal exposto na tela de Oportunidades — linguagem de decisão, nunca alarme genérico. | Sales Engineer |

## Módulo 1 — `outreach-touch-contact-link`

Mecânico, sem consulta a especialista.

### Implementação

- `core/models.py` — `OutreachTouch.contact_id: str | None = None`. Nunca
  obrigatório: toques antigos continuam válidos sem ele, e o rep pode
  registrar um toque sem saber (ou sem querer detalhar) com qual contato
  específico da conta falou.
- `core/db_models.py` — `OutreachTouchORM.contact_id` (nullable) — coluna
  nova adicionada automaticamente via `core/db.py::_add_missing_columns`
  em qualquer instalação existente, sem migração manual.
- `core/repository.py` — `save_outreach_touch`/`list_outreach_touches`
  atualizados pra ler/gravar o campo.
- `backend/routes_sync.py` — `OutreachTouchIn.contact_id` (opcional) no
  corpo de `POST .../outreach-touches`, repassado pro `OutreachTouch`
  construído na rota.

**Deliberadamente fora deste módulo**: nenhuma validação de que
`contact_id` referencia um `Contact` real, muito menos um `Contact` da
mesma `Company` da oportunidade. É só a "plumbing" — a checagem de
referência (e o próprio cálculo de cobertura) é responsabilidade do
módulo 3 (`single-threaded-risk-signal`).

### Achado da revisão de código

Nenhum — revisão aprovou sem achados Importantes/Críticos. Uma sugestão
não-bloqueante (comentário explicando a ausência de validação de
referência) foi aplicada.

### Teste

- `tests/test_persistence.py` (+1, +1 assert no teste existente): toque
  sem `contact_id` continua `None` por padrão; toque com `contact_id`
  round-trips corretamente.
- `tests/test_routes_sync.py` (+1): `POST .../outreach-touches` aceita e
  devolve `contact_id`.

### Critério de sucesso

- [x] `contact_id` nunca obrigatório — toda chamada existente (testes,
      rota) continua funcionando sem passar o campo.
- [x] Nenhuma validação de referência prematura — módulo 1 é só
      persistência do dado bruto.
- [x] Coluna nova adicionada sem migração manual (mesmo mecanismo já
      testado de `_add_missing_columns`).
- [x] Revisão de código sem achados Importantes/Críticos.

## Módulo 2 — `contact-stance-field`

**Consulta ao Deal Strategist** (antes de implementar):
- Três valores de referência, não mais: `champion`/`neutro`/`detrator`.
  Granularidade maior (ex. "champion forte/fraco") é ruído que ninguém
  preenche de forma consistente e que o módulo 3 não precisa.
- Sempre manual — diferente de `seniority_tier`, não existe texto de
  `role` que diga se a pessoa é favorável ao fornecedor; inferir seria o
  núcleo inventando informação que não tem.
- Default `None` ("não avaliado"), nunca um valor neutro assumido —
  ausência de dado é honesta, "neutro" fabricado não seria.
- `stance` e `seniority_tier` ficam CEGOS um ao outro no `Contact` — a
  combinação dos dois eixos (autoridade × disposição × contagem de
  threads) é responsabilidade só do módulo 3, nunca lógica aqui.

### Implementação

- `core/models.py` — `Contact.stance: str | None = None`, com docstring
  explicando a decisão (manual, sem inferência, sem default neutro,
  único caminho de escrita é `update_contact_stance`).
- `core/db_models.py` — `ContactORM.stance` (nullable) — adicionada
  automaticamente via `_add_missing_columns` em instalação existente.
- `core/repository.py` — `save_contact` reescrito de `_upsert` simples
  pra `sqlite_insert(...).on_conflict_do_update()` com `stance` excluído
  do `SET` (mesmo padrão de `save_company`/`renewal_date`): sem isso,
  todo `/sync` reverteria a avaliação manual do rep pra `None`, porque o
  `Contact` vindo do provider nunca carrega `stance`. Novo
  `update_contact_stance(session, contact_id, stance)` — única escrita
  real, coluna única (mesmo padrão de `update_company_renewal_date`).

**Deliberadamente fora deste módulo**: nenhuma rota HTTP expõe
`update_contact_stance` ainda — não existe tela de contatos no produto
hoje (achado ao planejar: a suposição inicial de "o rep edita isso onde
já registra nota pós-call" não corresponde a nenhuma tela real ainda).
Expor essa edição fica pro módulo 4 (`stakeholder-coverage-ui`) ou um
módulo dedicado, a decidir quando esse módulo for planejado.

### Achado da revisão de código

Nenhum Importante/Crítico. Revisão confirmou, campo a campo, que
`save_contact` exclui só `stance` do `SET` (nada mais foi derrubado do
upsert) e re-derivou o teste de TOCTOU de forma independente. Duas
sugestões não-bloqueantes: alinhar o vocabulário do roadmap/spec com o
docstring do model (aplicado acima) e confirmar que a ausência de rota
é rastreada como próximo módulo, não esquecimento (registrado acima).

### Teste

- `tests/test_persistence.py` (+3): `update_contact_stance` round-trips;
  devolve `None` pra id desconhecido; `save_contact` nunca reverte
  `stance` de um snapshot em memória desatualizado (mesma classe de
  TOCTOU já corrigida em `save_company`/`renewal_date` — a asserção
  também confirma que OUTRO campo, `phone`, É atualizado pelo snapshot
  desatualizado, provando que o upsert exclui só `stance`, não vira um
  no-op).

### Critério de sucesso

- [x] `stance` e `seniority_tier` nunca se misturam num campo/lógica só.
- [x] `stance` sobrevive a qualquer `/sync` — só `update_contact_stance`
      escreve essa coluna.
- [x] Nenhum valor "neutro" fabricado — ausência de avaliação é `None`,
      sempre.
- [x] Coluna nova adicionada sem migração manual.
- [x] Revisão de código sem achados Importantes/Críticos.

## Módulo 3 — `single-threaded-risk-signal`

**Consulta ao Deal Strategist + Account Strategist** (em paralelo,
divergiram em parte — reconciliado pelo engenheiro antes de implementar,
não pelos agentes):

- Deal Strategist: nunca inventar risco quando o dado é insuficiente —
  `contact_id` (módulo 1) é opcional, a maioria dos toques históricos não
  vai ter. "Zero toque com `contact_id` na janela" tem que devolver
  `None` (dado insuficiente), nunca virar "0 contato ativo" como se fosse
  fato observado.
- Account Strategist: gate amplo (qualquer status ativo, não só
  `qualified+`) e independente da cadência de QBR — são eixos ortogonais,
  mesmo princípio de `compute_severity_band` vs. `compute_account_health`
  nunca colapsarem. Propôs também reusar o vocabulário
  "vermelha"/"amarela" de `compute_account_health` pro retorno.
- **Reconciliação**: mantida a guarda de dado insuficiente do Deal
  Strategist (mais alinhada ao princípio já repetido no código —
  `is_aging_opportunity`, `compute_silence_signal` — de nunca fabricar
  sinal a partir de ausência de dado); mantido o gate amplo do Account
  Strategist (a própria guarda de dado insuficiente já filtra o ruído de
  início de funil que motivaria um corte por estágio); REJEITADO o reuso
  do vocabulário de severidade — misturaria este sinal (cobertura) com
  saúde de conta (outro eixo, os dois concordam que nunca deve colapsar),
  substituído por `reasons: tuple[str, ...]` com dois motivos
  independentes, mesmo princípio de `SilenceSignal` (nunca colapsar duas
  causas num motivo só).
- Ambos convergiram: nunca mascarar `compute_silence_signal` (fatos
  ortogonais — "ninguém respondeu" vs. "poucas pessoas cobrem a conta"),
  `stance=detrator` fica fora de escopo (é sobre qualidade da relação,
  não cobertura — sinal futuro separado).

### Implementação

- `core/opportunity_engine.py` — `ThreadingRiskSignal(reasons, active_contact_count,
  has_active_decisor)`, `SINGLE_THREADED_RISK`/`NO_ECONOMIC_BUYER_CONTACT`,
  `_ACTIVE_CONTACT_WINDOW_DAYS = 90`,
  `compute_threading_risk_signal(status, contacts, touches, now, window_days)`
  — função pura, nunca chama `update_opportunity_status`. `contacts` é
  sempre da CONTA inteira; `touches` é sempre da OPORTUNIDADE específica
  — a mesma conta com múltiplas oportunidades ativas pode dar resultados
  diferentes por chamada, de propósito (rollup "risco da conta" fica pro
  chamador, se algum dia precisar).

### Achado da revisão de código

Nenhum Importante/Crítico — revisão re-derivou a guarda de dado
insuficiente, o tratamento de `contact_id` desconhecido (nunca quebra,
conta pra `SINGLE_THREADED_RISK` mas nunca pra decisor) e a semântica de
fronteira da janela (`>=`, inclusiva, provada por teste) diretamente do
código, não dos nomes dos testes. Uma sugestão não-bloqueante aplicada:
normalização de timezone extraída pra uma função local, pra ficar mais
fácil de ler que nos `is_zombie_opportunity`/`is_aging_opportunity`.

### Teste

- `tests/test_threading_risk_signal.py` (12 testes): `dismissed` nunca
  sinaliza; toques sem `contact_id` (ou nenhum toque) é dado
  insuficiente, não risco; 1 contato ativo com/sem decisor; 2 contatos
  ativos com/sem decisor; `contact_id` desconhecido nunca quebra (conta
  como não-decisor); fronteira exata da janela (dentro e fora); todos os
  status ativos são elegíveis exceto `dismissed`; `window_days`
  customizado é realmente usado.

### Critério de sucesso

- [x] Nenhuma transição de `Opportunity.status` acontece a partir deste
      módulo — só leitura/sugestão, mesmo padrão dos módulos 6-8 da
      Fase G.
- [x] Dado insuficiente nunca vira risco fabricado.
- [x] As duas causas nunca colapsam num motivo só.
- [x] Nunca reusa vocabulário de saúde de conta (decisão explícita da
      reconciliação).
- [x] `contact_id` desconhecido nunca derruba a função.
- [x] Revisão de código sem achados Importantes/Críticos.

## Módulo 4 — `stakeholder-coverage-ui`

Último módulo da fase. Primeira rota/UI nova desde o módulo 1 — sync pra
cópia instalada + verificação ao vivo exigidas.

**Consulta ao Sales Engineer** (antes de implementar — cobrindo o gap
real descoberto ao planejar: não existe tela de contatos nenhuma no
produto hoje, então sem alguma UI o sinal do módulo 3 nunca teria dado
suficiente pra calcular nada, pra sempre):

- **Dropdown mínimo, não tela de contatos completa.** Menor esforço que
  destrava o sinal: um `<select>` opcional dentro do fluxo de "marcar
  como enviado" já existente (Fase G), não uma tela nova de gestão de
  contatos (isso fica pra quando "gestão de contatos" virar prioridade
  própria — inclui edição de `stance`/`seniority_tier`, ainda sem rota).
- **Onde o sinal aparece**: no painel de detalhe, ao lado da "próxima
  ação sugerida" — nunca badge na linha da tabela (é sinal qualitativo
  que precisa de contexto, e a tabela já compete por espaço com badges
  de severidade/saúde).
- **Tom**: convite, nunca alarme — título "Vale ampliar os contatos
  aqui", nunca "Risco: single-thread".
- **Frase por combinação de motivos** (nunca concatenar as duas — vira
  lista burocrática em vez de síntese):
  - só `single_threaded_risk`: "Só um contato ativo tem recebido seus
    toques recentes. Vale envolver mais uma pessoa da conta."
  - só `no_economic_buyer_contact`: "Nenhum decisor apareceu nos toques
    recentes. Vale trazer quem decide pra conversa."
  - os dois juntos: "Os toques recentes chegaram a uma pessoa só, e não
    a um decisor. Bom momento pra ampliar quem participa da conversa."
- **UX do dropdown**: sempre visível, nunca obrigatório, label discreta
  ("Contato (opcional)"), placeholder "Não atribuído"; pré-seleciona
  automaticamente o `contact_id` do último `OutreachTouch` da mesma
  oportunidade — rep só reabre quando quer trocar de pessoa. `<select>`
  nativo, sem busca/autocomplete (lista curta por conta).

### Implementação

- `backend/routes_sync.py`:
  - `GET /companies/{company_id}/contacts` (`ContactOut(id, name)`) —
    só leitura, só o que a UI precisa pro dropdown, nunca `stance`/
    `seniority_tier` (não é endpoint de gestão de contatos).
  - `NextSuggestedTouchOut` ganha `threading_risk_reasons`,
    `active_contact_count`, `has_active_decisor` (do módulo 3) e
    `last_contact_id` (contato do toque mais recente por `sent_at`,
    pra UI pré-selecionar o dropdown). `threading_risk_reasons` NUNCA é
    suprimido por `cap_diario_atingido` (diferente do `silence_reason`)
    — é sobre cobertura, não sobre "aja agora", não contradiz "espere
    até amanhã".
- `frontend/src/api.ts` — `getCompanyContacts`, `NextSuggestedTouch`
  ganha os 4 campos novos, `markOutreachTouchSent` ganha parâmetro
  `contactId`.
- `frontend/src/OpportunityTable.tsx` — `threadingRiskPhrase(reasons)`,
  `threadingBanner` (aditivo em cima de todos os 4 estados de cadência,
  mesmo padrão de `silenceBanner`), dropdown de contato no fluxo
  copiar→marcar-como-enviado, `selectedContactId` reinicializado a
  cada `load()` a partir de `lastContactId`.

### Achado da revisão de código (1 Importante, corrigido)

Nenhum teste provava que `last_contact_id` reflete o toque
GENUINAMENTE mais recente por `sent_at` quando esse toque não tem
`contact_id` mas um toque MAIS ANTIGO tem — o código já estava correto
(`max(touches, key=lambda t: t.sent_at)`, nunca busca um toque antigo
com dado), mas nada pegaria uma regressão que "ajudasse" a cair pro
toque antigo. Adicionado teste com toques fora de ordem de inserção,
provando que a escolha usa `sent_at`, não ordem de inserção nem "acha
o mais recente com contato". Sugestão não-bloqueante aplicada:
comentário explicando que a falha silenciosa ao buscar contatos é
deliberada (dropdown é best-effort, nunca bloqueia o fluxo principal).

### Não objetivo deste módulo

- Tela de gestão de contatos (listar/editar `stance`/`seniority_tier`
  via UI) — fica pra quando isso virar prioridade própria.
- Badge de risco na linha da tabela — decisão explícita do Sales
  Engineer, evita competir por espaço com os badges já existentes.
- Validação de `contact_id` contra `Contact`/`company_id` — continua
  responsabilidade futura, não deste módulo (módulo 1 já documentou
  essa decisão).

### Teste

- `tests/test_routes_sync.py` (+5, e 4 asserts existentes atualizados
  pros campos novos): rota de contatos devolve id/nome; rota de
  contatos vazia pra conta sem contato; `threading_risk_reasons`/
  `active_contact_count`/`has_active_decisor`/`last_contact_id`
  presentes quando há dado suficiente; ausentes (defaults) quando não
  há; `last_contact_id` reflete o toque mais recente por `sent_at`
  mesmo fora de ordem de inserção e mesmo quando esse toque não tem
  contato (achado da revisão de código).
- `npx tsc --noEmit` e `npx vitest run` (30 testes) sem regressão.

### Critério de sucesso

- [x] Sinal do módulo 3 tem, pela primeira vez, uma forma real de
      receber dado (`contact_id` atribuível via UI) — deixa de ser uma
      função permanentemente "insuficiente por design".
- [x] Nenhuma tela de gestão de contatos criada fora de escopo.
- [x] `threading_risk_reasons` nunca contradiz `cap_diario_atingido`.
- [x] `last_contact_id` reflete o toque genuinamente mais recente,
      provado por teste com dado fora de ordem.
- [x] Sincronizado pra cópia instalada e verificado ao vivo.
- [x] Revisão de código sem achados Importantes/Críticos pendentes.
