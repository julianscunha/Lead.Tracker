# Spec: Campos personalizados do Salesforce como contexto bruto

## Objetivo

`SalesforceProvider.fetch_context()` (`providers/salesforce.py`) hoje é um
stub: devolve `ProviderContext(company_id=company_id)` vazio. Esta feature faz
ele trazer de verdade os campos personalizados (`__c`) da conta Salesforce
correspondente, como dado bruto — sem decidir o que eles significam, sem
virar regra de oportunidade, sem passar por IA. Só coleta e normaliza no
formato do contrato `DataProvider`, exatamente como qualquer outro provider
(`providers/base.py`).

**Por que isso importa:** cada cliente configura campos personalizados
diferentes no Salesforce dele (segmento, data de renovação, produto
instalado). O núcleo do Lead.Tracker precisa continuar genérico — não pode
hardcodar nome de campo de nenhum cliente específico (CLAUDE.md: "core deve
permanecer genérico"). Capturar tudo como contexto bruto, sem exigir schema
conhecido, resolve isso agora; decidir *quais* campos viram atributo
estruturado de `Company` é decisão de produto adiada para uma fase futura de
mapeamento configurável (fora do escopo desta spec).

**Não objetivo (explicitamente fora de escopo):**
- Ligar esse contexto a uma chamada de IA de verdade (`AIRequest.provider_data`)
  — o pipeline que liga `fetch_context()` a uma chamada de IA real ainda não
  existe no backend (é a mesma lacuna de API real já identificada em conversas
  anteriores). Esta spec só garante que o dado certo está disponível no
  formato certo, pronto para ser consumido quando esse pipeline existir.
- Mapeamento configurável campo-a-campo via UI (fase futura).
- Campos personalizados de `Contact` (o contrato `fetch_context(company_id)`
  não recebe `contact_id` — ver "Questões em aberto").

## Comandos

```bash
python tests/test_salesforce_provider.py   # suíte do provider (será estendida)
python tests/test_config.py                # regressão geral, se algo mais mudar
```

Sem build/lint dedicado nessa camada (projeto Python puro, sem framework de lint configurado ainda).

## Estrutura afetada

```
providers/salesforce.py       → fetch_context() implementado de verdade
providers/base.py             → ProviderContext já tem campo `extra: dict` (sem mudança de contrato)
tests/test_salesforce_provider.py → novos testes para fetch_context()
CHANGELOG.md                  → entrada em [Unreleased]
```

## Design técnico

**Consulta:** `SELECT FIELDS(CUSTOM) FROM Account WHERE Id = '{company_id}' LIMIT 1`
via `_query()` já existente (reaproveita autenticação, retry, paginação —
paginação é irrelevante aqui pois `LIMIT 1`, mas o método já lida com isso
sem custo extra).

**Por que `FIELDS(CUSTOM)` e não listar campos manualmente:** essa função do
SOQL (Salesforce Spring '21+, API v51+; já estamos em v59.0) devolve todos os
campos personalizados da org sem eu precisar conhecer os nomes de antemão —
essencial porque cada instalação do Lead.Tracker aponta pra uma org Salesforce
diferente, com campos diferentes.
Fonte: [SELECT | SOQL and SOSL Reference](https://developer.salesforce.com/docs/atlas.en-us.soql_sosl.meta/soql_sosl/sforce_api_calls_soql_select_fields.htm).

**Caso "zero campos personalizados":** `FIELDS(CUSTOM)` sozinho em um objeto
sem nenhum campo `__c` retorna erro `MALFORMED_QUERY` (400) — não é uma falha
real, é a resposta esperada pra uma org sem customização. `fetch_context()`
deve tratar esse caso específico devolvendo `ProviderContext.extra = {}`, não
propagar `ProviderError`.

**Formato de saída:**
```python
ProviderContext(
    company_id=company_id,
    extra={"custom_fields": {"Segmento__c": "Enterprise", "Data_Renovacao__c": "2026-12-01", ...}},
)
```
Remove a chave `attributes` que o Salesforce injeta em todo registro (metadado
de tipo/URL, não é campo de negócio).

**Erros:** reaproveita a taxonomia já usada em `_query`/`_authenticate`
(`ProviderError` categorizado — `AUTHENTICATION`/`CONNECTIVITY`/`INTEGRATION`).
Único caso novo é o `MALFORMED_QUERY` tratado como "sem campos personalizados"
em vez de erro.

**Validação de `company_id`:** reaproveita `_SALESFORCE_ID_RE` já usado em
`fetch_contacts` — mesma fronteira de confiança, mesmo motivo (evitar
injeção SOQL).

## Estilo de código

Seguir o que já existe em `providers/salesforce.py` — método privado `async
def`, `ProviderError` com categoria explícita, docstring curta no topo do
método só quando o "porquê" não é óbvio (ex.: por que `FIELDS(CUSTOM)` em vez
de listar campos). Sem abstração nova — `fetch_context` chama `_query`
diretamente, como os outros métodos do provider.

## Estratégia de teste

Mesmo padrão de `tests/test_salesforce_provider.py`: `httpx.MockTransport`,
sem rede real, `assert`+`asyncio.run`, sem framework.

Casos obrigatórios:
1. `fetch_context` retorna `custom_fields` populado a partir de uma resposta
   simulada com campos `__c`.
2. Registro sem nenhum campo personalizado (org sem customização) →
   `MALFORMED_QUERY` (400) tratado como `extra={}`, não levanta erro.
3. `company_id` inválido → `ProviderError(INVALID_DATA)` antes de qualquer
   requisição (mesmo padrão do teste já existente para `fetch_contacts`).
4. A chave `attributes` do Salesforce nunca aparece no `extra` retornado.

## Fronteiras

- **Sempre fazer:** rodar a suíte completa de testes do backend antes de
  considerar a task concluída (16 arquivos hoje, ver README "Comandos").
  Atualizar `CHANGELOG.md`.
- **Perguntar antes:** qualquer mudança no contrato `DataProvider`
  (`providers/base.py`) — essa spec não deveria precisar tocar nele, já que
  `ProviderContext.extra` já existe.
- **Nunca fazer:** deixar `fetch_context` decidir oportunidade ou pontuar
  score a partir dos campos personalizados (isso é trabalho do
  `opportunity_engine`, nunca do provider). Nunca fazer essa chamada extra
  bloquear `fetch_companies`/`fetch_contacts` — `fetch_context` é chamado à
  parte, por empresa, sob demanda.

## Critérios de sucesso

- [ ] `fetch_context()` retorna campos personalizados reais de uma conta
      Salesforce, no formato `extra["custom_fields"]`.
- [ ] Org sem campos personalizados não gera erro — devolve `extra={}`.
- [ ] `company_id` inválido continua bloqueado antes de qualquer chamada de
      rede (mesma proteção contra injeção já validada em `fetch_contacts`).
- [ ] Todos os testes novos + suíte completa (16 arquivos) passam.
- [ ] `CHANGELOG.md` atualizado.

## Questões em aberto

1. **Campos personalizados de `Contact`**: o contrato atual
   (`fetch_context(company_id)`) não tem como pedir contexto de um contato
   específico. Fica de fora desta spec — se vier a ser necessário, é mudança
   de contrato (`providers/base.py`), não só deste provider, e merece spec
   própria.
2. **Quando isso realmente chega numa chamada de IA**: depende do pipeline de
   API real (ingestão → banco → `AIRequest.provider_data`) que ainda não
   existe. Esta spec não resolve isso — só deixa o dado pronto no formato
   certo para quando esse pipeline for construído.
