# Fase E — Prospecção geográfica (Google Maps)

Spec viva desta fase (`spec-driven-development`) — atualizada a cada
módulo entregue, não escrita de uma vez no início. Ver `docs/roadmap.md`
pro texto original dos requisitos; este documento registra as decisões
de como implementar cada um, o porquê, e o que cada módulo entrega.

## Capability map (consulta ao agente `Plan`, confirmado pelo usuário)

Fase E cruza pelo menos 4 fronteiras de responsabilidade (config/ICP,
coleta de provider, motor de scoring/anti-spam, apresentação/export) que
hoje não existem como módulos isolados — passou pelo Phase 0 (scope
check) do `spec-driven-development` antes de qualquer spec de módulo.

| Ordem | Módulo | Responsabilidade | Consulta a especialista |
|---|---|---|---|
| 1 | `icp-profile-store` | Critério de ICP por instalação como config genérica (categoria, porte, raio, produto de referência) — schema-less, mesmo padrão da config de Fontes. | Não (mecânica) |
| 2 | `places-signal-collector` | Provider Google Places: coleta bruta (categoria, business_status, reviews) — normaliza, nunca pontua. | Não (mecânica) |
| 3 | `icp-auto-derivation` | Deriva ICP sugerido a partir de Company⋈Opportunity onde `is_customer=true` e `opportunity_score` alto. | Sim — Growth Hacker/Sales Engineer (threshold de score, amostra mínima) |
| 4 | `geo-scoring-rules` | Regras determinísticas em camadas (categoria > business_status=OPERATIONAL > reviews como proxy fraco) dentro do `opportunity_engine` genérico. | Sim — Outbound Strategist (hierarquia de sinais, pesos) |
| 5 | `anti-spam-promotion-gate` | Score mínimo configurável pra sair de `detected`; cap de contatos por lote/dia por rep. | Sim — Outbound Strategist/Sales Engineer (cap errado = spam real) |
| 6 | `icp-wizard-ui` | Assistente de 3-4 passos (produto → raio → revisar → confirmar). | Sim — Discovery Coach/Sales Engineer (fluxo, fricção) |
| 7 | `geo-results-view` | Mapa/lista visual dos resultados — não tabela crua. | Sim — Sales Engineer/Discovery Coach |
| 8 | `geo-export` | Reuso do exportador PDF/Excel já existente em Oportunidades. | Não (mecânica) |

Ordem de construção: `icp-profile-store` → `places-signal-collector`
(paralelizáveis) → `icp-auto-derivation` → `geo-scoring-rules` →
`anti-spam-promotion-gate` → `icp-wizard-ui` → `geo-results-view` →
`geo-export`.

**Riscos arquiteturais registrados pelo Plan:**
- `geo-scoring-rules`/`anti-spam-promotion-gate` são onde é mais fácil
  violar "core nunca hardcode de vendor" (tentação de `if
  business_status == 'OPERATIONAL'` direto no engine) — contrato
  genérico ("sinal de status normalizado") precisa existir antes do
  provider.
- `icp-auto-derivation` corre risco de viés estatístico com amostra
  pequena de clientes satisfeitos — piso mínimo de amostra antes de
  sugerir automaticamente, cai no fluxo manual do wizard abaixo disso.
- Nenhum módulo precisa de dependência ou abstração nova — todos
  reaproveitam padrões já existentes (config de Fontes, exportador de
  Oportunidades, `opportunity_engine`).

## Módulo 1 — `icp-profile-store`

Classificado "mecânico" no capability map — sem consulta a especialista
(é só extensão do padrão de config já validado nas Fases 0-D). Novo
modelo `ICPProfile`: `reference_product_id`, `place_category`,
`company_size_hint`, `radius_km`. **Singleton** — uma linha só por
instalação, `id` sempre fixo `"icp_profile"`, nunca aceito do corpo da
requisição (`ICPProfileIn` não tem campo `id`) — fecha qualquer
possibilidade de o cliente HTTP criar uma 2ª configuração concorrente.
`place_category`/`company_size_hint` são string livre, nunca enum
fechado — núcleo genérico, a UI do wizard (módulo 6, ainda não
construído) é quem restringe as opções mostradas.

`GET /icp-profile` antes de qualquer `PUT` devolve 200 com todos os
campos `None`, nunca 404 — é config opcional de uma feature ainda em
construção, não um recurso que "não existe". `radius_km` negativo é
rejeitado na fronteira HTTP (`Field(ge=0)`), `None` (sem raio
configurado ainda) continua aceito.

Revisão de código: **aprovado sem pendências** — singleton confirmado
inquebrável, contrato GET-antes-de-PUT verificado, ausência de taxonomia
fechada confirmada, escopo mínimo respeitado (nenhuma lógica de
scoring/oportunidade vazou pra este módulo).

### Teste

- Modelo: defaults (`id` fixo, todos os outros `None`).
- Repositório: `get` antes do primeiro `save` retorna `None`; round-trip;
  segundo `save` faz upsert na mesma linha (nunca duplica).
- Rota: `GET` antes de qualquer `PUT` retorna 200 com corpo todo `None`
  (nunca 404); `PUT` round-trip e upsert; `radius_km` negativo rejeitado
  (422).

### Critério de sucesso

- [x] Singleton nunca duplica, `id` nunca vem de input do usuário.
- [x] `place_category`/`company_size_hint` sem taxonomia fechada.
- [x] `GET` antes do primeiro `PUT` nunca 404.
- [x] Suíte completa e revisão de código sem pendências.

## Módulo 2 — `places-signal-collector`

**Decisão de arquitetura resolvida durante a implementação** (não estava
resolvida no capability map original): `DataProvider.fetch_companies()`
genérico é chamado por `backend/sync.py::sync_source()` via `provider =
source.build(env)` — construção síncrona, só a partir do `.env`, sem
acesso a sessão de banco. O critério de busca do Google Maps (origem
geográfica, raio, categoria) mora no `ICPProfile` (banco, módulo 1), não
no `.env`. Resolvido decidindo que `GoogleMapsProvider` **não participa**
do laço `/sync` periódico — `fetch_companies()` sempre retorna `[]` de
propósito (documentado em 3 lugares: docstring do módulo, comentário do
método, este spec). A busca de verdade é `discover(origin_address,
radius_km, place_category) -> list[PlaceSignal]`, sob demanda, que será
chamada pelo wizard (módulo 6, ainda não construído).

**Decisão de produto perguntada direto ao usuário** (não era óbvia nem
mecânica, apesar do módulo estar classificado "mecânico" no capability
map): de onde vem a origem geográfica da busca? Resposta: endereço
cadastrado manualmente no ICP, não derivado de cliente nenhum — mais
simples e previsível, funciona mesmo sem clientes cadastrados ainda.
Adicionado `ICPProfile.search_origin_address: str | None` (módulo 1,
retroativo).

Endpoints confirmados via fonte oficial (WebFetch, mesma disciplina da
Fase A): Geocoding API (`GET .../geocode/json`, status
OK/ZERO_RESULTS/REQUEST_DENIED/INVALID_REQUEST/OVER_QUERY_LIMIT) e
Places API (New) Nearby Search (`POST
https://places.googleapis.com/v1/places:searchNearby`, headers
`X-Goog-Api-Key`/`X-Goog-FieldMask`, corpo
`locationRestriction.circle.center.{latitude,longitude}`+`radius` em
metros, `includedTypes`). `_MAX_RADIUS_KM = 50.0` — limite físico da
API (50000m) — validado ANTES de qualquer chamada de rede, junto com
`radius_km <= 0`.

`PlaceSignal` (place_id, name, category, business_status, rating,
review_count, formatted_address) é só dataclass de transporte — nenhuma
lógica de scoring/threshold aqui (isso é `geo-scoring-rules`, módulo 4).

**Achados da revisão de código** (2, Important, ambos corrigidos):
1. `_geocode`/`discover` indexavam o corpo da resposta direto
   (`body["results"][0]...`, `place["id"]`) sem tratar o caso de status
   "OK"/200 com formato inesperado (results vazio, campo faltando) —
   vazaria `KeyError`/`IndexError` cru pra quem chama `discover()`
   diretamente (o wizard, módulo 6, não tem nenhum try/except genérico
   no meio como `test_connection()` tem via `routes_settings.py`).
   Corrigido com `try/except (KeyError, IndexError/TypeError)` →
   `ProviderError(INTEGRATION)` nos dois pontos.
2. Faltava teste do caminho "erro transitório persiste além do retry" —
   regra "retry só em transitório, nunca em credencial inválida"
   (CLAUDE.md) não tinha cobertura de que o retry realmente para depois
   de 1 tentativa extra e vira `CONNECTIVITY`. Adicionado pros dois
   pontos de chamada de rede (`_geocode` e `searchNearby`).

### Não objetivo deste módulo

- Nenhuma persistência de `PlaceSignal` — é transporte efêmero,
  consumido por quem chamar `discover()` (módulo 4, ainda não existe).
- Nenhuma UI — wizard é módulo 6.
- Nenhuma lógica de scoring/descarte de fechados — isso é módulo 4.

### Teste

- Contrato: `GoogleMapsProvider` implementa `DataProvider`; chave
  ausente levanta `ConfigurationError`.
- `fetch_companies()`/`fetch_contacts()` sempre `[]`, nunca fazem
  requisição de rede (mock com `assert False` no handler prova isso).
- `discover()`: raio ≤0 e raio >50km rejeitados sem chamada de rede;
  fluxo feliz geocodifica então busca e normaliza sinal; categoria
  ausente omite `includedTypes`; erros categorizados (`ZERO_RESULTS`,
  `REQUEST_DENIED`, 403, 429); retry persistente em 5xx (`_geocode` e
  `searchNearby`) vira `CONNECTIVITY` após exatamente 1 retry; resposta
  malformada (`OK` com `results=[]`, `place` sem `id`) nunca vaza
  `KeyError`/`IndexError`.

### Critério de sucesso

- [x] `GoogleMapsProvider` implementado, integrado em `SOURCES`
      (`implemented=True`).
- [x] `fetch_companies()` nunca quebra o `/sync` — retorna `[]` de
      propósito, documentado.
- [x] `discover()` nunca vaza exceção técnica crua — toda falha vira
      `ProviderError` categorizado.
- [x] Suíte completa (20 arquivos) e revisão de código sem pendências
      após os 2 achados corrigidos.

## Módulo 3 — `icp-auto-derivation`

Consulta ao agente Growth Hacker antes de implementar (decisão de
negócio, registrada no docstring de `core/icp.py`):

1. **"Cliente satisfeito"** = `Company.is_customer=True` com pelo menos
   uma `Opportunity.opportunity_score >= 0.7` (threshold fixo — amostra
   pequena no início de uso faria estatística (top-N%, média±desvio)
   virar ruído; fixo é previsível e auditável).
2. **Amostra mínima de 5** clientes satisfeitos pra `confidence="high"`
   — abaixo disso, a sugestão AINDA é calculada e devolvida (nunca
   escondida), só marcada `confidence="low"`. Decidir usar ou não já é
   do usuário no wizard (módulo 6).
3. **Moda sempre**, nunca recusa sugerir por falta de maioria clara — a
   proporção da moda (`*_share`) acompanha a sugestão pra UI mostrar
   contexto quando fraca.
4. **`company_size_hint`** deriva de `Company.segment` (já presente),
   não de `Company.employee_count` (dado parcial, só populado por
   Salesforce desde a Fase A — usar hoje enviesaria a amostra).

`derive_icp_suggestion` (core/icp.py, pura) retorna `None` quando não há
nenhum cliente satisfeito (distinto de `confidence="low"`, que sempre
carrega uma sugestão real). `GET /icp-suggestion` só calcula e devolve —
nunca persiste automaticamente no `ICPProfile` (só o usuário confirma
isso no wizard, módulo 6, ainda não construído).

**Achados da revisão de código** (3, Important, todos corrigidos):
1. O campo derivado se chamava `place_category` — mesmo nome de
   `ICPProfile.place_category` (módulo 1), mas taxonomia incompatível:
   `ICPProfile.place_category` é um `type` real da Google Places API
   (ex. "car_dealer"), o que dá pra derivar aqui é a moda de
   `Company.industry` (vertical de negócio livre, ex. "Varejo"). Nomes
   iguais sugeririam ao wizard que dá pra jogar a sugestão direto no
   perfil, quebrando `discover()` silenciosamente. Renomeado pra
   `industry_hint`.
2. Esta seção da spec estava faltando — a consulta ao especialista tinha
   acontecido mas não ficou registrada por escrito, quebrando a própria
   disciplina de "spec viva" que as seções anteriores seguiam.
3. Docstring da rota dizia "204 implícito via corpo null" — errado: é
   200 com corpo JSON `null`, nunca 204 (que não carrega corpo). Corrigido.

### Não objetivo deste módulo

- Nenhuma auto-aplicação no `ICPProfile` — só cálculo e leitura.
- Nenhum mapeamento de `industry_hint` pra uma categoria real do Google
  Places — fica pro wizard (módulo 6) ou pro usuário decidir na revisão.
- Nenhum uso de `Company.employee_count` (decisão consciente do Growth
  Hacker, ver item 4 acima).

### Teste

- `derive_icp_suggestion`: `None` sem cliente satisfeito (distinto de
  `confidence="low"`); usa o MAIOR score entre as oportunidades da
  empresa, não o primeiro; `opportunity_score=None` nunca conta;
  prospect com score alto nunca conta (precisa `is_customer=True`);
  moda+proporção calculada corretamente com maioria fraca (2/5, não
  unânime); campo omitido (`None`) quando todos os satisfeitos têm o
  atributo vazio, nunca `ZeroDivisionError`.
- Rota: `null` (200) sem cliente satisfeito; reflete corretamente
  clientes satisfeitos reais, incluindo a proporção exata da moda.

### Critério de sucesso

- [x] Threshold/amostra mínima/moda seguem exatamente a decisão do
      Growth Hacker, registrada por escrito.
- [x] `None` (nada pra derivar) nunca confundido com `confidence="low"`
      (sugestão real, fraca).
- [x] Nomes de campo nunca colidem com taxonomias incompatíveis entre
      módulos.
- [x] Suíte completa e revisão de código sem pendências.

## Módulo 4 — `geo-scoring-rules`

Consulta ao agente Outbound Strategist antes de implementar (hierarquia
de sinais e pesos são decisão de negócio, registrada no docstring de
`core/geo_scoring.py`). `score_place_signal(signal, icp_category) ->
float | None` pontua `PlaceSignal` (módulo 2) em 3 camadas:

1. `business_status` em `CLOSED_TEMPORARILY`/`CLOSED_PERMANENTLY` →
   **descarte determinístico**, `None` (não `0.0`) — tipo de retorno
   diferente, não valor baixo, pra nenhum threshold do módulo 5
   conseguir reverter e reativar um lugar fechado.
2. Categoria bate (`base=0.7`) / não bate (`base=0.2`, nunca descarte —
   só `business_status` tem garantia "ponto final") / sem ICP
   configurado (`base=0.5`, neutro).
3. `rating`(1.0-5.0)/`review_count` (cap 50) — bônus até 0.15 cada,
   máximo combinado 0.30, sempre menor que o gap 0.7-0.2=0.5 entre bate
   e não bate — a hierarquia nunca se inverte. Ausência de dado é
   neutra (bônus 0.0), nunca penalidade.

**Achado da revisão de código** (Important, corrigido): a checagem
original só tratava `None`/`"OPERATIONAL"` como não-descarte, mas
`"BUSINESS_STATUS_UNSPECIFIED"` é um valor real do enum da Places API
que significa "não sabemos", nunca "sabemos que fechou" — tratá-lo como
fechado descartaria lugares só por falta de certeza do Google. Corrigido
pra incluir esse valor junto com `None` no não-descarte. Testes
adicionais também cobriram `category_matches` com string vazia e
`rating` fora da faixa 1.0-5.0 (clamp nos dois extremos).

### Não objetivo deste módulo

- Nenhuma decisão de "vira Opportunity ou não" — isso é
  `anti-spam-promotion-gate` (módulo 5), que aplica o corte sobre o
  score contínuo devolvido aqui.
- Nenhuma persistência — função pura, sem I/O.

### Teste

- Descarte: `CLOSED_TEMPORARILY`/`CLOSED_PERMANENTLY` sempre `None`
  independente de outros sinais; `None`/`"OPERATIONAL"`/
  `"BUSINESS_STATUS_UNSPECIFIED"` nunca descartam.
- Hierarquia: pior caso de "bate" (sem reviews) sempre acima do melhor
  caso de "não bate" (reviews máximos) — verificado matematicamente e
  por teste.
- `category_matches`: case-insensitive; `None`/string vazia em qualquer
  lado nunca "bate" (incluindo o caso de ambos os lados vazios).
- Bônus: rating mínimo/máximo (1.0/5.0) e fora da faixa (0.0/6.0)
  clampados corretamente; review count no cap (50) e acima dele
  produzem o mesmo bônus máximo; ausência de rating/reviews é neutra
  (score = base exata, nunca penalizado); score nunca passa de 1.0.

### Critério de sucesso

- [x] Descarte de `business_status` é tipo de retorno diferente
      (`None`), nunca valor dentro da escala 0-1.
- [x] Hierarquia categoria > reviews matematicamente garantida, nunca
      dependente só de teste.
- [x] `BUSINESS_STATUS_UNSPECIFIED` tratado como "não sabemos", nunca
      como fechado.
- [x] Suíte completa e revisão de código sem pendências.
