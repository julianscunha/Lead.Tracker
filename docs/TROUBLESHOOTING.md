---
title: "Lead.Tracker — Troubleshooting"
order: 4
tags: [lead-tracker, troubleshooting, erros, configuracao, suporte]
---

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

## "Esse contato está marcado como não contatar" ao gerar rascunho ou registrar contato

O bloqueio funciona como previsto. Veja a seção "Não contatar" no detalhe da
oportunidade: lá aparece quem está bloqueado, o canal e o motivo. Se a situação
mudou, use "Reativar" (o histórico é mantido). Se o contato realmente aconteceu,
confirme "Registrar mesmo assim": o toque fica marcado para auditoria. Se a
mensagem pede para escolher o contato, há contato bloqueado na empresa e a ação
precisa dizer a qual contato se refere.

## Apareceram "Conflitos de dados" depois de sincronizar ou importar

Duas fontes trouxeram valores diferentes para o mesmo campo de uma empresa. O
valor atual foi mantido. Abra Configurações > Conflitos de dados e escolha qual
manter; a escolha fica no histórico de alterações. Conflito de representante ou
segmento costuma vir de planilha que difere do que outra fonte já gravou.

## Aviso "valores da planilha diferem do que já estava na base"

A importação de planilha não sobrescreve o que outra fonte gravou: o valor
atual foi mantido e o conflito foi para a seção "Conflitos de dados". Para a
planilha passar a valer, escolha o valor dela no conflito.

## Atualizei o módulo e as telas dão erro (500)

Colunas e tabelas novas são criadas quando o módulo é instalado, ativado ou
atualizado. Se você copiou os arquivos à mão por cima de uma instalação antiga,
reative o módulo (ou rode `init_db()` uma vez) e reinicie o host.
