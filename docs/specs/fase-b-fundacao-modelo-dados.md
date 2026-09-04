# Spec: Fase B — Fundação do modelo de dados

Ver `docs/roadmap.md` (Fase B) pro contexto: retrofitar histórico depois que
dado real começar a fluir é caro, então os campos abaixo entram agora, antes
da Fase B.1 (ligação real) e da Fase C (motor de regras ampliado) existirem
de verdade.

## Objetivo

Ampliar `core/models.py`/`core/db_models.py`/`core/repository.py` com os
campos que o roadmap identificou como fundação — sem tela nova, sem rota
nova, sem popular esses campos automaticamente ainda. É preparação de
schema, silenciosa.

## Não objetivo (explicitamente fora de escopo)

- **Popular os campos a partir do Salesforce** (ex.: `segment`/`region` a
  partir de `AnnualRevenue`/endereço) — o `SalesforceProvider` ainda só
  traz `Id, Name, Website`; ampliar o SOQL é outra tarefa (retomar a
  proposta de campos padrão feita antes desta sessão de planejamento).
- **Gravar `OpportunityStatusChange` automaticamente** quando o status de
  uma oportunidade muda — a função de repositório existe (`save`/`list`),
  mas não é chamada de dentro de `save_opportunity`. Auto-registrar isso
  exige decidir *onde* a transição de status acontece de verdade (Fase
  B.1/D), não faz sentido adivinhar aqui.
- **UI de qualquer tipo.**

## Design

### Novo tipo reutilizável: `ContextNote`

Substitui "texto solto" por fato rastreável — reaproveitado em 3 lugares
(`trigger_event`, `attempted_solutions`, `strategic_context`) em vez de
inventar 3 formatos diferentes:

```python
class ContextNote(BaseModel):
    text: str
    source: SourceRef
    observed_at: datetime = Field(default_factory=_now)
```

### `Company` ganha

- `rep_id: str | None` — responsável, pré-requisito de corte por vendedor.
- `segment: str | None`, `region: str | None` — porte/região; string livre
  (não enum fechado — instalações diferentes segmentam diferente).
- `trigger_event: ContextNote | None` — "por que agora" (contratação,
  renovação próxima, incidente).
- `attempted_solutions: list[ContextNote]` — o que já tentaram antes.
- `strategic_context: ContextNote | None` — iniciativa/objetivo já
  mencionado pela empresa, sempre com fonte.

### `Contact` ganha

- `impacted_area: str | None` — quem sente o impacto do gap (string livre:
  "operações/TI", "compliance/risco", "liderança executiva", ...), não é o
  mesmo conceito que `role` (cargo formal).

### `Product`/`Service` ganham

- `category: str | None` em ambos — pré-requisito da Fase C (regra "tem
  categoria backup, não tem categoria monitoring").
- `Product.related_service_ids: list[str]` vira
  `Product.related_services: list[ProductRelation]` (renomeado — o campo
  nunca teve consumidor real ainda, `grep` confirma zero uso em
  `opportunity_engine.py`/testes, seguro renomear em vez de manter os dois):

```python
class ProductRelation(BaseModel):
    service_id: str
    relation_type: str = "complementary"  # convenção: prerequisite | complementary | substitute
```

`relation_type` fica string livre com convenção documentada, não `Enum`
fechado — mesmo princípio de núcleo genérico (revenda pode ter necessidade
que os 3 valores não cobrem).

### Dois modelos novos, duas tabelas novas

```python
class CompanySignal(BaseModel):
    id: str = Field(default_factory=_new_id)
    company_id: str
    signal_type: str          # string aberta: "renewal_upcoming", "champion_departed", ...
    evidence: list[str] = Field(default_factory=list)
    source: SourceRef
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    detected_at: datetime = Field(default_factory=_now)
    status: str = "open"      # open | resolved | dismissed

class OpportunityStatusChange(BaseModel):
    id: str = Field(default_factory=_new_id)
    opportunity_id: str
    status: OpportunityStatus
    entered_at: datetime = Field(default_factory=_now)
```

`CompanySignal` alimenta o mesmo motor de regras da Fase C (nunca um motor
paralelo — já é decisão registrada no roadmap). `OpportunityStatusChange` é
o histórico que faltava pra métricas de aging/velocity da Fase D.

### Persistência

- `core/db_models.py`: colunas novas nas tabelas existentes (`companies`,
  `contacts`, `products`, `services`), duas tabelas novas
  (`company_signals`, `opportunity_status_changes`). `ContextNote`/
  `ProductRelation` serializam como JSON (mesmo padrão de `sources`).
- **Sem Alembic** — mantém a decisão já documentada em `core/db.py`
  ("migração formal só se/quando o schema evoluir"). `create_all` só cria
  tabela ausente, nunca adiciona coluna a tabela existente — irrelevante
  hoje porque não existe instalação real com dado gravado ainda (Fase B.1,
  que liga isso de ponta a ponta, ainda não existe). Documentar esse limite
  como dívida conhecida, não resolver agora.
- `core/repository.py`: CRUD completo (`save`/`list`) para os dois modelos
  novos; mapeamento Pydantic↔ORM atualizado para os campos novos nas
  entidades existentes.

## Estratégia de teste

Mesmo padrão dos arquivos existentes (`tests/test_models.py`,
`tests/test_persistence.py`) — sem framework novo.

- `ContextNote`/`ProductRelation`: validação básica (campo obrigatório,
  default de `relation_type`).
- Round-trip de persistência pros 2 modelos novos (salva, recarrega, campo
  bate) — mesmo padrão de `test_company_round_trip_...`.
- Round-trip confirmando que os campos novos em `Company`/`Contact`/
  `Product`/`Service` sobrevivem ao save/load (incluindo `None`/lista vazia
  como default, pra não quebrar dado já existente sem esses campos).

## Fronteiras

- **Sempre:** suíte completa (backend) passa sem regressão antes de fechar.
- **Nunca:** inventar valor pra `segment`/`region`/`trigger_event` — todos
  ficam `None`/vazio até uma fonte real preenchê-los (Fase A ampliada ou
  Fase B.1).

## Critérios de sucesso

- [ ] Todos os campos novos existem em `core/models.py`, com default seguro
      (nunca quebra a criação de uma instância sem eles).
- [ ] `core/db_models.py`/`core/repository.py` espelham os campos novos.
- [ ] 2 tabelas novas com CRUD testado.
- [ ] Suíte completa passa.
- [ ] `CHANGELOG.md` atualizado.
