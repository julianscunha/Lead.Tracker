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
