# Plano: business case por oportunidade

Spec aprovada: `engineering/specs/business-case-por-oportunidade.md`.
Tarefas: `tasks/todo.md`. Código real fica na raiz (`core/`, `ai/`,
`exports/`, `backend/`); `.techforge-dev/` é espelho de teste, não mexer.

## Visão geral

PDF de 1 página por oportunidade (situação → gap → custo de não agir →
estado futuro), montado de forma determinística; IA opcional só redige prosa,
sob guardrail em código.

## Decisões de arquitetura

- **Rota por `opportunity_id`** (recomendação C6): `POST /exports/business-case`
  recebe só `{opportunity_id}` e carrega `Opportunity`, `Company` e item do
  portfólio no servidor (`core/repository.py`). Evita o payload fino do front
  (`OpportunityRowSchema` não traz `evidence`, `scope_note`, `criticality`…) e
  impede o cliente de forjar dados.
- **Banda de severidade:** `compute_severity_band(scope_note, criticality)`
  (`core/opportunity_engine.py:427`), sem limiar novo.
- **Guardrail da IA:** reaproveita só `_numbers_in`/`_DATE_RE` de
  `ai/email_guardrails.py`; lista própria de termos (a do e-mail reprova
  "sempre/nunca/mais/menos" e daria falso positivo, C4).
- **Degradação é código novo** (C1): o `/email-draft` hoje devolve erro sem
  `AI_API_KEY`. Aqui, falha de IA/guardrail → prosa determinística.

## Contradições spec × código (a resolver)

| # | Achado | Resolução proposta |
|---|---|---|
| C1 | Spec diz "sem IA sai igual"; `/email-draft` faz o oposto | degradação nova em T3 |
| C2 | `Opportunity.evidence` é `list[str]` crua; fato+fonte+data só em `evidence_summary` (`opportunity_engine.py:538-548`); a "data" é `synced_at` | **pergunta 2** |
| C3 | "Aderência" não tem campo próprio | **pergunta 1** (`opportunity_score`?) |
| C4 | guardrail do e-mail dá falso positivo | lista própria em T3 |
| C5 | spec cita um só `test_business_case.py`; teste de rota fica em `test_routes_exports.py` | T5 usa os dois |
| C6 | spec diz "payload do front" | **pergunta 3** (rota por id) |

## Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Limite de 1 página no FPDF (evidência/nome longos) | Alto | truncar por palavras, `auto_page_break=False`, teste na borda (6 evidências, texto máximo) |
| Falso positivo do guardrail (números "1.200" vs "1200") | Médio | normalizar com `_normalize_number`; teste dedicado |
| `evidence_summary`/`synced_at` fora do contrato do front | Médio | rota por id (C6) |
| Descrição de portfólio longa ou nula | Baixo | truncar; omitir parágrafo |
| PDF encaminhado sem revisão | Médio | marca "rascunho" obrigatória no rodapé |

## Perguntas em aberto (bloqueiam T1)

1. "Aderência" = `opportunity_score`?
2. Data da evidência = `synced_at` (via `evidence_summary`) é aceitável?
3. Confirma a rota por `opportunity_id` em vez de payload do front?
