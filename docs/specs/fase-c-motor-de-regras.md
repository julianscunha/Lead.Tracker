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
- Janela de recência: **90 dias**. Existe atividade recente → quente.
  Não existe (nunca registrada ou expirou) → fria — nunca um terceiro
  estado "desconhecido", a ausência já é o sinal.
- Multiplicador de `confidence_score`: quente `×1.0`, fria `×0.7`.
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
    não passado (retrocompat) → `1.0` sem penalidade; `company` passado
    sem `last_activity_at` ou fora da janela de 90 dias → `0.7`; dentro
    da janela → `1.0`.
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
- `evaluate_rules`: `company` quente → confidence_score cheio; `company`
  frio (sem `last_activity_at` ou > 90 dias) → confidence_score ×0.7;
  sem `company` (retrocompat) → confidence_score cheio, sem penalidade.
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
