# Fase D — Dashboard acionável

Spec viva desta fase (`spec-driven-development`) — atualizada a cada módulo
entregue, não escrita de uma vez no início. Ver `docs/roadmap.md` pro texto
original dos requisitos; este documento registra as decisões de como
implementar cada um, o porquê, e o que cada módulo entrega.

## Capability map (consulta ao agente `Plan`)

Fase D bundla várias capacidades testáveis independentemente sobre uma
arquitetura de agregação compartilhada (snapshot diário) — passou pelo
Phase 0 (scope check) do `spec-driven-development` antes de qualquer código.

| Ordem | Módulo | Responsabilidade |
|---|---|---|
| 0 | `status-transition` | Rota + UI de mudança manual de status (gap descoberto durante o planejamento — sem isso, funil/aging nunca teriam dado real pra mostrar). |
| 1 | `status-history-recording` | Fundido no módulo 0 — `OpportunityStatusChange` grava em toda transição real. |
| 2 | `daily-snapshot-table` | Tabela de snapshot diário, recalculada no fim de todo `POST /sync`. |
| 3 | `zombie-detection` | Oportunidade parada há muito tempo no mesmo estágio, exclusão de métrica de pipeline saudável. |
| 4 | `snapshot-aggregator` | `dashboard_metrics.py` passa a ler do snapshot: funil+conversão, potencial ponderado, cortes por rep/segmento/fonte. |
| 5 | `aging-sla-alerts` | Oportunidade em `detected` há mais de N dias — alerta configurável. |
| 6 | `dismissal-reason-taxonomy` | Motivo categorizado de `dismissed`. |
| 7 | `rep-target-coverage` | Meta manual por rep/período + coverage ratio. |
| 8 | `dashboard-ui-kpi-cards` | Frontend: cards com explicação inline de cada número. |

## Módulo 0 — Transição manual de status

### Objetivo

Pré-requisito descoberto durante o planejamento, não um item do roadmap:
antes desta fase, **nenhuma rota nem tela mudava `Opportunity.status`** — só
a criação, sempre em `detected`. Funil-com-conversão e aging (módulos
4 e 5) dependem de oportunidades realmente mudarem de status; sem este
módulo, toda a Fase D nasceria medindo dado degenerado (tudo sempre
`detected`).

### Decisões tomadas (consulta a Plan e Sales Coach, divergentes)

**Achado crítico do agente `Plan`, antes de desenhar a rota**: o motor
(`core/opportunity_engine.py::_build_opportunity`) sempre constrói
`Opportunity` com `status=DETECTED`, e o id da oportunidade é
determinístico — `core/repository.py::save_opportunity` incluía `status`
no `SET` do upsert atômico, então rodar `/sync` de novo pra uma empresa
cujo portfólio não mudou resetaria pra `detected` qualquer oportunidade já
avançada manualmente. Bug pré-existente, nunca disparado porque nunca
havia como mudar status. **Corrigido antes de adicionar a rota**: `status`
só entra no `INSERT` inicial, nunca no `SET` de atualização — mesmo padrão
de `scope_note`/`criticality`/`renewal_date` (Fase C).

**Sequência estrita vs. dropdown livre — Plan e Sales Coach divergiram,
usuário decidiu**: Plan recomendou validar transição contra a sequência
documentada no CLAUDE.md (só avançar 1 estágio por vez). Sales Coach
argumentou que isso produz "pipeline mentiroso" — o rep de um deal fechado
rápido simplesmente atualiza tudo no fim (ou evita mexer), e sequência
rígida não impede o gaming, só cria fricção sem valor. Decisão final
(escolha do usuário): **dropdown livre, sem máquina de estados no
domínio**, mas exige uma `note` obrigatória (`OpportunityStatusChange.note`,
campo novo) quando:
- a transição avança 2+ estágios de uma vez (`detected→qualified→reviewed→
  contacted→opportunity`, "dismissed" fora da sequência linear — é
  terminal), ou
- reabre uma oportunidade `dismissed` pra qualquer outro estágio.

Avançar pra `dismissed` a partir de qualquer estágio nunca exige nota —
sair do funil não é um "salto", é uma saída.

### Achado da revisão de código — TOCTOU na validação da rota

Primeira versão da rota lia o status atual (`get_opportunity`), decidia se
precisava de justificativa, e só então chamava `update_opportunity_status`
(que fazia sua própria busca separada) — entre as duas leituras, o status
real podia mudar (ex. duas abas do navegador), fazendo a rota decidir com
base num status já obsoleto. **Corrigido**: a checagem de justificativa
roda dentro de `update_opportunity_status`, contra a MESMA linha que a
função acabou de buscar — nunca uma leitura separada antes de chamar. A
função levanta `StatusChangeRequiresJustificationError` (novo, em
`core/models.py`, mesmo padrão de `RuleError`), capturada pela rota e
convertida em 422 amigável. Regressão coberta por
`test_update_opportunity_status_checks_justification_against_the_real_current_status`.

### Design

- `core/models.py`: `OpportunityStatusChange` ganha `note: str | None`.
  Nova exceção `StatusChangeRequiresJustificationError`.
- `core/db_models.py`: `OpportunityStatusChangeORM` ganha coluna `note`.
- `core/opportunity_engine.py`: `requires_status_change_justification(old,
  new) -> bool` — função pura, `_STAGE_ORDER` de 5 estágios (sem
  `dismissed`, que é terminal).
- `core/repository.py`:
  - `save_opportunity` (motor): `status` excluído do `SET` do upsert.
  - `update_opportunity_status(session, opportunity_id, new_status, note)`
    — único caminho de escrita de `status` após a criação. Busca a linha,
    decide justificativa contra ela mesma, grava `Opportunity.status` e
    `OpportunityStatusChangeORM` na mesma transação (histórico até aqui
    existia no modelo mas nunca era escrito em código real). No-op (mesmo
    status) não grava histórico.
  - `save_opportunity_status_change` marcado como helper de
    teste/fixture — nunca usar pra transição real (reabriria o TOCTOU).
  - Nova `get_opportunity(session, opportunity_id)`.
- `backend/routes_sync.py`: `PATCH /opportunities/{id}/status`
  (`OpportunityStatusIn`: `new_status` Literal das 6 opções + `note`
  opcional) — captura `StatusChangeRequiresJustificationError` → 422, `None`
  → 404.
- Frontend: `StatusTransition` (`OpportunityTable.tsx`) — dropdown de
  status na linha expansível, campo de justificativa condicional (mesma
  regra duplicada em TS só pra feedback imediato — backend é a fonte da
  verdade). Reaproveita o callback `onRowUpdated` (renomeado de
  `onQualificationUpdated`, já que agora serve status/severidade/QBR
  igualmente).

### Não objetivo deste módulo

- Nenhuma máquina de estados no domínio — dropdown livre, fricção só via
  justificativa obrigatória em saltos grandes.
- Nenhuma UI de histórico de status ainda (só a gravação) — consumido
  pelos módulos 2/3/5 (snapshot, zumbi, aging), não exibido diretamente.

### Teste

- `requires_status_change_justification`: 1 estágio (falso), 2+ estágios
  (verdadeiro), retroceder (falso), reabrir dismissed (sempre verdadeiro),
  avançar pra dismissed (falso), mesmo status (falso).
- `update_opportunity_status`: round-trip com nota; `None` pra id
  inexistente; no-op não grava histórico; regressão do TOCTOU (decide
  contra o status real, não uma crença desatualizada do chamador).
- `save_opportunity`: nunca reseta status avançado manualmente num 2º sync.
- Rota: avanço de 1 estágio sem nota (200); salto de 2+ sem nota (422) e
  com nota (200); 404 amigável pra id inexistente.

### Critério de sucesso

- [x] `status` nunca mais é resetado pelo motor após a criação.
- [x] `PATCH /opportunities/{id}/status` funcional, 422 amigável quando
      falta justificativa, 404 amigável se não existir.
- [x] Checagem de justificativa imune a TOCTOU (decide contra a leitura
      que a própria escrita usa).
- [x] UI com dropdown de status + campo de justificativa condicional.
- [x] Suíte completa passa (backend + frontend), verificado ao vivo contra
      o módulo instalado.

## Módulos 2+3 — Snapshot diário e detecção de zumbi

Implementados juntos (decisão do agente `Plan`): o esquema de snapshot já
embute a coluna `is_zombie`, então não fazia sentido entregar a tabela sem
a lógica que a preenche.

### Objetivo

Fundação de leitura pro resto da Fase D (funil/potencial ponderado/cortes,
módulo 4, e aging, módulo 5): uma tabela de snapshot diário, recalculada
por inteiro no fim de todo `POST /sync` — nunca uma agregação em tempo real
nas tabelas transacionais (decisão de arquitetura do roadmap, evita
reescrever histórico quando um rep muda de território e evita 3 cálculos
divergentes de MTD/YTD). "Zumbi" é uma oportunidade parada há muito tempo
no MESMO estágio — conceito à parte do SLA de aging (módulo 5), que ainda
não existe.

### Achado crítico da revisão de código — `synced_at` não serve de proxy de "última atividade"

Primeira versão usava `Opportunity.synced_at` como fallback de
`last_touch_at` quando não havia `OpportunityStatusChange` (o caso comum:
o módulo de transição de status acabou de ser criado, então praticamente
nenhuma oportunidade tem histórico ainda). Problema: `synced_at` é
reescrito a cada `/sync` que ainda detecta a mesma oportunidade
(`_build_opportunity` sempre gera um objeto novo com `synced_at=agora`, e
até este achado `save_opportunity` incluía a coluna no `SET` do upsert).
Resultado: uma oportunidade nunca revisada por ninguém, parada em
`detected` há 6 meses, nunca seria marcada zumbi — o motor "renovava" o
timestamp a cada ciclo de sync, neutralizando a feature exatamente pra
população que ela deveria capturar.

**Correção**: novo campo `Opportunity.first_detected_at`, gravado só no
`INSERT` inicial (mesmo padrão insert-only de `status`/`scope_note`) —
`save_opportunity` nunca mais o reescreve depois da criação, mesmo quando
o motor re-detecta a mesma oportunidade em sync futuros. Fallback de zumbi
passa a usar esse campo, nunca `synced_at`.

### Outros achados da revisão

- **N+1 corrigido**: a primeira versão buscava `OpportunityStatusChange`
  numa query por oportunidade, dentro do loop de recálculo — rodando sobre
  TODAS as oportunidades do banco a cada `/sync`, isso escalaria mal
  (diferente do N+1 já aceito em `_account_health_map`, que não faz
  consulta nenhuma dentro do loop). Corrigido: uma única query busca todo
  `OpportunityStatusChange`, agrupado em memória por `opportunity_id`.
- **Corrida com escrita concorrente**: aceitável, documentado no docstring
  de `recompute_daily_snapshot` — não é a mesma classe de TOCTOU já
  corrigida 3 vezes nesta fase (aquelas eram lost-update na MESMA linha;
  aqui é uma foto aproximada de fim de sync que se autocorrige no ciclo
  seguinte).
- **Recalcular mesmo sem nenhuma fonte sincronizada**: intencional, não
  gatear em `results` não vazio — um dia com todas as fontes desligadas
  mas com transições manuais de status (`update_opportunity_status`) ainda
  precisa de snapshot atualizado.

### Design

- `core/models.py`: `Opportunity.first_detected_at` novo (insert-only).
  `OpportunitySnapshot` (Pydantic).
- `core/db_models.py`: `OpportunityORM.first_detected_at`.
  `OpportunitySnapshotORM` — `id` determinístico
  (`opportunity_id:snapshot_date`), uma linha por (oportunidade, dia).
- `core/opportunity_engine.py`: `is_zombie_opportunity(status,
  last_touch_at, now) -> bool` — pura, `dismissed` nunca é zumbi, 30 dias
  fixo (`_ZOMBIE_DAYS`, piso conservador do Pipeline Analyst enquanto não
  há histórico suficiente pra calibrar por mediana real de estágio).
- `core/repository.py`:
  - `save_opportunity`: `first_detected_at` excluído do `SET` do upsert.
  - `recompute_daily_snapshot(session, today=None)` — 1 query pra todas as
    oportunidades, 1 query pra todas as empresas, 1 query pra todo
    `OpportunityStatusChange` (agrupado em memória), upsert atômico por
    oportunidade.
  - `list_latest_snapshot(session)` — devolve a data mais recente
    disponível, nunca força "hoje" (se `/sync` não rodou ainda hoje, mostra
    o último dia calculado em vez de fingir dado inexistente).
- `backend/sync.py`: `recompute_daily_snapshot` chamado no fim de
  `sync_all_enabled_sources`, sempre (mesmo com zero fontes sincronizadas).

### Não objetivo destes módulos

- Nenhuma UI ainda — só a infraestrutura de leitura (módulo 8 consome).
- Nenhum cálculo de funil/conversão/potencial ponderado aqui — isso é o
  módulo 4 (`snapshot-aggregator`), que lê desta tabela.

### Teste

- `is_zombie_opportunity`: estagnação além de 30 dias, `dismissed` nunca
  zumbi, datetime naive não quebra.
- `recompute_daily_snapshot`: reflete estado atual (potencial/confiança/
  rep/segmento/fonte/zumbi); idempotente no mesmo dia (upsert, não
  duplica); zumbi via fallback de `first_detected_at`; **regressão do
  achado crítico** — zumbi sobrevive a um 2º `save_opportunity` (simulando
  re-sync) que só reescreve `synced_at`, nunca `first_detected_at`.
- `list_latest_snapshot`: vazio quando nunca rodou.
- `sync_all_enabled_sources`: recalcula snapshot refletindo oportunidade
  gerada nesta mesma chamada.
- `test_db_table_registration`: contagem de tabelas atualizada (10 → 11).

### Critério de sucesso

- [x] Snapshot recalculado no fim de todo `/sync`, idempotente no mesmo
      dia.
- [x] Zumbi nunca "se cura" sozinho por re-sync automático — só sai desse
      estado por transição manual de status ou por avançar de estágio.
- [x] Sem N+1 sensível a volume de oportunidades históricas.
- [x] Dashboard (módulo 4, ainda não implementado) terá de onde ler sem
      tocar as tabelas transacionais.
- [x] Suíte completa passa, verificado ao vivo contra o módulo instalado
      (`POST /sync` roda sem erro em banco vazio, tabela nova criada).

## Módulo 4 — Agregador do dashboard via snapshot

### Objetivo

`GET /dashboard-metrics` passa a ler do snapshot diário (módulos 2+3) pras
métricas novas da Fase D: potencial ponderado (bruto vs. avaliado vs.
estimado), cortes por rep/segmento/fonte (sempre segmentados, nunca total
misturado), contagem de zumbi, e alcance do funil. Funções antigas que já
operavam em `list[Opportunity]`/`list[Company]` (distribuição por
fabricante, funil por contagem simples) ficam intactas — não fazem parte
do escopo desta fase, não têm problema de histórico/velocity que o
snapshot resolveria.

### Decisão de metodologia (consulta ao Pipeline Analyst) — "alcance", nunca "conversão"

O snapshot só guarda o estágio ATUAL de cada oportunidade, não o histórico
completo de por quais estágios ela já passou (`OpportunityStatusChange`
só existe pra transições manuais, a maioria das oportunidades ainda não
tem nenhuma). Calcular "taxa de conversão por etapa" de verdade exigiria
uma coorte fechada num período — dado que não existe ainda.

**Decisão**: `funnel_reach` — alcance cumulativo do snapshot mais recente,
nunca chamado de "conversão" em variável, docstring ou campo de API.
`reach_count[estágio]` = quantas oportunidades estão HOJE nesse estágio ou
além; `reach_ratio_from_previous[i] = reach_count[i] / reach_count[i-1]`.
É uma foto transversal (mistura oportunidades de idades bem diferentes),
não uma taxa histórica de coorte — limitação conhecida, documentada, não
escondida. Migrar pra conversão de coorte de verdade quando
`OpportunityStatusChange` tiver massa suficiente (o Pipeline Analyst
sugeriu um piso explícito: >70% das oportunidades fechadas no período com
pelo menos 1 transição registrada) — até lá, a UI (módulo 8) precisa
rotular como "Alcance do funil (visão atual)", nunca "Taxa de conversão".

### Design

- `core/dashboard_metrics.py`:
  - `exclude_zombies(snapshot)` — filtro simples, usado antes de qualquer
    métrica de "pipeline saudável" (blindagem obrigatória do roadmap).
  - `compute_weighted_potential(snapshot)` — bruto / ponderado-avaliado
    (só `confidence_score` real) / ponderado-estimado (+ as sem
    `confidence_score`, confiança padrão 0.5) — nunca misturado sem rótulo
    (decisão do Pipeline Analyst, mesma da cadência de QBR).
  - `potential_by_rep/segment/source(snapshot)` — sempre segmentado; linha
    sem a chave fica de fora, nunca vira categoria "sem atribuição"
    fingida.
  - `count_zombie_opportunities(snapshot)`.
  - `funnel_reach(snapshot)` — ver decisão de metodologia acima.
- `backend/routes_sync.py::get_dashboard_metrics`: busca
  `list_latest_snapshot`; `exclude_zombies` aplicado antes de
  `compute_weighted_potential`/`potential_by_*`, mas NÃO antes de
  `funnel_reach` (funil mostra a posição real de toda oportunidade, zumbi
  ou não — só as métricas de pipeline saudável em R$ excluem).
  `zombie_count` exposto separado, sobre o snapshot completo, pra UI
  mostrar o número em vez de escondê-lo.

### Achado da revisão de código, registrado pra quando o módulo 8 (UI) for implementado

A soma de `potential_by_rep`/`segment`/`source` pode legitimamente ficar
abaixo do `financial_potential_total` do topo (KPI antigo, soma tudo) —
oportunidade sem `rep_id`/`segment`/`source` conta no total mas não entra
em nenhum corte (decisão correta, "nunca inventar categoria sem
atribuição"). Isso vai parecer inconsistência pra quem olha os dois
números lado a lado. **Não objetivo desta fatia** (é backend puro) —
registrado aqui pra o módulo 8 tratar com uma nota explícita na UI (ex.:
"soma inclui oportunidades sem responsável atribuído").

### Não objetivo deste módulo

- Nenhuma migração das métricas antigas (distribuição por fabricante,
  funil por contagem simples) pro snapshot — não têm problema de
  histórico/velocity que o snapshot resolveria, ficam como estão.
- Nenhuma UI ainda — só os novos campos na resposta de
  `GET /dashboard-metrics` (módulo 8 consome).

### Teste

- `exclude_zombies`, `compute_weighted_potential` (avaliado vs. estimado,
  `financial_potential=0.0` não é tratado como falsy), `potential_by_*`
  (sempre segmentado, ignora linha sem chave), `count_zombie_opportunities`.
- `funnel_reach`: cumulativo com `dismissed` fora; ratio `None` no
  primeiro estágio e em lista vazia (nunca `ZeroDivisionError`); caso-limite
  de todas as oportunidades no último estágio (sequência não-crescente,
  achado da revisão de código).
- Rota: estado vazio honesto (zeros, nunca `None`/erro); snapshot real
  refletido, zumbi excluído do ponderado e dos cortes mas contado à parte.

### Critério de sucesso

- [x] `GET /dashboard-metrics` lê do snapshot pras métricas novas, nunca
      em tempo real.
- [x] Nenhuma referência a "conversão"/"conversion" em `funnel_reach` (só
      "alcance"/"reach") — confirmado por grep na revisão de código.
- [x] Zumbi nunca entra em potencial ponderado nem cortes, mas é contado
      e exposto.
- [x] Suíte completa passa, incluindo o caso-limite de funil todo no
      último estágio.

## Módulo 5 — SLA de triagem (aging)

Oportunidade parada em `detected` (nunca avançou nem foi descartada) por
mais de N dias — sinal distinto de "zumbi" (módulos 2+3): zumbi é sobre
qualquer estágio parado há muito tempo (30 dias fixos, decisão de
severidade de pipeline), aging é especificamente sobre triagem inicial
nunca acontecer, com prazo configurável pelo usuário (`AGING_SLA_DAYS`,
padrão 7 dias) — os dois nunca compartilham a mesma constante de
propósito, mesmo quando os dois eventualmente disparam pra uma mesma
oportunidade muito antiga.

`is_aging_opportunity`/`parse_aging_sla_days` (`core/opportunity_engine.py`)
são funções puras: status precisa ser exatamente `detected` e
`first_detected_at` (o mesmo carimbo insert-only do módulo 2+3, nunca
`synced_at`) precisa estar a mais de `sla_days` dias de `now`.
`parse_aging_sla_days` nunca lança em config inválida — `ValueError`/valor
≤0 caem no default de 7, mesmo princípio de "config quebrada nunca derruba
o módulo" já aplicado em outras leituras de `.env`.

Configuração via `GET`/`PUT /settings/config/aging-sla-days`, path de 2
segmentos deliberadamente (evita qualquer ambiguidade com o catch-all
`PUT /settings/{source_id}` já existente). `is_aging` é computado por
requisição em cada rota que devolve `OpportunityOut` (nunca persistido —
mesma decision de não pré-computar booleano derivável, evita
dessincronizar do relógio). `aging_count`/`aging_sla_days` entram no
`GET /dashboard-metrics`, lidos do mesmo snapshot diário do módulo 4.

### Não objetivo deste módulo

- UI: nenhum badge/indicador visual de "atrasada" na tabela de
  oportunidades ainda — só o campo `is_aging` na API (módulo 8 consome,
  mesma decisão dos módulos 2-4).

### Teste

- `is_aging_opportunity`/`parse_aging_sla_days`: status errado nunca conta,
  limite exato do SLA, config ausente/inválida cai no default.
- `count_aging_opportunities`: só conta `detected` além do SLA no snapshot.
- Rotas: `GET`/`PUT /config/aging-sla-days` round-trip e rejeita valor
  não-positivo; `is_aging` aparece correto em `GET /opportunities`;
  `aging_count`/`aging_sla_days` aparecem em `GET /dashboard-metrics`.

### Critério de sucesso

- [x] SLA configurável, nunca hardcoded, com default seguro.
- [x] `is_aging` nunca confundido com "zumbi" (constantes/funções
      inteiramente separadas).
- [x] Verificado ao vivo contra a cópia instalada do módulo (`curl` +
      Playwright): dashboard reflete `aging_count`/`zombie_count`
      corretos com dado fictício semeado.

## Módulo 6 — Motivo categorizado de descarte

`dismissed` sem motivo categorizado era um beco sem saída pra qualquer
relatório futuro de "por que perdemos oportunidades" — decisão consultada
com o agente `Pipeline Analyst` (ver histórico da sessão): taxonomia de 8
valores proposta, mas o roadmap (`docs/roadmap.md`, linha ~273) já
especificava 4 categorias explícitas de uma rodada de persona anterior
("sem evidência / sem fit / cliente não qualificado / falso positivo de
regra") — priorizei o roadmap já vetado por cima da sugestão nova do
agente, adicionando só `OTHER` como escape hatch (recomendação do próprio
Pipeline Analyst pra fechar o enum sem forçar categorização errada).
`DismissalReason` final: `NO_EVIDENCE`, `NOT_FIT`, `NOT_QUALIFIED`,
`FALSE_POSITIVE`, `OTHER`.

`update_opportunity_status` (`core/repository.py`) levanta
`DismissalReasonRequiredError` se `new_status == DISMISSED` sem
`dismissal_reason` — mesmo padrão TOCTOU de `StatusChangeRequiresJustificationError`:
decide contra a MESMA linha que acabou de buscar, nunca uma leitura
separada da rota. `Opportunity.dismissal_reason` é limpo pra `None` ao
reabrir (só faz sentido enquanto `status==dismissed`); `save_opportunity`
(caminho do motor) exclui a coluna do `SET` do upsert, mesmo padrão
insert-protected de `status`/`first_detected_at`/`scope_note`.

**Achado da revisão de código** (Important): guardar o motivo só em
`Opportunity.dismissal_reason` — que é limpo ao reabrir — apagava
irrecuperavelmente o motivo de um descarte anterior assim que a
oportunidade fosse reaberta e descartada de novo com outro motivo,
inviabilizando exatamente o relatório histórico que é a razão de existir
do campo. Corrigido gravando o motivo também na linha de histórico
imutável (`OpportunityStatusChange.dismissal_reason`), nunca limpa —
cada descarte passado continua consultável mesmo depois de reaberto.
Segundo achado (Important): faltava o teste de resync-safety pro campo
novo (mesma classe de bug já corrigida 3x nesta fase pra outras colunas
protegidas) — adicionado.

Frontend (`OpportunityTable.tsx`): dropdown de motivo aparece só quando o
status selecionado é "Descartada", bloqueia "Confirmar mudança" até um
valor ser escolhido; motivo atual é exibido como texto abaixo do seletor
quando a oportunidade já está descartada (fecha o ciclo do dado — sem
isso a categorização ficava invisível depois de salva).

### Não objetivo deste módulo

- Nenhuma agregação/relatório de "por que perdemos oportunidades" ainda —
  só a captura estruturada. Consumir isso no dashboard fica pra uma fatia
  futura fora do capability map original desta fase.

### Teste

- `update_opportunity_status`: exige motivo pra `dismissed`, persiste,
  limpa ao reabrir, sobrevive a um 2º `/sync` (resync-safety), histórico
  preserva o motivo de descartes anteriores após reabrir e descartar de
  novo com outro motivo.
- Rota: 422 sem motivo, motivo aceito e retornado, `dismissal_reason: null`
  na resposta ao reabrir. Enum fechado via `Literal` na fronteira HTTP —
  string arbitrária nunca chega ao domínio.

### Critério de sucesso

- [x] Enum fechado, nunca texto livre.
- [x] Motivo histórico nunca perdido em ciclos reabrir→descartar de novo.
- [x] `save_opportunity` (motor) nunca reseta o motivo num resync.
- [x] Suíte completa (backend + frontend) e revisão de código sem
      pendências abertas.

## Módulo 7 — Meta e cobertura por rep/período

Roadmap: "sem meta configurada, 'potencial financeiro total' é número sem
contexto" — cadastro manual de meta comercial por rep/período (nunca vem
de fonte externa), pra calcular `coverage_ratio = pipeline atual / meta`.
Escopo desta fatia: só nível de **rep** (o nome do próprio módulo no
capability map é `rep-target-coverage`, não `rep-segment-target-coverage`)
— meta por segmento fica registrada aqui como extensão possível, não
construída (YAGNI até haver pedido real).

`PeriodType` (mensal/trimestral, confirmado na consulta de capability map
do início da Fase D) + `current_period_key` (`core/opportunity_engine.py`)
gera o rótulo do período calendário corrente — trimestre é sempre
calendário fixo (jan-mar=Q1, ...), nunca "trailing 90 dias" (meta
comercial é pactuada contra calendário fiscal, não janela móvel).
`rep_target_id` gera um id determinístico (mesmo padrão de
`_generate_opportunity_id`) a partir de `(rep_id, period_type, period_key)`
— recadastrar meta pro mesmo rep+período é upsert via `session.merge`,
nunca cria uma 2ª meta concorrente.

`compute_rep_coverage` (`core/dashboard_metrics.py`) é a peça que
implementa a blindagem do roadmap: rep sem meta cadastrada pro período
nunca vira meta=0 (isso infla um "déficit" fictício) — `coverage_ratio`
fica `None`, e o `target` também fica `None` (distinto de uma meta
explicitamente cadastrada como 0, que mostra `target=0.0` mas ainda assim
`coverage_ratio=None`, nunca `ZeroDivisionError`). Um rep com meta
cadastrada mas pipeline zerado no período também aparece na lista — 0% de
cobertura é dado real, bem diferente de "sem meta definida".

`GET /dashboard-metrics` ganhou o query param `period_type` (default
`monthly`); o `period_key` usado pra buscar metas é sempre calculado como
"hoje" via `current_period_key`, nunca aceito do cliente — evita uma
inconsistência entre "que período o dashboard está olhando" e "que
período a URL pede". `POST /rep-targets` já aceita `period_key` do
cliente (é cadastro manual, não "hoje"), o que abre uma janela de
inconsistência diferente — ver achado da revisão de código abaixo.

**Achados da revisão de código** (2, Important, ambos corrigidos):
1. `RepTargetIn.period_key` era texto livre sem validação de formato —
   um typo (`"2026-Q3"` sob `period_type=monthly`, ou espaço/hífen
   trocado) criava uma meta que nunca casaria com nenhum
   `current_period_key()` real, degradando silenciosamente pra "sem meta
   definida" sem nenhum aviso — exatamente o sintoma que o roadmap pediu
   pra nunca acontecer, só por uma porta diferente (má formação do dado
   de entrada, não ausência dele). Corrigido com `field_validator` que
   valida `period_key` contra o formato exato que `current_period_key`
   produz (regex `AAAA-MM`/`AAAA-Q[1-4]`), mais `target_amount >= 0` e
   `rep_id` não-vazio. Frontend (`RepTargetsSection.tsx`) trocou o input
   de texto livre por `<input type="month">` (mensal) e `<select>` de
   trimestres calculados (`quarterOptions`, ano corrente + próximo) —
   formato inválido fica irrepresentável na UI, mais barato que validar
   depois.
2. `save_rep_target` reconstruía `created_at=_now()` a cada upsert —
   recadastrar a mesma meta reescrevia o carimbo, fazendo a coluna se
   comportar como "última modificação" apesar do nome. Corrigido: busca
   a linha existente antes do upsert e preserva o `created_at` original
   quando já existe.

### Não objetivo deste módulo

- Meta por segmento (só por rep, ver "Escopo" acima).
- Nenhum aviso proativo se uma meta cadastrada nunca aparecer em nenhum
  `coverage_ratio` (ex.: rep_id com typo que não bate com nenhuma empresa
  real) — mitigado só pro caso de `period_key` malformado (achado 1
  acima); um `rep_id` que simplesmente não existe em nenhuma
  `Company.rep_id` real não tem validação cruzada.

### Teste

- `current_period_key`: formato mensal, mapeamento correto dos 12 meses
  pros 4 trimestres (não só as 4 bordas testadas — fórmula
  `(mês-1)//3+1` verificada matematicamente na revisão de código).
- `rep_target_id`: determinístico pro mesmo rep+período, diferente pra
  período diferente (inclui o caso do mesmo texto de `period_key` sob
  `period_type` diferente, garantindo que nunca colidem).
- `compute_rep_coverage`: sem meta → `None` nunca 0%; meta explícita 0 →
  `target=0.0` mas `coverage_ratio=None`, nunca `ZeroDivisionError`; rep
  com meta mas pipeline zerado aparece com 0% real.
- Repositório: round-trip, upsert nunca duplica, filtro por período,
  `created_at` preservado num upsert.
- Rota: upsert via `POST` repetido, 422 pra `period_key` mal-formado e
  pra `target_amount` negativo, `dashboard-metrics` reflete meta
  configurada e calcula `coverage_ratio` corretamente.

### Critério de sucesso

- [x] Rep sem meta nunca mostra 0% nem divide por zero.
- [x] Recadastrar meta pro mesmo rep+período é upsert, nunca duplicata.
- [x] `period_key` malformado é rejeitado na fronteira HTTP, nunca cria
      meta órfã silenciosa.
- [x] Suíte completa (backend + frontend) e revisão de código sem
      pendências abertas.

## Módulo 8 — Dashboard: cards de KPI e fio final da Fase D

Última fatia da Fase D — 100% frontend. Os módulos 2 a 7 (já commitados)
implementaram tudo no backend (`GET /dashboard-metrics`: `funnel_reach`,
`weighted_potential`, `zombie_count`, `aging_count`/`aging_sla_days`,
`potential_by_rep/segment/source`, `rep_coverage`), mas o
`Dashboard.tsx` só consumia os campos anteriores (Fase B/C). Este módulo
liga o fio: consome todos os campos novos e adiciona uma linha de
explicação (`hint`) em todo card de KPI — requisito explícito do roadmap
("princípio 4: público final é comercial, não analista").

`StatTile` já suportava `hint` desde antes (Fase B/C) — nunca usado.
Terminologia "alcance do funil" (nunca "conversão", decisão do Pipeline
Analyst do módulo 4) verificada também no texto novo. Estados vazios
seguem o padrão já usado no resto do módulo: `lt-empty role="status"`
pros cortes (`potential_by_rep/segment/source`) sem dado, `"Sem meta
definida"` (nunca `0%`) na tabela de cobertura quando `coverage_ratio`
vem `null` do backend.

**Achados da revisão de código** (3, Important, todos corrigidos):
1. `error` era setado num fetch falho mas nunca limpo quando um fetch
   posterior (disparado pela troca de período) tinha sucesso — uma
   falha transitória travava o dashboard na mensagem de erro pra
   sempre, mesmo depois de uma resposta válida chegar. Corrigido:
   `setError(null)` no início do efeito.
2. Sem guarda contra resposta desatualizada: se uma requisição lenta
   (ex. trimestral) resolvesse depois de uma mais rápida subsequente
   (ex. mensal), a mais lenta sobrescreveria o estado mais fresco com
   dado de período errado — `coveragePeriodType` no estado divergiria
   do `<select>`. Corrigido com a guarda padrão `cancelled` (variável de
   fechamento setada `true` no cleanup do efeito, checada antes de
   qualquer `setMetrics`/`setError`).
3. `setMetrics(null)` a cada troca de período zerava o dashboard
   INTEIRO (todos os KPIs, todos os gráficos) só porque o usuário trocou
   o filtro da tabela de cobertura — a única seção que de fato depende
   de período. Corrigido: o `metrics` anterior continua renderizado
   durante o refetch; só a checagem de carregamento inicial (`!metrics`)
   ainda mostra "Carregando…", e só na primeira renderização.

### Não objetivo deste módulo

- Segmentação por região (mantido do texto de rodapé anterior — ainda
  exige dado real de região vindo de uma fonte configurada, ex. Google
  Maps).
- Tendência temporal / série histórica dia a dia — o snapshot diário
  (módulos 2+3) guarda o estado de HOJE, recalculado por inteiro a cada
  `/sync`, nunca uma série de snapshots anteriores. `funnel_reach` é o
  mais próximo que a Fase D chega disso, e mesmo assim é "alcance hoje",
  nunca uma série temporal real.
- Testes de componente React: o projeto não tem infraestrutura de
  testes de renderização (só `*.test.ts` de lógica pura extraída, ver
  `frontend/src/settings/logic.ts`/`.test.ts`) — os 3 achados da revisão
  foram verificados via Playwright ao vivo (troca de período mantendo o
  resto do dashboard visível), não por teste automatizado. Adicionar
  React Testing Library só pra isso seria escopo maior que o bug em si.

### Teste

- Nenhum teste automatizado novo (módulo é composição de dado já
  testado nos módulos 2-7 — a lógica de mapeamento snake_case→camelCase
  em `api.ts` foi conferida campo a campo contra `routes_sync.py` na
  revisão de código, sem mismatch).
- Verificação ao vivo (Playwright, cópia instalada): todos os KPIs com
  hint renderizando; "Alcance do funil" com 5 estágios e texto sem
  "conversão"; cortes por rep/segmento/fonte com estado vazio amigável;
  tabela de cobertura calculando `coverage_ratio` corretamente (rep-1
  50%, rep-2 40%) e mostrando "Sem meta definida" pro trimestre sem
  cadastro; troca de período mensal→trimestral preserva o resto do
  dashboard visível (não zera mais tudo); zero erros de console.

### Critério de sucesso

- [x] Todo card de KPI (novo e antigo) tem uma linha de explicação.
- [x] `funnel_reach` nunca rotulado como "conversão" em nenhum texto
      visível.
- [x] `coverage_ratio` nulo nunca renderiza como `0%`.
- [x] Troca de período não zera o dashboard inteiro, sem race condition
      nem erro que trava permanentemente.
- [x] Fase D encerrada — 8 módulos do capability map entregues, testados,
      revisados e documentados.
