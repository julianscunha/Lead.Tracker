# Troubleshooting

Guia rápido pra quem está desenvolvendo/testando o Lead.Tracker localmente.
Erros de usuário final (não-técnico) já viram mensagem amigável — ver
`core/errors.py`. Este documento é sobre os erros que aparecem *durante o
desenvolvimento*.

## "IA não configurada" / rascunho de e-mail retorna 503

`AI_API_KEY` está vazia no `.env`. Configure a chave do provider escolhido
em `AI_PROVIDER` (`openrouter`, `openai`, `gemini` ou `claude`). O módulo
funciona normalmente sem isso —
só a geração de rascunho de e-mail fica indisponível (IA é opcional, ver
`core/opportunity_engine.py`: o motor de oportunidades não depende de IA).

## `unable to open database file`

O caminho do banco (`data/lead_tracker.db`) é relativo à raiz do módulo
(`_MODULE_ROOT` em `backend/main.py`). Se você importar `core.db`/
`core.repository` fora do contexto do módulo (ex.: um script solto), passe
um `db_path` absoluto pra `create_engine()` em vez de confiar no path default.

## Tabelas não existem depois de rodar `init_db()`

Isso já foi um bug real, corrigido: `init_db()` precisa que
`core.db_models` esteja importado antes de `Base.metadata.create_all()`
rodar, senão as classes ORM nunca se registram e o `create_all` roda vazio
— sem erro nenhum, só sem criar tabela. `core/db.py` já importa
`core.db_models` internamente dentro de `init_db()`; se você reescrever essa
função, mantenha esse import (ver comentário no código e
`tests/test_db_table_registration.py`, que reproduz a regressão em
subprocesso isolado).

## Checkpoint contra o Core não mostra o módulo como saudável

`/api/v1/health` **não chama** `ModuleContract.health_check()` — é um stub
que só olha o status do registry (`INSTALLED` = saudável). Pra testar o
lifecycle de verdade (`install`/`enable`/`disable`/`health_check`), use:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/marketplace/deactivate/lead_tracker
curl -X POST http://127.0.0.1:8000/api/v1/marketplace/activate/lead_tracker
curl http://127.0.0.1:8000/api/v1/modules/lead_tracker/diagnostics
```

O último endpoint mostra o `RuntimeState` real (`READY`/`FAILED`/`DEGRADED`)
e o `last_error`, se houver.

## Processo do Core (`uvicorn --reload`) não morre com `taskkill`

O reloader do uvicorn frequentemente deixa um processo worker vivo mesmo
depois de matar o PID do processo "principal". Liste os processos python
reais antes de encerrar:

```powershell
tasklist /FI "IMAGENAME eq python.exe"
# mate cada PID listado, não só o primeiro
```

## Exportação PDF quebra com caractere estranho no nome da empresa

Também já foi um bug real, corrigido: a fonte core do fpdf2
(`Helvetica`) só cobre latin-1 — travessão (`—`), aspas curvas e emoji
derrubavam a exportação. `exports/pdf.py` tem `_pdf_safe()` pra isso; use-o
em qualquer texto dinâmico novo que for pra dentro de um PDF.

## `frontend/index.js` desatualizado / tela não reflete mudança recente

`frontend/index.js` é build output (gitignored) — rode `npm run build`
dentro de `frontend/` depois de qualquer mudança em `frontend/src/` antes de
copiar o módulo pro Core.
