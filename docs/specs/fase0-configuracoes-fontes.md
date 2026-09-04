# Spec: Fase 0 — Configurações de Fontes

Ver `docs/roadmap.md` (Fase 0) pro contexto de por que essa fase é
pré-requisito de tudo. Esta spec detalha o que a fase anterior deixou em
alto nível.

## Objetivo

Tela onde o usuário liga/desliga cada fonte de dado (hoje: Manual,
Salesforce; Website e Google Maps aparecem como "em breve" até seus
providers existirem) e cadastra credencial sem editar `.env` na mão — com
feedback imediato de conexão no próprio ato de ligar. Sem essa tela, o
projeto viola sua própria regra ("usuário configura tudo por tela, nunca
editando `.env` na mão").

Sucesso = um operador não-técnico consegue ligar o Salesforce sozinho, sem
precisar saber o que é `.env`, OAuth ou Client Credentials Flow.

## Design técnico

### Registro de fontes (genérico, sem hardcode por fonte na UI)

Um descritor por fonte, `backend/settings.py` (novo):

```python
@dataclass
class SourceDescriptor:
    id: str                      # "manual" | "salesforce" | "website" | "google_maps"
    label: str                   # "Salesforce" — nome exibido
    enabled_key: str             # "SALESFORCE_ENABLED"
    fields: list[SourceField]    # credenciais, vazio pra manual
    implemented: bool            # False pra website/google_maps até os providers existirem

@dataclass
class SourceField:
    key: str                     # "SALESFORCE_CLIENT_ID"
    label: str                   # "Identificador do Aplicativo Conectado"
    help_text: str                # explicação curta em português
    secret: bool                  # True esconde valor no GET e mascara no input
```

Lista de descritores é dado estático no módulo — cada fonte nova (Website,
Google Maps, quando implementadas) só precisa de uma entrada nova aqui,
nunca lógica de UI nova. Fonte com `implemented=False` aparece na tela
desabilitada com rótulo "Em breve".

### Rotas (`backend/routes_settings.py`, montada em `backend/main.py`)

- `GET /modules/lead_tracker/settings` → lista todas as fontes com:
  `id`, `label`, `implemented`, `enabled` (lido do `.env`), e por campo:
  `key`, `label`, `help_text`, `has_value` (bool — nunca o valor em si se
  `secret=True`), `last_check: {status: "connected"|"failed"|"unknown", message, checked_at}`.
- `PUT /modules/lead_tracker/settings/{source_id}` → body `{enabled: bool,
  fields: dict[str, str]}`. Grava no `.env` via `set_env_values()` (nova
  função em `core/config.py`, ver abaixo). Campo com valor vazio no body
  não apaga um valor já salvo (mesma filosofia não-destrutiva do
  `sync_env`) — só atualiza campo explicitamente enviado com valor não-vazio.
- `POST /modules/lead_tracker/settings/{source_id}/test` → instancia o
  provider (se `implemented=True`) com os valores atuais do `.env` e chama
  `test_connection()`. Resposta: `{is_connected: bool, message: str}` —
  `message` já em linguagem de negócio (o provider já garante isso via
  `ProviderError`). Fonte não implementada retorna erro amigável
  ("Esta fonte ainda não está disponível nesta versão"), nunca 500.
- Todas as rotas seguem o padrão de erro já existente
  (`DomainError`→`HTTPException` da tabela categoria→status, igual
  `routes_exports.py`).

### `core/config.py` — nova função `set_env_values`

```python
def set_env_values(env_path: Path, values: dict[str, str]) -> None:
    """Atualiza ou adiciona cada chave em values no .env, preservando
    comentários, linhas em branco e qualquer chave não mencionada.
    Nunca remove/zera uma chave existente com valor vazio em values."""
```
Complementa `sync_env` (que só adiciona chave ausente do template) — esta
função assume a chave já existe (veio do template) e só troca o valor.

### Frontend (`frontend/src/settings/`, pasta nova — mesmo padrão de `dashboard/`)

- `SettingsScreen.tsx`: lista de cards, um por fonte.
- Cada card: nome da fonte, toggle liga/desliga, indicador de conexão
  (🟢/🔴/⚪ + rótulo curto), campos de credencial (só visíveis/expandidos
  quando a fonte está com o formulário aberto — não precisa mostrar campo
  de senha permanentemente na tela principal).
- Fluxo do toggle, conforme `docs/roadmap.md` Fase 0:
  1. Usuário liga o toggle → se a fonte tem campos obrigatórios sem valor
     salvo, abre o formulário em vez de tentar conectar direto.
  2. Usuário preenche e confirma → `PUT` salva → `POST .../test` roda
     automaticamente → indicador atualiza para 🟢/🔴 com a mensagem.
  3. Reabrir a tela → `GET /settings` já traz o último `last_check`
     conhecido (sem re-testar do zero) — botão "Testar de novo" força novo
     teste sob demanda.
- Nova aba na navegação principal (`App.tsx`), ao lado de Dashboard/
  Oportunidades — rótulo "Configurações".
- Nenhum nome de campo de API na tela — só os `label`/`help_text` que
  vieram do backend.
- Erro de rede/servidor também em linguagem de negócio (mesmo texto de
  fallback usado em `api.ts`).

## Estrutura afetada

```
backend/settings.py          → novo: SourceDescriptor, registro de fontes
backend/routes_settings.py   → novo: GET/PUT/POST das rotas acima
backend/main.py              → monta o novo router
core/config.py               → nova função set_env_values()
frontend/src/settings/       → novo: SettingsScreen.tsx, SourceCard.tsx, api de settings
frontend/src/App.tsx         → nova aba "Configurações"
frontend/src/api.ts          → funções fetch para as 3 rotas novas
tests/test_config.py         → testes de set_env_values
tests/test_settings.py       → novo: testes das rotas (mock de provider, sem rede real)
```

## Estratégia de teste

Backend: mesmo padrão dos demais (`assert`+`asyncio.run` ou `TestClient`
como em `test_routes_exports.py`), sem framework novo. Casos:
- `set_env_values` atualiza chave existente, preserva o resto do arquivo.
- `set_env_values` nunca apaga valor existente com string vazia.
- `GET /settings` nunca devolve valor de campo `secret=True` em claro.
- `PUT` seguido de `POST .../test` com Salesforce mockado (reusa o padrão
  de `httpx.MockTransport` de `test_salesforce_provider.py`).
- Fonte `implemented=False` no `POST .../test` devolve mensagem amigável,
  nunca 500.

Frontend: `vitest`, mesmo padrão de `logic.test.ts`/`palette.test.ts` —
foco em lógica pura do fluxo (ex.: decidir se abre formulário ou testa
direto), não teste de renderização pesado.

## Fronteiras

- **Sempre:** rodar suíte completa antes de fechar a fase; nunca deixar
  secret em claro em resposta de API/log.
- **Perguntar antes:** qualquer mudança em `providers/base.py` (contrato
  `DataProvider`) — esta fase não deveria precisar tocar nele.
- **Nunca:** hardcodar um `if source_id == "salesforce"` na lógica de UI —
  tudo vem do `SourceDescriptor`. Nunca remover `SALESFORCE_ENABLED`/afins
  do `.env-model` (a tela lê/escreve as chaves que já existem).

## Critérios de sucesso

- [ ] `set_env_values` testado e não quebra `sync_env`/`load_env` existentes.
- [ ] Rotas novas seguem a mesma taxonomia de erro do projeto.
- [ ] Tela nova mostra Manual (sempre conectado) e Salesforce (testável de
      verdade) e Website/Google Maps como "em breve", sem código
      condicional hardcoded por fonte na camada de UI.
- [ ] Nenhum segredo aparece em claro em nenhuma resposta de API.
- [ ] Suíte completa (backend + frontend) passa sem regressão.
- [ ] `CHANGELOG.md` e `README.md` (se comando de teste novo) atualizados.
