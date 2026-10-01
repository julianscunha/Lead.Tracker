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

## T3 — `prose-guard` (M)
- [ ] `ai/business_case_prose.py`: request mínimo (sem segredo) + parse + guardrail
  - Acceptance: rejeita número/data/%/"R$"/"mil/milhões"/produto fora da entrada e urgência sem data; IA mockada (`httpx.MockTransport`) que injeta produto e valor → rejeitada, cai na prosa determinística; sem IA/timeout/exceção → mesma prosa determinística, sem erro técnico
  - Verify: `python -m pytest tests/test_business_case.py tests/test_email_guardrails.py -q`
  - Files: `ai/business_case_prose.py`, `tests/test_business_case.py` (toca `ai/email_guardrails.py` só se extrair helpers)
  - Depende de: T1, T2. Security Auditor antes de fechar.

### Checkpoint após T3
- [ ] Teste de injeção de produto e valor passa (critério 1 da spec)

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
