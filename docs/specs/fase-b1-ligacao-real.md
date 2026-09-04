# Spec: Fase B.1 — Ligação real (ingestão → banco → API → frontend)

Ver `docs/roadmap.md` (Fase B.1) — é a lacuna mais antiga identificada nesta
sessão: hoje `backend/main.py` só tem `/ping` e rotas de export; o frontend
roda inteiro sobre `sampleData.ts`/`sampleMetrics.ts`.

## Descoberta que muda o escopo

`opportunity_engine.evaluate_rules(portfolio, rules)` recebe `rules:
list[CorrelationRule]` como parâmetro — **não existe hoje nenhuma
persistência de regra** (sem tabela, sem rota, sem UI). Isso só nasce na
Fase C ("motor de regras ampliado" — editor de regras do portfólio).
Portanto: rodar o motor de regras de verdade contra dado sincronizado não é
possível ainda nesta fase, honestamente — geraria zero oportunidades sempre
(lista de regras vazia), o que seria simular funcionalidade que não existe.

## Objetivo (redefinido)

Ligar o que **já existe e já pode ser real** — ingestão de empresas via
provider habilitado, normalização, persistência, e a API/frontend
mostrando esse dado de verdade em vez de `sampleData`. A geração de
oportunidades por regra fica para quando a Fase C existir (a rota de
oportunidades já lê a tabela real desde já — só estará vazia até lá, o que
é honesto, não um bug).

## Não objetivo (explicitamente fora de escopo)

- **Rodar `evaluate_rules` com regras de verdade** — não existe fonte de
  regra ainda (Fase C). A função de orquestração desta fase aceita uma
  lista de regras vazia por padrão e documenta isso.
- **Popular `Portfolio.product_ids` (o que a empresa cliente tem) a partir
  de um provider** — nenhum provider hoje extrai "produtos que o cliente
  usa" de Account/Contact do Salesforce (isso dependeria do mapeamento de
  campo personalizado, Fase F, ou de uma tela de portfólio por empresa,
  ainda não desenhada). `GET /opportunities` vai devolver lista vazia num
  install real até essas duas dependências (Fase C + fonte de portfolio
  por empresa) existirem — comportamento correto, não simulado.
- **Tela de portfólio da revenda** (catálogo Vendor/Product/Service) — já
  mencionada no README como existente conceitualmente, mas sem rota/tela
  própria; fora do escopo desta fase de ligação.

## Design técnico

### Orquestração de sincronização (`backend/sync.py`, novo)

```python
async def sync_source(session_factory, source: SourceDescriptor, env: dict) -> SyncResult:
    """Busca empresas/contatos do provider, normaliza, persiste.
    Não gera oportunidade (sem regra configurada ainda — ver spec)."""
```
- Usa `source.build(env)` (já existe em `backend/settings.py`) pra
  instanciar o provider.
- `provider.fetch_companies()` → `normalization.merge_companies()` →
  `repository.save_company()` por empresa.
- Por empresa salva, `provider.fetch_contacts(company.id)` →
  `repository.save_contact()`.
- Erros de provider (`ProviderError`) não abortam a sincronização inteira —
  uma fonte falhando não trava as outras nem perde o que já foi salvo
  (`asyncio.gather` com captura por item, não `try` único envolvendo tudo).
- Retorna `SyncResult(companies_synced, contacts_synced, errors: list[str])`
  — erros em linguagem de negócio, nunca exceção crua.

### Rotas novas (`backend/routes_sync.py` + extensão de `routes_settings.py`?)

- `POST /modules/lead_tracker/sync` — aciona `sync_source` pra toda fonte
  com `implemented=True` e `enabled=True` no `.env`. Corpo de resposta:
  resumo por fonte (`{source_id, companies_synced, contacts_synced,
  errors}`).
- `GET /modules/lead_tracker/companies` — lê `repository.list_companies()`,
  serializa pra JSON.
- `GET /modules/lead_tracker/opportunities` — lê
  `repository.list_opportunities()` (sem filtro de company por padrão,
  filtro opcional por query param `company_id`).

### Frontend

- `frontend/src/api.ts` ganha `listCompanies()`, `listOpportunities()`,
  `triggerSync()`.
- `App.tsx`: `OpportunitiesView` troca a prop `rows = sampleOpportunities`
  por `useEffect` chamando `listOpportunities()` — estado de carregamento e
  vazio em linguagem de negócio ("Nenhuma oportunidade ainda — rode uma
  sincronização em Configurações" em vez de tabela vazia sem contexto).
- `Dashboard.tsx`: troca `sampleMetrics` por métricas calculadas a partir
  de `listOpportunities()` real (reaproveita `core/dashboard_metrics.py`
  via uma rota nova `GET /dashboard-metrics`, ou calcula no frontend a
  partir da lista — decisão: **rota nova**, já que a lógica de KPI já
  existe em Python e duplicá-la em TS violaria DRY).
- Botão "Atualizar dados" — natural encaixe na tela de Configurações
  (Fase 0 já existe), aciona `POST /sync` e mostra resultado.

## Estratégia de teste

Mesmo padrão dos demais — sem framework novo.

- `sync_source`: provider mockado (reusa padrão `httpx.MockTransport` já
  usado em `test_salesforce_provider.py`, ou um provider fake in-memory
  tipo `ManualProvider` com dados pré-carregados), confirma normalização +
  persistência, confirma que erro de uma fonte não derruba a sincronização
  inteira.
- Rotas novas: `TestClient`, mesmo padrão de `test_routes_exports.py`/
  `test_settings.py`.
- Frontend: `logic.test.ts`-style pra qualquer lógica pura nova (ex.:
  formatação de resultado de sync); sem teste de render pesado.

## Fronteiras

- **Sempre:** erro de sincronização em linguagem de negócio, nunca
  exceção técnica. Suíte completa passa antes de fechar.
- **Nunca:** fingir que existe oportunidade gerada por regra — lista vazia
  é a resposta honesta até a Fase C existir. Nunca popular
  `Portfolio.product_ids` com valor inventado.

## Critérios de sucesso

- [ ] `POST /sync` ingere companies/contacts reais de uma fonte habilitada
      (testável com Manual, já que não exige credencial externa).
- [ ] `GET /companies`/`GET /opportunities` leem do banco de verdade.
- [ ] Frontend mostra dado real (mesmo que vazio) em vez de `sampleData`.
- [ ] Estado vazio em linguagem de negócio, não tabela em branco muda.
- [ ] Suíte completa (backend + frontend) passa.
- [ ] `CHANGELOG.md` atualizado, e o roadmap ganha nota clara: geração de
      oportunidade por regra continua pendente da Fase C.
