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
