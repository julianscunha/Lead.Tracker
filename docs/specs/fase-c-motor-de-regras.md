# Spec: Fase C — Motor de regras ampliado

Ver `docs/roadmap.md` (Fase C) pro contexto completo. Esta spec cobre a
**primeira fatia vertical** — persistência de regra + regra por categoria/
relação + ligação no fluxo de sync + editor mínimo na UI. As fatias
seguintes (sinais de expansão no motor, formato de evidência rico,
quantificação de gap, cadência de QBR) ficam em specs próprias, menores,
conforme o roadmap já preveem como itens separados.

## Por que fatiar

Fase C no roadmap lista 8 capacidades. Entregar tudo de uma vez violaria
`incremental-implementation` — nenhuma delas é útil sozinha até a
**persistência de regra existir**, que é o bloqueio real desde a Fase B.1
("não existe nenhum lugar que guarda regra"). Por isso esta fatia entrega
o mínimo que já resolve a lacuna mais visível: uma regra cadastrada de
verdade gera uma oportunidade real na tela, pela primeira vez no projeto.

## Objetivo desta fatia

1. `CorrelationRule` vira modelo de domínio persistido (hoje é um
   `dataclass` só em memória, criado ad-hoc em teste).
2. Regra por categoria — generaliza sem quebrar a forma atual
   (`requires`/`absent` continuam existindo, mas passam a aceitar também
   `requires_category`/`absent_category`).
3. Regra de relação tipada (`relation_type` de `ProductRelation`, já
   existente da Fase B): `prerequisite` vira sinalização de risco técnico
   (novo campo em `Opportunity`), `substitute` vira oportunidade tipo
   `consolidation`.
4. `POST /sync` passa a rodar o motor de regras persistidas contra o
   portfólio de cada empresa sincronizada — a lacuna documentada na Fase
   B.1 ("sem fonte de regra, sempre zero oportunidades") fecha aqui.
5. Editor de regras na UI: formulário por dropdown (categoria/relação/
   item), nunca campo de texto livre — nova aba ou seção em Configurações.

## Não objetivo desta fatia (fica pra próxima)

- Sinais de expansão (`CompanySignal`) entrando no motor.
- Formato de evidência rico (fato+implicação+fonte+data,
  `discovery_prompt`).
- Quantificação de gap por severidade.
- Cadência de QBR.
- Sinais granulares de qualificação (recência de atividade, nível
  hierárquico, contagem de contatos).

Continuam com a evidência simples atual (`evidence: list[str]` com os itens
que dispararam a regra) — não é regressão, é a mesma forma que já existe e
já é testada; só ganha mais uma fonte de regra pra avaliar.

## Design técnico

### `core/models.py` — `CorrelationRule` vira modelo persistido

```python
class CorrelationRule(BaseModel):
    id: str = Field(default_factory=_new_id)
    opportunity_type: str
    justification: str
    requires: list[str] = Field(default_factory=list)
    absent: list[str] = Field(default_factory=list)
    requires_category: list[str] = Field(default_factory=list)
    absent_category: list[str] = Field(default_factory=list)
    relation_type: str | None = None  # "prerequisite" | "substitute" — regra baseada em ProductRelation, não em requires/absent
    opportunity_score: float = 1.0
    confidence_score: float = 1.0
    active: bool = True
```
Substitui o `dataclass` atual em `core/opportunity_engine.py` (que migra
pra cá — regra é modelo de domínio, não detalhe do motor). `RuleError`
(validação "requires não pode ser vazio... a menos que seja regra de
categoria ou relação") continua em `opportunity_engine.py`, que é quem
valida antes de avaliar.

`Opportunity` ganha `risk_flag: str | None` — usado pela regra de
pré-requisito pra sinalizar risco técnico sem forçar isso a virar uma
"oportunidade" fake (venda já feita sem o pré-requisito não é uma
oportunidade de venda, é um alerta).

### `core/opportunity_engine.py` — `evaluate_rules` ampliado

- Regra por categoria: verifica se **algum** item do portfólio pertence à
  categoria de `requires_category`, e **nenhum** pertence a
  `absent_category` — precisa do catálogo de Product/Service (com
  `category`) além do Portfolio (que só tem IDs), então a assinatura de
  `evaluate_rules` ganha `products: list[Product]`, `services:
  list[Service]` como parâmetros (mapeamento id→category).
- Regra de relação: itera `Product.related_services` do catálogo — se
  `relation_type == rule.relation_type` e o produto está no portfólio mas o
  service associado não, gera oportunidade (`substitute` →
  `opportunity_type="consolidation"`) ou risco (`prerequisite` →
  `Opportunity.risk_flag` preenchido, sem forçar `opportunity_type`).
- Mantém 100% de retrocompatibilidade com regra simples (`requires`/
  `absent` sem categoria/relação) — testes existentes de
  `test_opportunity_engine.py` continuam passando sem alteração.

### Persistência

- `core/db_models.py`: `CorrelationRuleORM` nova tabela.
- `core/repository.py`: `save_rule`/`list_active_rules`.
- `core/db_models.py`: `OpportunityORM` ganha `risk_flag`.

### `backend/sync.py` — liga o motor no fluxo real

Depois de persistir companies/contacts, `sync_source` passa a: carregar
portfólio de cada empresa sincronizada (se existir — Fase B.1 já
documentou que não há fonte popula isso ainda, então na prática continua
vazio pra Salesforce/Manual hoje, mas o código já fica pronto pra quando
existir), carregar regras ativas, catálogo de produto/serviço, rodar
`evaluate_rules`, persistir oportunidades geradas. Empresa sem portfólio
conhecido não gera oportunidade nenhuma — comportamento correto, não bug.

### Frontend — editor mínimo

Nova seção "Regras" na aba Configurações (reaproveita o padrão de card já
usado pra fontes). Formulário: tipo de regra (dropdown: presença/ausência,
categoria, relação) → campos condicionais por tipo, todos dropdown
alimentado pelo catálogo real (`GET /products`, `GET /services` novos) —
nunca texto livre. Lista de regras cadastradas com toggle ativo/inativo.

## Estratégia de teste

Mesmo padrão dos demais — sem framework novo.

- `core/opportunity_engine.py`: regra de categoria, regra de prerequisito
  (gera `risk_flag`, não oportunidade), regra de substituto (gera
  `consolidation`), regra simples antiga continua passando (retrocompat).
- `core/repository.py`: round-trip de `CorrelationRule`.
- `backend/sync.py`: sync com regra ativa + portfólio existente gera
  oportunidade persistida; sync sem portfólio não gera nada (não é erro).
- Rotas novas: `TestClient`, mesmo padrão dos demais.
- Frontend: lógica pura do formulário (`logic.test.ts`-style).

## Fronteiras

- **Sempre:** regra sempre citando item/categoria real que disparou —
  nunca oportunidade sem evidência (regra de domínio já existente,
  reforçada aqui).
- **Nunca:** motor de regras genérico tipo query language — só os 3 tipos
  fixos. Nunca campo de texto livre no editor.

## Critérios de sucesso

- [ ] Regra cadastrada via API gera oportunidade real numa sincronização
      com portfólio de teste.
- [ ] Regra de prerequisito gera `risk_flag`, nunca uma oportunidade falsa.
- [ ] Regra de substituto gera oportunidade tipo `consolidation`.
- [ ] Retrocompatibilidade total com `test_opportunity_engine.py` atual.
- [ ] Editor mínimo funcional na UI (criar regra por dropdown, ver lista).
- [ ] Suíte completa passa. `CHANGELOG.md` atualizado.

---

## Fatia 2 — Sinais de expansão entrando no motor

### Objetivo

`CompanySignal` existe desde a Fase B (persistido, com CRUD) mas nenhuma
regra consegue reagir a ele — sinal de renovação próxima, troca de
contato-chave, adoção parcial fica só guardado, nunca vira oportunidade.

### Design — sem 4º tipo de regra

Roadmap é explícito: "só 3 tipos de regra no total, nunca mais". Em vez de
criar um mecanismo novo (`requires_signal_type`), `signal_type` dos sinais
**abertos** (`status="open"`) da empresa entra no mesmo conjunto de itens
que `requires`/`absent` (mecanismo 1) já verifica — uma regra
`requires=["renewal_upcoming"]` dispara se existir um `CompanySignal`
aberto com esse `signal_type`, exatamente como hoje dispara por
`product_id`/`service_id` no portfólio. Zero mecanismo novo, zero regra
nova — só uma fonte a mais de "item presente".

- `core/opportunity_engine.py::evaluate_rules` ganha parâmetro opcional
  `signals: list[CompanySignal] | None = None`; `_portfolio_items` (ou uma
  variante) passa a unir `portfolio` + `{s.signal_type for s in signals if
  s.status == "open"}`.
- `backend/sync.py` carrega `list_company_signals(session, company.id)`
  pra cada empresa avaliada e passa pro motor.
- Sinal resolvido/descartado (`status != "open"`) nunca conta — evita regra
  disparar por um sinal que já foi tratado.

### Não objetivo desta fatia

- Nenhuma fonte ainda **gera** `CompanySignal` automaticamente (nem
  Salesforce nem Manual criam sinal — isso é outra tarefa, ligar
  `LastActivityDate`/dado de CRM a um sinal de verdade). Esta fatia só
  garante que, se um sinal existir (hoje só via `POST` direto no
  repositório/teste, sem rota de criação ainda), o motor o usa.
- Sem rota de criação de sinal na API/UI ainda — fica pra quando existir
  fonte real gerando sinal.

### Teste

- `evaluate_rules` com sinal aberto presente dispara regra que o `requires`.
- Sinal `status="resolved"` não dispara.
- Sem `signals` (retrocompat) continua funcionando como hoje.
- `backend/sync.py`: empresa com sinal aberto + regra correspondente gera
  oportunidade via sync.

### Critério de sucesso

- [x] Sinal aberto dispara regra simples via `requires`.
- [x] Sinal resolvido/descartado nunca dispara.
- [x] Retrocompat total (chamada sem `signals` continua igual).
- [x] Suíte completa passa.

---

## Fatia 3 — Formato de evidência rico

### Objetivo

Princípio 2 do roadmap: evidência é sempre "fato + implicação de negócio +
fonte + data", nunca um log técnico cru. Hoje `Opportunity.evidence` é só
`list[str]` de ids que dispararam a regra (fica) — falta compor a frase
legível e a `discovery_prompt` opcional.

### Design

- `CorrelationRule` ganha `discovery_prompt: str | None = None` — pergunta
  que o vendedor deveria fazer pra confirmar a causa raiz (nunca a
  resposta). Configurável por regra, não hardcoded.
- `Opportunity` ganha 3 campos novos, nunca substituindo os que já existem
  (evidência bruta e rastreável continua em `evidence`/`sources`):
  - `evidence_summary: str | None` — frase montada pelo motor no formato
    `"[FATO] ... → [OPORTUNIDADE|RISCO] ... → [FONTE] ..., sincronizado em ..."`.
    `[RISCO]` quando a regra gera `risk_flag` (prerequisite), `[OPORTUNIDADE]`
    nos demais casos.
  - `discovery_prompt: str | None` — copiado da regra que gerou a
    oportunidade.
  - `synced_at: datetime` — timestamp de quando o motor avaliou (o "data"
    do formato). Não é "primeira detecção" (isso é Fase D/histórico de
    status) — é literalmente a data da última sincronização que confirmou
    a evidência, exatamente o que o formato de referência pede.
- `core/opportunity_engine.py::_build_opportunity` monta `evidence_summary`
  a partir de `evidence`, `rule.justification`, `sources[0].type` e
  `synced_at` — sem IA, string formatada por código determinístico.
- Persistência: `OpportunityORM` ganha as 3 colunas; `core/repository.py`
  atualizado nos dois sentidos (leitura/escrita).

### Não objetivo

- Não altera `evidence`/`justification`/`sources` existentes — só adiciona.
- Não resolve id de item pra nome legível (ex.: `veeam_vbr` → "Veeam VBR")
  — isso é responsabilidade do frontend, que já tem o catálogo carregado.

### Teste

- `evaluate_rules`: `evidence_summary` contém `[FATO]`, `[OPORTUNIDADE]` (ou
  `[RISCO]` no caso prerequisite) e `[FONTE]`.
- `discovery_prompt` da regra aparece na oportunidade gerada; regra sem
  `discovery_prompt` gera oportunidade com o campo `None` (não quebra).
- Round-trip de persistência (`core/repository.py`) preserva os 3 campos
  novos.

### Critério de sucesso

- [x] `evidence_summary` presente e no formato de referência em toda
      oportunidade gerada pelo motor (inclusive regra só-de-ausência,
      achado de revisão corrigido — `_fact_description` nunca deixa
      `[FATO]` em branco).
- [x] `discovery_prompt` propagado da regra pra oportunidade.
- [x] Retrocompat: regra sem `discovery_prompt` não quebra nada.
- [x] Suíte completa passa.

---

## Fatia 4a — Sinais granulares de qualificação (campos automáticos)

Decisões tomadas com o usuário antes desta fatia:
- Janela de recência: **90 dias**, binário quente/fria, `×1.0`/`×0.7`.
  **Corrigido após o fato** (ver "Correção pós-shipping" abaixo) — mantido
  aqui só como registro histórico da decisão original.
- Nível hierárquico: mapeamento automático por palavra-chave a partir do
  `Title`/`role` que o Salesforce já traz; sem correspondência fica
  `None` — nunca inventa classificação.
- **Fatiado deliberadamente**: esta fatia só cobre campo + mapeamento
  automático + exposição via API já existente. Edição manual do nível
  hierárquico (rota `PATCH` nova + UI nova, porque hoje não existe
  nenhum endpoint de edição de contato) fica pra **Fatia 4b**, separada.

### Design

- `core/models.py`:
  - `Company.last_activity_at: datetime | None = None`.
  - `Contact.seniority_tier: str | None = None` — string aberta (núcleo
    genérico, não é enum fechado), valores de referência do mapeamento:
    `"decisor"` / `"influenciador_tecnico"` / `"operacional"`.
- `providers/salesforce.py`:
  - `fetch_companies`: SOQL ganha `LastActivityDate`; parse pra
    `datetime` UTC-aware (campo é `Date` no Salesforce — vira meia-noite
    UTC do dia).
  - `fetch_contacts`: nova função `_infer_seniority_tier(title)` —
    dicionário de palavras-chave em português (`gestor`/`diretor`/`head`
    → decisor; `arquiteto`/`especialista` → influenciador técnico;
    `técnico`/`analista`/`suporte` → operacional), case-insensitive,
    substring match. Sem match → `None`.
- `core/opportunity_engine.py`:
  - `_warmth_multiplier(company: Company | None) -> float` — `company`
    não passado (retrocompat) → `1.0` sem penalidade; ver "Correção
    pós-shipping" abaixo pros níveis atuais.
  - `evaluate_rules` ganha `company: Company | None = None`; `confidence_score`
    de toda oportunidade gerada é `rule.confidence_score * _warmth_multiplier(company)`.
- `backend/sync.py`: passa `company=company` (já disponível no loop) pra
  `evaluate_rules`.
- Persistência: `CompanyORM.last_activity_at`, `ContactORM.seniority_tier`
  novas colunas; `core/repository.py` atualizado nos dois sentidos.
- Exposição: `GET /companies` já serializa `Company` inteiro (sem mudança
  de rota) — `last_activity_at` aparece automaticamente. `seniority_tier`
  fica disponível via `list_contacts`/`Contact` pra quando a Fatia 4b
  expuser rota/tela de contato.

### Não objetivo desta fatia

- Nenhuma UI nova, nenhuma rota de edição manual (Fatia 4b).
- Contagem de contatos distintos (multi-threading) — sinal separado,
  puramente derivado (sem campo novo), fica como fatia própria mínima
  se/quando a tela de oportunidade for exibir isso.

### Teste

- `_infer_seniority_tier`: reconhece cada categoria de palavra-chave,
  `None` pra título sem match, `None` pra título vazio/ausente.
- `SalesforceProvider.fetch_companies`: mapeia `LastActivityDate` pra
  `last_activity_at`.
- `evaluate_rules`: `company` quente → confidence_score cheio; sem
  `company` (retrocompat) → confidence_score cheio, sem penalidade.
  Ver "Correção pós-shipping" pros níveis morno/muito frio atuais.
- Persistência: round-trip dos dois campos novos.

### Critério de sucesso

- [x] `last_activity_at` mapeado do Salesforce, alimenta o multiplicador
      de `confidence_score` na geração de oportunidade.
- [x] `seniority_tier` mapeado automaticamente por palavra-chave, `None`
      quando não reconhece.
- [x] Retrocompat total: chamada sem `company` não muda comportamento
      hoje existente.
- [x] Suíte completa passa (achado de revisão corrigido:
      `_warmth_multiplier` reanexa UTC se `last_activity_at` vier naive,
      em vez de deixar `TypeError` explodir cru até o sync).

---

## Fatia 5 — Quantificação de gap por severidade

### Objetivo

Última capacidade em aberto da Fase C do roadmap: classificar o quão
sério é um gap detectado, sem inventar valor em R$. Diferente das fatias
anteriores, os dois campos-fonte (`scope_note`/`criticality`) são
**100% manuais** — não existe nenhuma fonte automática que os preencha.

### Decisões tomadas (com o usuário + consulta ao Deal Strategist)

Desenho original (usuário) tinha 2 opções de criticidade e 3 bandas; o
Deal Strategist (especialista em qualificação de deals/MEDDPICC,
consultado por instrução do usuário antes de fixar a metodologia)
recomendou refinar pra separar "crítico mas interno" de "crítico e
exposto ao cliente" — são histórias de venda diferentes. Versão adotada:

- **Alcance** (`scope_note`, dropdown): `isolado` (poucos sistemas/
  licenças) / `parcial` (parte relevante do parque) / `generalizado`
  (maior parte do parque).
- **Criticidade** (`criticality`, dropdown): `nao_critico` / `critico_interno`
  (grave, mas não visível ao cliente) / `critico_exposto` (produção/
  cliente-facing).
- **Observação** (`severity_note`, texto livre **opcional**): rastro de
  auditoria pra banda não virar "número sem contexto" — não é um 3º eixo
  de classificação, só contexto de apoio (mesmo padrão de uso livre que
  `ContextNote` já tem em outros lugares do domínio).
- **Banda de severidade**: `baixo` / `medio` / `alto` / `critico`,
  **nunca persistida** — computada a partir de `scope_note`×`criticality`
  toda vez que a oportunidade é lida (elimina de vez o risco de banda e
  campos-fonte saírem de sincronia). Qualquer um dos dois em branco →
  `nao_avaliado`, nunca um valor calculado com informação incompleta.

Tabela (Alcance × Criticidade → banda):

| | não crítico | crítico interno | crítico exposto |
|---|---|---|---|
| isolado | baixo | medio | alto |
| parcial | medio | alto | alto |
| generalizado | medio | alto | critico |

### Decisão de arquitetura (consulta ao agente `Plan`)

Consultado antes de decidir o fatiamento: **tudo numa fatia só**
(campos + função de banda + rota de escrita + UI), não repetir o padrão
"campo primeiro, edição depois" da Fatia 4a — lá o campo tinha fonte
automática (Salesforce) e produzia efeito observável sem UI nova; aqui
não existe fonte automática nenhuma, então uma fatia sem rota de escrita
deixaria `severity_band` em `nao_avaliado` pra sempre, sem nenhum
comportamento observável fora de teste unitário.

**Achado real do mesmo agente, confirmado no código**: `core/repository.py
save_opportunity` faz `session.merge()` de um `OpportunityORM` inteiro
construído a partir do `Opportunity` que o motor gera — como o motor
nunca sabe de `scope_note`/`criticality`/`severity_note` (ficam `None`
no objeto que ele constrói), todo `POST /sync` futuro apagaria qualquer
valor que o vendedor tivesse preenchido manualmente. **Correção**:
`save_opportunity` (caminho do motor) passa a preservar os 3 campos
manuais da linha já existente antes do merge. A escrita manual desses 3
campos usa uma função própria (`update_opportunity_qualification`),
nunca `save_opportunity` — dois caminhos de escrita totalmente
separados, sem ambiguidade sobre qual "vence".

### Design

- `core/models.py`: `Opportunity` ganha `scope_note: str | None`,
  `criticality: str | None`, `severity_note: str | None` — todos
  opcionais, strings abertas (núcleo genérico, não enum fechado no
  domínio; a UI que restringe às 3+3 opções via dropdown).
- `core/opportunity_engine.py`: `compute_severity_band(scope_note,
  criticality) -> str` — função pura, tabela acima + fallback
  `"nao_avaliado"`. Nunca chamada durante `evaluate_rules` (motor não
  sabe de severidade) — só na leitura (rota).
- `core/db_models.py`: `OpportunityORM` ganha as 3 colunas novas
  (nullable). Sem coluna de banda — é sempre derivada.
- `core/repository.py`:
  - `save_opportunity` (caminho do motor): busca a linha existente por
    id antes do merge; se existir, copia `scope_note`/`criticality`/
    `severity_note` dela pro objeto que vai ser salvo (motor nunca
    sobrescreve dado manual).
  - `update_opportunity_qualification(session, opportunity_id,
    scope_note, criticality, severity_note) -> Opportunity | None` —
    único caminho de escrita desses 3 campos; `None` se a oportunidade
    não existir (rota decide 404). Substituição completa dos 3 campos
    a cada chamada (a UI sempre envia o estado atual dos 3 controles,
    sem merge parcial ambíguo).
- `backend/routes_sync.py`:
  - `OpportunityOut` ganha `scope_note`, `criticality`, `severity_note`,
    `severity_band` (computado na resposta via `compute_severity_band`).
  - `PATCH /opportunities/{opportunity_id}` — body `{scope_note,
    criticality, severity_note}` (`OpportunityQualificationIn`, todos
    opcionais/nuláveis) — chama `update_opportunity_qualification`,
    404 amigável se não existir.
- Frontend:
  - `types.ts`: `OpportunityRow` ganha os 4 campos novos.
  - `api.ts`: `fromApiRow` mapeia os campos novos; `updateOpportunityQualification`
    nova função (`PATCH`, mesmo padrão de `createRule`).
  - `OpportunityTable.tsx` (`RowDetail`): 2 `<select>` (Alcance,
    Criticidade — sempre dropdown, nunca texto livre pro que vira
    critério) + 1 `<textarea>` opcional (Observação) + selo da banda
    calculada; salva via `updateOpportunityQualification` ao mudar.

### Não objetivo desta fatia

- Nenhuma fonte automática de `scope_note`/`criticality` — 100% manual,
  como decidido.
- Nenhuma quantificação em R$ — banda qualitativa só, nunca número
  calculado (regra de domínio, princípio "IA/motor nunca inventa valor
  financeiro").

### Teste

- `compute_severity_band`: as 9 combinações da tabela + fallback
  `nao_avaliado` pra cada campo em branco (isolado, junto, e os dois).
- `core/repository.py`: `save_opportunity` chamado 2x (simulando 2
  syncs) com `update_opportunity_qualification` no meio preservando o
  valor manual no segundo `save_opportunity` — regressão do bug
  encontrado pelo agente `Plan`.
- `update_opportunity_qualification`: round-trip dos 3 campos; `None`
  quando a oportunidade não existe.
- Rota `PATCH /opportunities/{id}`: sucesso atualiza e devolve
  `severity_band` recalculado; 404 amigável pra id inexistente.
- Frontend: lógica pura de formatação/rótulo (se houver) em teste
  `*.test.ts`, mesmo padrão de `RulesSection.test.ts`.

### Revisão de código (`agent-skills:code-reviewer`) — 2 achados corrigidos

- **TOCTOU no fix do `Plan`**: o fetch-then-merge original de
  `save_opportunity` (busca a linha, depois `session.merge()`) ainda
  deixava uma janela entre as duas `await` onde um `PATCH` concorrente
  podia ser sobrescrito pelos valores antigos lidos antes dele.
  Corrigido trocando por upsert atômico (`INSERT ... ON CONFLICT(id) DO
  UPDATE`, `sqlalchemy.dialects.sqlite.insert`) que nunca lista as 3
  colunas manuais no `SET` — não há mais janela de leitura entre a
  checagem e a escrita. Regressão coberta por
  `test_save_opportunity_concurrent_with_qualification_update_never_reverts_it`
  (20 rodadas de `save_opportunity`/`update_opportunity_qualification`
  concorrentes via `asyncio.gather`).
- **Frontend, respostas de PATCH fora de ordem**: mudar Alcance e
  Criticidade rapidamente dispara 2 `PATCH` independentes; se a resposta
  do mais antigo chegasse depois, revertia silenciosamente o valor mais
  novo na tela. Corrigido com um contador de sequência
  (`SeverityQualification`, `frontend/src/OpportunityTable.tsx`) que
  descarta qualquer resposta que não seja a do último `save` disparado.
- **Sugestão adotada**: `scope_note`/`criticality` continuam string
  aberta no domínio (decisão documentada acima), mas a rota `PATCH` é
  acessível por qualquer cliente HTTP, não só a UI — um `Literal` em
  `OpportunityQualificationIn` fecha esse ponto de entrada (valor fora
  das 3 opções vira 422, nunca degrada silenciosamente pra
  "não avaliado").

### Critério de sucesso

- [x] `severity_band` correto pra cada uma das 9 combinações + fallback.
- [x] `POST /sync` nunca apaga `scope_note`/`criticality`/`severity_note`
      já preenchidos manualmente (regressão coberta por teste, inclusive
      concorrente).
- [x] `PATCH /opportunities/{id}` funcional, 404 amigável se não existir,
      422 pra valor fora das 3 opções.
- [x] UI com os 2 dropdowns + observação opcional, nunca texto livre pro
      que vira critério de banda.
- [x] Suíte completa passa (backend + frontend).

### Correção pós-shipping — threshold de recência (consulta ao Pipeline Analyst)

Por instrução do usuário ("sempre... puxar antes as skills de
especialistas... pois eu e vc não somos especialistas"), consultamos o
agente Pipeline Analyst *depois* deste código já commitado — achado real:
90 dias binário é curto demais pra ciclo de venda B2B de infraestrutura
(normalmente 90-180+ dias), penalizando conta só no ritmo normal do ciclo
(aprovação de budget, licitação) como se tivesse esfriado. Além disso, o
corte único igualava "91 dias sem atividade" a "700 dias" — populações de
risco muito diferentes.

**Substitui o binário por 3 níveis:**
- Quente: `≤120 dias` → `×1.0`.
- Morno: `121-270 dias` → `×0.85`.
- Muito frio: `>270 dias` OU nunca registrado → `×0.5` (ausência continua
  sendo o próprio sinal, nunca um terceiro estado "desconhecido" — só
  ficou mais severo que o binário original).

`_WARM_WINDOW_DAYS`/`_LUKEWARM_WINDOW_DAYS`/`_LUKEWARM_MULTIPLIER`/
`_COLD_MULTIPLIER` em `core/opportunity_engine.py`. O Pipeline Analyst
recomendou calibrar o corte quente/morno pela mediana real de
intervalo-entre-atividades dos deals fechados do usuário (não temos esse
dado ainda) — os números acima são o ponto de partida, não um valor
definitivo; revisitar quando existir essa métrica.
