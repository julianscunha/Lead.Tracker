# Spec: Campos padrão adicionais de Account (Fase A)

## Objetivo

`SalesforceProvider.fetch_companies()` hoje só traz `Id, Name, Website,
LastActivityDate`. O roadmap (Fase A) pede trazer também: endereço
(`BillingCity/State/PostalCode/Country`), `Industry`, `AnnualRevenue`,
`NumberOfEmployees`, `Type`, `CreatedDate`. Esta spec decide, campo a
campo, o que vira atributo estruturado genérico de `Company` (núcleo
precisa continuar 100% genérico — nenhum campo cujo nome/semântica só
faça sentido pra Salesforce) e o que fica fora desta fatia.

Consultei o agente `Salesforce Architect` (decisão registrada abaixo,
campo a campo) antes de desenhar o modelo — decisão de domínio, não só
código.

## Decisões campo a campo

| Campo Salesforce | Decisão | Motivo |
|---|---|---|
| `Industry` | Novo campo `Company.industry: str \| None` | Distinto de `segment` (categorização comercial própria do Lead.Tracker, porte/prioridade de GTM) — `industry` é vertical de mercado. Colapsar os dois quebra o motor de regras no dia em que uma regra precisar de "vertical X + produto Y" sem mexer em segmentação comercial. |
| `AnnualRevenue` | Novo campo `Company.annual_revenue: float \| None` | Nome neutro — qualquer fonte (Maps, CSV, enriquecimento externo) preenche o mesmo campo. |
| `NumberOfEmployees` | Novo campo `Company.employee_count: int \| None` | Idem. |
| `BillingCity/State/PostalCode/Country` | Novo campo `Company.address: Address \| None`, objeto aninhado (`city, state, postal_code, country`) | Endereço como bloco coeso é o padrão comum de account profile B2B (Salesforce, HubSpot, Clearbit) — 4 campos soltos no namespace raiz de `Company` empurrariam a mesma decisão pra cada fonte futura de endereço. Sem `BillingStreet` (decisão já tomada na spec anterior — custo de PII sem ganho de precisão de geocoding). |
| `Type` | **Fora de escopo — não capturado** | Prospect/Customer é redundante com `is_customer` já existente; Partner/Competitor é papel de relacionamento, não status de cliente — misturar no mesmo conceito viola "Company genérico". `Company` não tem hoje nenhum mecanismo de metadado bruto por fonte (ao contrário de `ProviderContext.extra`, usado pela spec de custom fields) — criar um só pra guardar `Type` seria especulativo (YAGNI). Revisitar com spec própria se um caso de uso concreto aparecer (ex.: excluir competidores do funil). |
| `CreatedDate` | **Fora de escopo — não capturado** | Data de criação do registro no Salesforce, distinta de `Company.created_at` (quando o Lead.Tracker criou seu próprio registro). Baixo valor acionável pro motor de oportunidade hoje; mesmo raciocínio de `Type` — campo especulativo sem consumidor. |

## Estrutura afetada

```
core/models.py          → novo modelo Address; Company ganha industry/annual_revenue/employee_count/address
core/db_models.py       → CompanyORM ganha as 4 colunas (address como JSON, mesmo padrão de trigger_event/strategic_context)
core/repository.py      → _address_to_json/_address_from_json; _company_from_row e save_company estendidos
core/normalization.py   → merge_pair preserva os campos novos (first-known-wins, mesmo padrão de legal_name/website)
providers/salesforce.py → fetch_companies() consulta os campos novos e popula Company
tests/                  → test_models.py, test_persistence.py, test_normalization.py, test_salesforce_provider.py
CHANGELOG.md            → entrada em [Unreleased]
```

## Design técnico

**`Address` como `BaseModel` aninhado**, não um dict solto — mesmo padrão
de `ContextNote`/`SourceRef` já usados em `Company`. Todos os 4 campos
opcionais (`str | None`); provider Salesforce omite o campo Billing* que
vier vazio, nunca inventa string vazia no lugar de `None`.

**Persistência**: `address` vira coluna `JSON` (mesmo padrão de
`trigger_event`/`strategic_context`, que já guardam um `BaseModel`
aninhado serializado). `industry` (`String`), `annual_revenue`
(`Float`), `employee_count` (`Integer`) são colunas simples.

**`merge_pair`**: os 4 campos novos seguem o padrão `base.X or other.X`
(primeiro valor não-nulo vence, igual `legal_name`/`website`/
`customer_status`) — nenhum deles tem semântica de "sempre pegar o mais
recente" como `last_activity_at` (não são sinais de momentum, são
atributos de perfil que não mudam com frequência).

**`fetch_companies()`**: `SELECT Id, Name, Website, LastActivityDate,
Industry, AnnualRevenue, NumberOfEmployees, BillingCity, BillingState,
BillingPostalCode, BillingCountry FROM Account`. `Address` só é
construído (não fica `Address()` vazio) quando pelo menos um dos 4
campos veio preenchido — `None` inteiro quando a conta não tem nenhum
endereço, nunca um objeto com os 4 campos `None`.

## Estilo de código

Seguir o que já existe: `Company`/`Address` como `pydantic.BaseModel`
puro; helpers `_x_to_json`/`_x_from_json` em `repository.py` espelhando
`_note_to_json`/`_note_from_json`; sem abstração nova.

## Estratégia de teste

- `test_models.py`: `Address` aceita todos os campos opcionais.
- `test_persistence.py`: round-trip de `Company` com `industry`,
  `annual_revenue`, `employee_count`, `address` preenchidos; round-trip
  com todos `None` (nunca quebra); `address` nunca vira objeto com os 4
  campos `None` quando a fonte não trouxe endereço nenhum.
- `test_normalization.py`: `merge_pair` preserva o valor de `base` quando
  presente, usa o de `other` quando `base` é `None` (mesmo padrão de
  `legal_name`).
- `test_salesforce_provider.py`: `fetch_companies()` mapeia os campos
  novos corretamente; conta sem nenhum campo Billing preenchido nunca
  gera `Address` com todos os campos `None`.

## Fronteiras

- **Sempre fazer:** suíte completa antes de considerar concluído.
  Atualizar `CHANGELOG.md`.
- **Nunca fazer:** capturar `Type`/`CreatedDate` nesta fatia (fora de
  escopo, ver tabela acima). Nunca usar `industry`/`annual_revenue`/
  `employee_count` pra decidir oportunidade nesta fatia — são só dado
  estrutural novo; usá-los em regra do motor é decisão de produto
  separada, fora do escopo desta spec.

## Critérios de sucesso

- [x] `Company` ganha `industry`, `annual_revenue`, `employee_count`,
      `address` (objeto `Address` aninhado), todos opcionais.
- [x] `fetch_companies()` popula os 4 campos novos a partir da conta
      Salesforce real, sem inventar dado ausente.
- [x] `merge_pair` nunca perde o valor de nenhum dos campos novos ao
      reconciliar duas fontes.
- [x] `Type`/`CreatedDate` conscientemente fora de escopo (documentado,
      não esquecido).
- [x] Suíte completa passa. `CHANGELOG.md` atualizado.

## Revisão de código

Achado importante corrigido antes do commit: `merge_pair` usava `or` pra
`annual_revenue`/`employee_count` — `0` é falsy em Python, então
`annual_revenue=0.0` (empresa pré-receita) ou `employee_count=0` em
`base` seria sobrescrito por `other` mesmo sendo valor real, não
ausência de dado. Corrigido pra `base.X if base.X is not None else
other.X`, com teste de regressão (`test_merge_pair_preserves_zero_annual_revenue_and_employee_count`).
CHANGELOG inicialmente esquecido, adicionado.
