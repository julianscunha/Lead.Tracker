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
