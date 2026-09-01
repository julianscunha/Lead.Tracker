# Feedback — SDK e convenções do Tech.Forge

Registro vivo, alimentado conforme o desenvolvimento do Lead.Tracker (módulo)
esbarra em algo — bom ou ruim — no SDK, no contrato de módulo, ou nas
convenções do Tech.Forge Core. Objetivo: virar insumo real para melhorias
no Core ou nos exemplos/documentação de referência, com casos concretos em
vez de opinião abstrata.

Cada entrada: **Fase em que surgiu**, **o que aconteceu**, **por que importa**,
**sugestão** (quando houver).

## Pontos fortes (manter/reforçar)

- **`ModuleContract` (Fase 04)**: contrato de lifecycle (`install/enable/disable/upgrade/health_check/uninstall`) é enxuto e autoexplicativo — implementei sem nenhuma dúvida sobre o que cada método deveria fazer.
- **`create_sdk(module_id)` (Fase 04)**: escopo automático de logger/settings/storage por módulo evita colisão de estado global sem esforço nenhum do autor do módulo.
- **Validador de manifest (Fase 04)**: mensagens de erro/aviso são certeiras e acionáveis — os avisos de `assets/`/`docs/`/`tests/` ausentes me disseram exatamente o que faltava, sem precisar ler código-fonte do validador.
- **Endpoint de assets restritivo por padrão (Fase 04/10)**: whitelist de extensão + guarda de path traversal já vêm prontos — não precisei pensar em segurança nesse ponto.
- **Módulo de referência `hello_world` (Fase 04)**: molde genuinamente útil pra copiar/adaptar backend e frontend na primeira tentativa.
- **Tokens de tema via CSS custom properties (Fase 10)** (`--text`, `--bg`, `--accent`, `--success`, etc.): convenção leve — dark/light automático sem nenhuma lógica de tema no módulo.
- **Proxy de `/api` já configurado no Vite dev do Core (Fase 12)**: o frontend do módulo pôde usar `fetch('/api/v1/modules/lead_tracker/...')` relativo, sem CORS nem config extra — funcionou igual em dev (`:5173` com proxy) e via Core servindo tudo direto. Não precisei descobrir isso lendo código-fonte, só testei e funcionou — mas só percebi que existia por acaso; um comentário no `manifest.example.yaml` ou no guia de módulos citando "use fetch relativo, o Core já resolve" pouparia essa dúvida em quem for escrever o primeiro fetch de um módulo novo.

## Atritos / lacunas encontradas

### Fase 15 — `techforge validate-module` falso-positivo em módulo bundlado (Vite/Rollup)
`ModuleCLIValidator._check` faz busca textual ingênua por `"export default"`
literal no `entry_frontend` (`module_validator.py`, seção 11). Um módulo
React empacotado via Vite/Rollup em modo `lib` com mais de um export (nosso
caso: `default` + `moduleConfig`) sai como `export { lD as default,
iD as moduleConfig }` — semanticamente idêntico, mas sem a substring
contígua `"export default"`. `hello_world` passa porque é JS puro, sem
bundler, então a string aparece literal no source. Confirmei que o módulo
funciona de verdade (import via Node, `render()` executando no navegador
via demo real, Core servindo o asset) — é falso-positivo do validador, não
defeito real. Usei `--skip-validation` pra empacotar, depois de checar
manualmente os outros 26 checks.
**Sugestão**: trocar a busca textual por um parse real (AST via `esprima`/
`ast` de JS, ou até uma checagem mais tolerante tipo regex por
`export\s*\{[^}]*\bas\s+default\b` OU `export\s+default\b`) — qualquer
módulo com mais de um export e um bundler minimamente comum (Vite, esbuild,
webpack) vai cair nesse mesmo falso-positivo.

### Fase 15 — CLI do Tech.Forge quebra no console padrão do Windows (cp1252)
`techforge validate-module`/`package-module` usam `rich` pra formatar saída,
que tenta imprimir glifos Unicode (`❯`, `✓`, `✗`) direto no console. No
Windows com codepage padrão (cp1252, não UTF-8), isso derruba o comando com
`UnicodeEncodeError` antes de mostrar qualquer coisa útil. Contorno:
`PYTHONIOENCODING=utf-8` antes de rodar. Não é um problema de lógica, só de
saída — mas quebra a primeira experiência de quem roda o CLI no Windows sem
saber desse detalhe.
**Sugestão**: o `rich.Console` do CLI detectar/forçar UTF-8 (ou cair pra
ASCII puro) quando `sys.stdout.encoding` não suportar os glifos, em vez de
deixar estourar.

### Fase 14 — `/api/v1/health` não chama `health_check()` do módulo; lifecycle real fica escondido em `/marketplace/activate`
Passei da Fase 04 até a 13 achando (e afirmando ao usuário) que os
checkpoints contra o Core real validavam o ciclo de vida do `ModuleContract`.
Não validavam: `/api/v1/health` é um stub — `is_healthy` vem só do status do
registry (`entry.status == ModuleStatus.INSTALLED`), o próprio arquivo
(`app/api/routes/health.py`) documenta isso como "Phase 5 pendente". E
`ModuleLoader.scan_installed()` nunca chama `install()`/`enable()`/
`health_check()` — só monta o router. O caminho real (`app/module_runtime/
lifecycle.py`, "Fase 9 §10") existe e funciona bem — `POST /api/v1/
marketplace/activate/{id}` e `/deactivate/{id}` chamam `enable()`/`disable()`
de verdade — mas fica em um router (`marketplace.py`) sem nenhuma ligação
óbvia com "isso é o jeito certo de testar o lifecycle de um módulo em dev".
Só achei porque fui atrás de um jeito de exercitar `enable()` de verdade pra
validar a camada de persistência nova.
**Sugestão**: documentar explicitamente (no guia de módulos ou no próprio
`hello_world`) que `POST /marketplace/activate|deactivate/{id}` é o caminho
oficial pra testar lifecycle em dev sem precisar de um `.mod` empacotado —
e, idealmente, fazer `/api/v1/health` reportar de verdade se o
`health_check()` do módulo está acessível, não só o status do registry
(mesmo que como fallback quando o runtime hook não puder ser carregado).

### Fase 14 — `sdk.database` ainda é só um mock in-memory
Fui implementar persistência real pro módulo e descobri, lendo o código-fonte
do SDK (`techforge_sdk/database/__init__.py`), que `DatabaseSDK` está marcado
"Phase 3: in-memory mock" — `fetch_all`/`execute` não tocam banco nenhum,
só um dict em memória que nem sobrevive a um restart. Não tem aviso nenhum
disso na superfície da API (a assinatura dos métodos parece uma sessão real).
Acabei implementando minha própria camada (SQLAlchemy async + aiosqlite,
arquivo em `data/<module>.db`, mesmo padrão do próprio Core) porque não dava
pra confiar no que existe hoje. `sdk.storage` (arquivos) já é real e funciona
bem — só `sdk.database` que ainda não chegou na "Phase 4" mencionada no
próprio docstring.
**Sugestão**: ou completar a Fase 4 do SDK (sessão real scoped por módulo),
ou pelo menos logar um warning bem visível na primeira chamada de
`fetch_all`/`execute` avisando que é mock — hoje só se descobre lendo
código-fonte, e um módulo em produção rodando contra o mock perderia dado
silenciosamente.

### Fase 10 — Nenhum exemplo de módulo com framework (React/TS)
O contrato de frontend (Core só serve `.js`/`.mjs` estático, nunca compila) é
uma escolha de isolamento defensável, mas o único módulo de referência
(`hello_world`) é vanilla JS. Tive que inferir sozinho o padrão "Vite lib
mode → ESM único, React bundlado" sem nenhum exemplo pra validar contra.
**Sugestão**: um segundo módulo de referência (`hello_world_react` ou
similar) mostrando o pipeline de build completo pra quem quer usar
React/Vue/Svelte — economizaria a fase inteira de tentativa-e-erro.

### Fase 10 — Sem runtime compartilhado entre Core e módulos
Cada módulo React empacota seu próprio React (~180KB gzip no nosso caso).
Ok pra isolamento/independência entre módulos, mas escala mal se vários
módulos React forem instalados ao mesmo tempo — cada um duplica a mesma
dependência no navegador do usuário.
**Sugestão**: considerar um import map ou global exposto pelo Core
(`window.React`) como *opção* pros módulos que quiserem economizar
bytes, mantendo o bundle completo como fallback pra quem preferir isolamento.

### Fases 04/10/11 (checkpoints de integração) — Reloader deixa processos órfãos
`uvicorn --reload` frequentemente deixou um processo worker vivo mesmo depois
de matar o PID do reloader — precisei localizar o PID real via `netstat`/
`tasklist` toda vez que queria encerrar limpo pra reiniciar o teste. Não é
bug do SDK, mas atrapalhou o ciclo de teste manual mais do que deveria.
**Sugestão**: nenhuma mudança no Core necessariamente — só vale documentar
esse comportamento do watcher no guia de desenvolvimento de módulos, pra
quem for repetir esse loop de teste local.

### Fase 04 — Schema do manifest só documentado no código
`ParsedManifest` (dataclass em `module_engine/manifest.py`) é a fonte real
de todos os campos/defaults, mas não achei um schema de referência em texto
equivalente — tive que ler o parser fonte pra saber todos os campos opcionais
(`channel`, `documentation_version`, `source_type`, etc.) além do que aparece
em `docs/manifest.example.yaml`.
**Sugestão**: expandir `manifest.example.yaml` pra cobrir todos os campos
(mesmo os opcionais/Fase 5+), com comentário do default de cada um.

## Ideias em aberto (ainda não testadas a fundo)

- Não testei ainda o fluxo de **upgrade** (`upgrade(from_version)`) nem
  **desinstalação real** via `PackageManager` (só testei o contrato isolado
  e o `scan_installed()` — nunca passei pelo ciclo completo de install via
  `.mod` empacotado, que só existe a partir da Fase 15).
- Não testei o comportamento do Core quando **dois módulos** declaram a
  mesma `category` ou entram em conflito de `order` na navegação.
