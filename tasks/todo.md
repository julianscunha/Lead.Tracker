# Tarefas: business case por oportunidade

Plano: `tasks/plan.md`. Regra por tarefa: especialista antes e depois, busca
por ast-grep/git incremental, Haiku no mecânico e Sonnet no restante, commit
e push por etapa.

## Bloqueio
- [x] Perguntas em aberto respondidas (ver spec, decisões 4–9).

## T1 — `business-case-assembler` (S)
- [x] `assemble_business_case(opp, company, item, today)` pura: cabeçalho, 4 seções, rodapé
  - Acceptance: sem evidência → `ExportError` em linguagem de negócio; 4 scores separados; nenhum R$; sem descrição → só o nome do item; evidência antiga mostra data + aviso; confiança baixa → flag de tom condicional
  - Verify: `python -m pytest tests/test_business_case.py -q`
  - Files: `core/business_case.py`, `tests/test_business_case.py`
  - Depende de: nada (bloqueio resolvido)

## T2 — `severity-band-reuse` (XS)
- [x] Assembler chama `compute_severity_band(scope_note, criticality)`
  - Acceptance: 9 combinações + `None` → "Não avaliado" com seção mantida; `discovery_prompt` nunca entra no PDF (assert)
  - Verify: `python -m pytest tests/test_business_case.py tests/test_opportunity_engine.py -q`
  - Files: `core/business_case.py`, `tests/test_business_case.py`
  - Depende de: T1

### Checkpoint após T1–T2
- [x] Suíte do motor verde (109 testes focados); nenhum limiar novo; revisão do code-reviewer aplicada

## T3a — guardrail da prosa (M) — parecer do Security Auditor
- [x] `ai/business_case_guardrails.py`: funções puras `validate_section(text, allowed_text, ...)`, termos proibidos próprios (sem "sempre/nunca/mais/menos"), números/datas/R$/%/"mil/milhões" só se estiverem na entrada, entidades só as da entrada, tamanho como rejeição (nunca truncar saída da IA), cobertura dos fatos, scrub de PII/segredo para envio
  - Acceptance: cada regra tem teste de rejeição e teste de não-falso-positivo ("30 dias", "VDC365", "M365", frases com "sempre/nunca/mais/menos"); urgência proibida SEMPRE (decisão 7); nenhum `except Exception`
  - Verify: `python -m pytest tests/test_business_case_guardrails.py -q`
  - Files: `ai/business_case_guardrails.py`, `tests/test_business_case_guardrails.py`
  - Depende de: T1, T2

## T3b — prosa por IA com degradação (M)
- [ ] `ai/business_case_prose.py`: `apply_ai_prose(case, provider|None)` — whitelist de campos enviados, texto de fonte delimitado como dado, 1 chamada com `asyncio.wait_for`, validação por seção (seção ruim → determinística; ≥2 ruins, JSON não-dict ou injeção detectada → tudo determinístico), `fonte_prosa`, captura só `DomainError`/`httpx.HTTPError`/timeout
  - Acceptance: os 8 testes do parecer (injeção via evidência, produto/número inventado, termos proibidos, boa resposta, parcial, degradação, vazamento no corpo da requisição, erro de programação não engolido); `custo` e `rodape` nunca reescritos
  - Verify: `python -m pytest tests/test_business_case_prose.py tests/test_business_case.py -q`
  - Files: `ai/business_case_prose.py`, `tests/test_business_case_prose.py`, `ai/base.py` (+ teste de regressão: `parse_structured_response` quebra com JSON que não é dict)
  - Depende de: T3a

### Checkpoint após T3a+T3b
- [ ] Teste de injeção de produto e valor passa (critério 1 da spec); degradação sem IA passa (critério 2)

## T4 — `business-case-pdf` (S)
- [ ] `business_case_pdf(doc, generated_at)` em `exports/pdf.py`
  - Acceptance: exatamente 1 página com 3 e com 6 evidências (`pdf.page == 1`); truncamento por palavras; marca "rascunho para revisão do vendedor; não enviado"
  - Verify: `python -m pytest tests/test_exports.py tests/test_business_case.py -q`
  - Files: `exports/pdf.py`, `tests/test_exports.py`
  - Depende de: T1–T3

### Checkpoint após T4
- [ ] Teste de 1 página passa (critério 3 da spec)

## T5 — rota + botão (M)
- [ ] `POST /exports/business-case` + `exportBusinessCase` em `api.ts` + botão em `OpportunityTable.tsx`
  - Acceptance: devolve `%PDF`; sem evidência → 4xx com mensagem de negócio; sem IA ainda gera; não muda status nem envia nada; pergunta em aberto só na tela
  - Verify: `python -m pytest tests/test_routes_exports.py -q` e `cd frontend && npm run build && npm run test`
  - Files: `backend/routes_exports.py`, `tests/test_routes_exports.py`, `frontend/src/api.ts`, `frontend/src/OpportunityTable.tsx`, `frontend/src/logic.test.ts`
  - Depende de: T4

### Checkpoint final
- [ ] `python -m pytest -q` e `npm run build && npm run test` verdes
- [ ] Smoke manual com empresa fictícia; PDF sai com a IA desligada (critério 2)
- [ ] CHANGELOG em `[Unreleased]`; revisão final com especialista
