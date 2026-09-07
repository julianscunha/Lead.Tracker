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
