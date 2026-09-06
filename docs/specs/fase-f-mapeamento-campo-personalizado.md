# Fase F — Mapeamento configurável de campo personalizado

Depende da Fase A (contexto bruto do Salesforce já chegando via
`fetch_context`/`FIELDS(CUSTOM)`) e reaproveita a mesma tela de
configuração de fontes já existente (Fase 0).

## Mapa de capacidades (confirmado pelo usuário)

| Ordem | Módulo | Responsabilidade | Consulta a especialista |
|---|---|---|---|
| 1 | `sobject-field-catalog` | Descoberta via `sobjectDescribe` dos campos personalizados do `Account` (rótulo + tipo), sem exigir API name. | Salesforce Architect |
| 2 | `semantic-field-role` | Enum fechado e genérico no core (`industry_hint`, `deal_size_hint`, `renewal_date`, ...), sem referência a Salesforce. | Não (mecânico) |
| 3 | `field-mapping-store` | Config por instalação (não por company): `(provider_id, source_field_api_name, source_field_label, role)`, mesmo padrão de `ICPProfile`/`RepTarget`. | Não (mecânico) |
| 4 | `mapping-driven-context-split` | Campo mapeado grava no destino certo (reaproveitando `Company.industry`/`Company.renewal_date` quando existem); campo sem mapeamento continua em `custom_fields` pra IA — Fase A não pode regredir. | Salesforce Architect (curta — decisão de precedência/destino) |
| 5 | `mapping-config-ui` | Tela: campo do Salesforce → dropdown de papel semântico → status, linguagem não-técnica. | Sales Engineer |
| 6 | `mapping-health-check` | Catálogo atual vs. mapeamentos salvos; campo sumido/mudado de tipo vira aviso em linguagem de negócio no `health_check()`. | Sales Engineer |

**Decisão confirmada (`raw_context`)**: não é um valor explícito do
enum — é a ausência de linha na tabela de mapeamento, idêntico ao
comportamento já existente da Fase A (campo sem mapeamento continua
como contexto bruto pra IA, sem exigir uma escolha extra do usuário).

**Riscos de arquitetura identificados no planejamento** (a mitigar
módulo a módulo, não resolvidos de antemão):
- `field-mapping-store` guarda `provider_id` como string genérica —
  nunca uma tabela/import específico de Salesforce no core.
- Precedência quando `Company.industry`/`renewal_date` já têm valor
  estrutural E existe um mapeamento pro mesmo papel: mapeamento só
  preenche campo vazio, nunca sobrescreve (mesmo padrão de
  `merge_pair`) — decisão a confirmar no módulo 4.
- `deal_size_hint` (e qualquer papel sem campo estrutural hoje) só
  ganha destino novo quando realmente necessário — nada de `dict`
  genérico especulativo criado cedo demais.
- `mapping-health-check` é checagem de configuração, nunca um segundo
  motor de regras — nunca decide oportunidade nem reclassifica campo
  sozinho.

## Módulo 1 — `sobject-field-catalog`

Consulta ao agente Salesforce Architect antes de implementar (decisões
abaixo não devem ser reabertas):

- **Chamada**: `GET {instance_url}/services/data/v59.0/sobjects/Account/describe`
  (Metadata API — endpoint REST direto, não SOQL; reaproveita `_send`
  pra timeout/retry, não passa por `_query`).
- **Filtro de campos oferecidos**: `custom=True AND updateable=True`.
  `updateable=False` já é a interseção certa — cobre fórmula, rollup
  summary e qualquer campo protegido, sem precisar checar `calculated`
  separadamente. Nenhum filtro por `type`: decidir se um tipo serve
  pra um papel semântico é responsabilidade da UI de mapeamento
  (módulo 5), não deste catálogo.
- **Cache**: em memória por instância do provider
  (`self._field_catalog_cache: tuple[list[SalesforceFieldInfo], datetime] | None`),
  TTL de 1h — describe é uma chamada pesada (payload com todos os
  campos padrão+custom da org) e conta pro limite diário de
  requisições. `force_refresh: bool = False` bypassa o cache — vai
  virar o botão "atualizar catálogo" da UI (módulo 5) e também é
  usado pelo `mapping-health-check` (módulo 6), que não pode confiar
  em cache desatualizado pra detectar campo removido.
- **Erros**: reautentica uma vez em 401/403 (mesmo padrão recursivo de
  `_query`); 404 vira `NOT_FOUND` ("objeto Account não acessível");
  5xx/429 reusa `_TRANSIENT_STATUS`/retry existente; corpo malformado
  (200 mas JSON inesperado) vira `INTEGRATION`, nunca uma exceção
  técnica crua.

**Achados da revisão de código** (3 Sugestões, todas aplicadas —
nenhum Crítico/Importante):
1. `_describe_account` fazia `response.json()` sem `try/except`
   próprio — funcionava porque o único chamador já envolvia a chamada
   num `try/except (ValueError, ...)`, mas deixava o método inseguro
   por si só caso ganhasse outro chamador no futuro. Corrigido: parse
   de JSON agora tem seu próprio `try/except → ProviderError`, mesmo
   padrão de `_authenticate`.
2. Faltava teste pra campo do describe sem as chaves `custom`/
   `updateable` (em vez de `false` explícito) — `.get()` já tratava
   corretamente (default `None`, falsy), mas sem teste provando.
   Adicionado `test_describe_custom_account_fields_treats_missing_flags_as_false`.
3. Teste de TTL expirado manipula `provider._field_catalog_cache`
   diretamente (sem clock injetável) — aceito como está pela revisão;
   é o jeito mais simples dado que o provider não tem um `_now()`
   injetável hoje.

### Não objetivo deste módulo

- Filtro por `type` de campo — fica pra tela de mapeamento (módulo 5),
  que sabe qual tipo serve pra qual papel semântico.
- Cache persistente (SQLite/Redis) — TTL em memória por processo já
  cobre o caso de uso (tela de configuração aberta várias vezes na
  mesma sessão do backend).
- Teste de isolamento de cache entre duas instâncias distintas do
  provider — trivialmente correto por ser atributo de instância
  (sugestão da revisão, não crítico o suficiente pra travar aqui).

### Teste

- `describe_custom_account_fields`: filtra corretamente
  custom+updateable (fórmula custom fica de fora, campo padrão
  updateable fica de fora); cache reusado entre chamadas na mesma
  janela de TTL; `force_refresh=True` sempre busca de novo; cache
  expirado (TTL passado) busca de novo mesmo sem `force_refresh`;
  404→`NOT_FOUND`; reautentica uma vez em 401 e recupera; corpo
  malformado→`INTEGRATION`; campo sem chaves `custom`/`updateable`
  tratado como ausente, nunca `KeyError`.
- Suíte completa (30 testes em `test_salesforce_provider.py`, todos
  via `httpx.MockTransport`, nenhuma chamada de rede real).

### Critério de sucesso

- [x] Nenhum código específico de Salesforce vaza pro contrato
      genérico `DataProvider` (`describe_custom_account_fields` é
      método próprio do `SalesforceProvider`, não um dos 4 métodos
      abstratos).
- [x] Erro técnico nunca vaza cru — todo caminho de falha vira
      `ProviderError` com categoria e mensagem acionável.
- [x] Revisão de código sem achados Críticos/Importantes.

## Módulos 2 e 3 — `semantic-field-role` e `field-mapping-store`

Ambos classificados como mecânicos no mapa de capacidades (sem
consulta a especialista) e revisados juntos por serem pequenos e o
módulo 3 depender diretamente do enum do módulo 2.

**Módulo 2**: `SemanticFieldRole(str, Enum)` em `core/models.py` —
`INDUSTRY_HINT`, `DEAL_SIZE_HINT`, `RENEWAL_DATE`. **Decisão
confirmada**: nenhum valor `raw_context` no enum — campo sem
mapeamento explícito já continua como contexto bruto pra IA por
padrão (comportamento pré-existente da Fase A); a ausência de linha
na tabela de mapeamento (módulo 3) já significa isso.

**Módulo 3**: `FieldMapping` (`core/models.py`) + `FieldMappingORM`
(`core/db_models.py`) + repositório (`save_field_mapping`,
`list_field_mappings(session, provider_id)`,
`delete_field_mapping(session, mapping_id)`). Config **por
instalação**, nunca por company — mesmo padrão de `ICPProfile`/
`RepTarget`. Id determinístico via `field_mapping_id(provider_id,
source_field_api_name)` (`core/opportunity_engine.py`, mesmo padrão
de `rep_target_id`): cadastrar mapeamento de novo pro mesmo campo é
upsert, nunca duplicata. `provider_id` é string livre e genérica —
nenhuma referência a Salesforce em `core/`.

**Revisão de código**: aprovada sem achados Críticos/Importantes.
Um ponto investigado e conscientemente não escalado: leitura de
`FieldMapping.role` a partir do banco (`SemanticFieldRole(row.role)`)
não tem try/except — um valor de role legado/removido derrubaria a
leitura com `ValueError` cru. Não é regressão deste módulo (mesmo
padrão já usado em todo enum persistido como string no repositório) e
não há hoje nenhum caminho de remoção/deprecação de valor de enum na
Fase F — risco especulativo, não real; se blindar, é item transversal
("todos os enums persistidos"), não específico deste diff. A revisão
também corrigiu o comentário desatualizado em
`test_db_table_registration.py` (ainda dizia "13 tabelas"/lista sem
`field_mappings`).

### Não objetivo destes módulos

- Try/except na leitura de enum persistido — aceito como risco
  especulativo transversal, não resolvido aqui.
- Rota HTTP/UI pra criar ou listar mapeamentos — isso é módulo 5
  (`mapping-config-ui`), que ainda não existe nesta fatia.

### Teste

- `SemanticFieldRole`: valores exatos e nunca contêm referência a
  "salesforce" (guard-rail automatizado da regra "core genérico").
- `FieldMapping`: round-trip; upsert pro mesmo (provider_id,
  source_field_api_name) nunca duplica; dois providers diferentes
  mapeando o mesmo `source_field_api_name` não colidem; delete remove;
  delete de id inexistente é no-op seguro.
- `test_db_table_registration.py`: contagem bumped de 13→14
  (`field_mappings`).

### Critério de sucesso

- [x] Nenhuma referência a Salesforce em `core/`.
- [x] Upsert por chave natural nunca duplica mapeamento.
- [x] Revisão de código sem achados Críticos/Importantes.

## Módulo 4 — `mapping-driven-context-split`

Consulta curta ao agente Salesforce Architect (decisões abaixo
confirmadas, não reabrir):

- **Onde o split acontece**: em `backend/sync.py::sync_source()`
  (nova função `_apply_field_mappings_for_synced_companies`), nunca
  dentro do provider — `fetch_context()` continua devolvendo só o
  bruto; provider nunca pode depender do repositório/domínio
  (direção de dependência do projeto).
- **Custo**: só chama `fetch_context()` (1 requisição por empresa)
  quando existe pelo menos 1 `FieldMapping` pra aquela fonte —
  instalação sem Fase F configurada (caso comum hoje) não paga custo
  extra nenhum, comportamento idêntico ao de antes deste módulo.
- **Precedência**: campo mapeado **sempre sobrescreve** o campo
  estrutural correspondente, nunca "só se vazio" como
  `merge_pair` faz pra outros campos — é o usuário escolhendo
  explicitamente aquele campo customizado como fonte de verdade pro
  papel, uma decisão deliberada, não um merge implícito entre fontes
  conflitantes.
- **`deal_size_hint`**: novo campo estrutural de primeira classe em
  `Company`, mesmo nível de `industry`/`annual_revenue` — não existia
  destino antes, criado especificamente pra isto.
- **Dedup**: campo mapeado sempre sai do contexto bruto restante
  (`custom_fields`), com valor válido ou não — é a configuração de
  mapeamento, não o valor de uma empresa em particular, que decide se
  o campo é estrutural. **Achado do planejamento**: `fetch_context()`/
  `ProviderContext.extra["custom_fields"]` está órfão desde a Fase A —
  nenhum consumidor real em `ai/`/`backend/` hoje. Construir esse
  consumidor (contexto bruto de fato chegando à IA) fica fora do
  escopo desta fatia — o módulo 4 só garante que o campo MAPEADO tem
  destino certo; o resto continua exatamente tão não-conectado quanto
  antes, sem regressão.

**Achados da revisão de código** (1 Importante, corrigido; 1
Sugestão de teste aplicada; demais aceitas sem ação):
1. **Importante**: `_apply_field_mappings_for_synced_companies`
   escrevia o valor mapeado no banco mas nunca atualizava o objeto
   `Company` em memória (`to_persist`) — como
   `_evaluate_rules_for_synced_companies` roda logo depois usando
   esses mesmos objetos, o motor de regras avaliaria contra
   `industry`/`deal_size_hint` ainda `None` na mesma rodada de sync,
   só refletindo o valor mapeado no PRÓXIMO `/sync`. Silencioso hoje
   (nenhuma regra lê esses campos ainda), mas seria um bug real no
   dia em que uma regra passasse a usar `deal_size_hint` — exatamente
   o motivo do campo existir. Corrigido: a função agora também
   substitui `to_persist[native_id]` por uma cópia atualizada
   (`model_copy(update=updates)`), mutando o mesmo dict que
   `sync_source` passa adiante.
2. Faltava teste de `RENEWAL_DATE` parseando o formato DateTime do
   Salesforce com offset sem dois-pontos (`"...T00:00:00.000+0000"`),
   só o formato Date puro (`"YYYY-MM-DD"`) estava coberto —
   `datetime.fromisoformat` só aceita esse formato a partir do Python
   3.11 (confirmado contra a versão instalada). Adicionado teste
   dedicado nos dois arquivos (função pura e integração de sync).
3. Aceitas sem ação (risco de baixa prioridade, já no mesmo padrão de
   tolerância do resto do arquivo): `apply_field_mapping_updates` sem
   controle de versão/lock otimista (mesma classe de risco já aceita
   em `recompute_daily_snapshot`); `merge_pair`'s `industry` usando
   `or` em vez de `is not None else` (pré-existente, não tocado nesta
   fatia); falta de teste de integração com múltiplos papéis mapeados
   ao mesmo tempo (já coberto no nível de função pura).

### Não objetivo deste módulo

- Construir um consumidor real pro contexto bruto restante
  (`custom_fields` não-mapeado) virar prompt de IA de fato — infra
  que nunca existiu desde a Fase A, fora do escopo desta fatia.
- Lock otimista/controle de versão em `apply_field_mapping_updates` —
  aceito como risco de baixa probabilidade (sync concorrente da mesma
  fonte não é um cenário real hoje).

### Teste

- `split_custom_fields` (função pura, `tests/test_field_mapping.py`,
  14 testes): cada papel escreve na coluna certa; datas ISO e
  DateTime-com-offset parseiam; número e string numérica parseiam
  pra `deal_size_hint`; `bool` explicitamente rejeitado (subclasse de
  `int` em Python); valor vazio/`None`/não-parseável nunca escreve
  nem derruba, mas ainda sai do contexto bruto restante; campo sem
  mapeamento permanece no bruto; múltiplos papéis simultâneos.
- Integração (`tests/test_sync.py`, 8 testes novos): sem mapeamento
  nunca chama `fetch_context` (custo zero); mapeamento escreve campo
  estrutural; mapeamento sempre sobrescreve valor já existente;
  `deal_size_hint` numérico; valor não-parseável não derruba nem
  escreve; **objeto em memória reflete o valor mapeado na mesma
  rodada** (regressão do achado Importante); DateTime Salesforce com
  offset; falha de `fetch_context` vira erro reportado sem abortar o
  sync.
- `merge_pair` (`tests/test_normalization.py`, 2 testes novos):
  preserva `deal_size_hint=0.0`; nunca zera valor já promovido quando
  o fetch fresco da fonte não traz o campo (que é sempre o caso —
  `fetch_companies()` nunca popula `deal_size_hint`).

### Critério de sucesso

- [x] Campo mapeado disponível pro motor de regras na MESMA rodada de
      sync em que foi promovido, não só na próxima.
- [x] Nenhum custo de rede extra pra instalação sem Fase F
      configurada.
- [x] `renewal_date`/`deal_size_hint`/`industry` mapeados nunca são
      revertidos por uma sincronização subsequente.
- [x] Revisão de código sem achados Críticos pendentes.
