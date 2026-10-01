# Business case por oportunidade (backlog do roadmap, item "Gerador de business case")

Origem: backlog priorizado do `engineering/roadmap.md` (sugestão do Proposal
Strategist). Não depende de dado histórico novo — só compõe o que o motor já
calcula (`core/models.py::Opportunity`).

**Status:** spec e mapa de capacidades aprovados pelo usuário. Próximo: plano e tarefas (sem código ainda).

## Objetivo

Documento de 1 página (PDF) por oportunidade, para o vendedor levar a uma
conversa: situação → gap → custo de não agir → estado futuro. É **rascunho
para revisão do vendedor**, nunca enviado pelo sistema.

Sucesso = o vendedor exporta, em 1 clique, um PDF que só diz o que os dados
sustentam (fato + fonte + data), sem número em R$ nem fato inventado.

## Premissas (corrija agora ou sigo com elas)

1. Uma oportunidade → um documento. Sem edição livre do texto na v1 (editar
   abriria nova superfície para violar as regras).
2. Reaproveita `exports/pdf.py` (FPDF, `_pdf_safe`), o padrão de
   `ai/email_draft.py` (instrução + validação determinística + degradação) e
   `backend/routes_exports.py`.
3. "Custo de não agir" é **banda qualitativa** (baixo/médio/alto) + 1 frase
   de racional + pergunta em aberto. Nunca R$ nem % (já é regra permanente do
   roadmap: custo de inação calculado pelo sistema está fora de escopo).
4. Sem IA configurada, o documento sai igual em fatos, com prosa
   determinística.

## Mapa de capacidades (confirmado pelo usuário)

| Ordem | Módulo | Responsabilidade | Consulta a especialista |
|---|---|---|---|
| 1 | `business-case-assembler` | Função pura: `Opportunity` + `Company` + item do portfólio → estrutura das 4 seções (+ cabeçalho e rodapé). Define seção essencial vs. complementar. Sem IA, sem I/O. | Proposal Strategist (feito) |
| 2 | `severity-band-reuse` | **Reutiliza `compute_severity_band(scope_note, criticality)`** (`core/opportunity_engine.py:427`). Sem mapa novo nem limiares: a banda vem do que o vendedor avaliou; qualquer campo em branco = `nao_avaliado`. Módulo fino: só liga a função existente ao assembler. | Não (reuso) |
| 3 | `business-case-prose-guard` | IA opcional redige só a prosa; guardrail **em código** rejeita qualquer produto, número, data ou % fora dos campos de entrada e cai no modo determinístico. | Security Auditor (agent-skills) |
| 4 | `business-case-pdf` | Renderiza em `exports/`, exatamente 1 página (limite de palavras por seção, truncamento determinístico). | Não (mecânico) |
| 5 | `business-case-route-and-ui` | `POST /exports/business-case` + botão na tela de Oportunidades, com aviso em linguagem de negócio quando faltar dado. | Frontend Developer |

Dependência: 1 → 2 → 3 → 4 → 5 (cada módulo consome o anterior).

## Conteúdo do documento (ordem fixa, ~330–380 palavras)

| Seção | Fonte | Se faltar dado |
|---|---|---|
| Cabeçalho | empresa, produto/serviço do portfólio, data, 4 scores como rótulos separados | — |
| Situação (~70 pal.) | `evidence` (fato + fonte + data), atributos da empresa | **Essencial: bloqueia exportação** ("faltam evidências para esta oportunidade") |
| Gap (~70 pal.) | motivo principal + 2–3 evidências (fato → implicação) | **Essencial.** Sem implicação: mostra só o fato |
| Custo de não agir (~60 pal.) | banda de `compute_severity_band(scope_note, criticality)` + `confidence_score` (só para o tom); a pergunta em aberto (`discovery_prompt`) aparece **só na tela** | Banda `nao_avaliado` mantém a seção com "Não avaliado"; sem pergunta no PDF |
| Estado futuro (~60 pal.) | descrição do item no portfólio | Omite o parágrafo, mostra só o nome (nunca "[preencher]" no PDF) |
| Rodapé (~40 pal.) | fontes, nível de confiança, "rascunho para revisão do vendedor; não enviado" | — |

Os 4 scores nunca se fundem em um. Rótulos para o vendedor: aderência,
potencial financeiro, relevância estratégica, confiança. `financial_potential`
não aparece em R$ em lugar nenhum; no cabeçalho entra só como rótulo qualitativo.

Confiança baixa rebaixa o tom (verbos condicionais: "indica", "sugere").
Evidência antiga mostra a data e aviso de envelhecimento.

## Comandos

```
Testes:   python -m pytest tests/test_business_case.py -q
Suíte:    python -m pytest -q
Frontend: cd frontend && npm run build && npm run test
```

## Estrutura

```
core/business_case.py        → montagem determinística (módulos 1–2)
ai/business_case_prose.py    → prosa opcional + guardrail (módulo 3)
exports/pdf.py               → renderização de 1 página (módulo 4)
backend/routes_exports.py    → rota (módulo 5)
frontend/src/api.ts, OpportunityTable.tsx → botão (módulo 5)
tests/test_business_case.py  → testes
```

## Estilo e testes

Funções puras, tipadas, no padrão de `compute_silence_signal`/`email_draft.py`.
Testes só com empresas fictícias, IA mockada (`httpx.MockTransport`, zero rede),
no molde de `test_email_draft.py`, `test_exports.py`, `test_routes_exports.py`.
Cada bug corrigido ganha teste de regressão.

## Fora de escopo

Proposta comercial/precificação; edição livre do texto; envio por e-mail;
qualquer número em R$ calculado pelo sistema; prova social ("empresas como a
sua"); comparação com concorrente.

## Limites

- **Sempre:** guardrail de saída da IA em código (não só no prompt); degradar
  sem IA; mensagens de erro em linguagem de negócio; nenhum segredo em prompt
  ou PDF; mandar à IA só os campos necessários.
- **Perguntar antes:** mudança de schema; nova dependência; mudar o fluxo de
  status.
- **Nunca:** inventar produto/serviço/fato/número; mudar status; enviar algo
  sozinho; urgência sem dado temporal na evidência; hardcode de fabricante.

## Critérios de sucesso (verificáveis)

1. **Rastreabilidade:** todo número, nome de produto/serviço/fabricante e data
   na saída existe nos campos de entrada. Teste com IA mockada que tenta
   injetar produto e valor: saída rejeitada, documento cai no modo
   determinístico. Zero "R$", "%" ou "mil/milhões" fora de fatos citados.
2. **Degradação:** com IA desligada, indisponível ou em timeout, o PDF sai com
   as 4 seções e os mesmos fatos; nenhuma exceção técnica visível; nenhuma
   chamada de rede além do download.
3. **Fidelidade e 1 página:** com os mesmos scores/evidências fictícios, os 4
   scores aparecem separados e inalterados; oportunidade sem evidência não
   gera documento; PDF com 3 e com 6 evidências tem exatamente 1 página.

## Riscos registrados (do parecer do Proposal Strategist)

- Business case clássico pede valor financeiro; aqui é qualitativo de
  propósito, o que enfraquece a persuasão para sponsor financeiro.
- Limiares score→banda são decisão de produto; banda arbitrária pode ser lida
  como cálculo. Precisam ser configuráveis e documentados.
- O vendedor pode encaminhar o PDF sem revisar. Mitigação: marca "rascunho
  para revisão do vendedor" no PDF.
- "Estado futuro" sem resultado quantificado é mais fraco; mitigação é a
  pergunta em aberto, não métrica genérica.

## Decisões do usuário (resolvem as perguntas em aberto)

1. A pergunta em aberto do "custo de não agir" aparece **somente na tela**.
   O PDF não a traz (a linha neutra "ponto a validar com o cliente"
   sugerida pelo especialista **não** foi adotada).
2. Bandas: **reutilizar** `compute_severity_band`. Consequência: a banda
   deriva de `scope_note` × `criticality` (avaliação do vendedor), não de
   scores; o módulo 2 vira só uma ligação, sem limiares configuráveis.
3. Os 5 módulos estão confirmados.

## Decisões adicionais (parecer do Pipeline Analyst + usuário)

4. **Rótulos e faixas dos scores** (sem número cru, lado a lado, sem total,
   com legenda de 1 linha de que são dimensões independentes):
   `opportunity_score` → "Aderência ao portfólio"; `financial_potential` →
   "Porte estimado da conta"; `strategic_score` → "Relevância estratégica";
   `confidence_score` → "Solidez das evidências". Nunca "chance",
   "probabilidade", "valor" ou "receita".
5. **Faixas:** Baixa/Média/Alta em terços iguais da escala 0–1 (até 0,33 /
   até 0,66 / acima), ajustáveis depois. **Ressalva:** a escala 0–1 é o
   default (`CorrelationRule.*_score = 1.0`), mas não é imposta pelo modelo;
   regra personalizada pode usar outra. Score `None` = "Não avaliado".
   `compute_severity_band` **não** serve para scores (recebe
   `scope_note` × `criticality`).
6. **`financial_potential` e `strategic_score` costumam ser `None`** nas
   oportunidades geradas por regra (`core/opportunity_engine.py:589-590`),
   então tendem a aparecer como "Não avaliado". Aceito na v1.
7. **Data da evidência = data de sincronização**, rotulada: "Dado
   sincronizado em dd/mm/aaaa (a data do fato no CRM pode ser anterior)".
   Mais de 30 dias: "confirme com o cliente antes de usar"; mais de 90:
   destaque "Dado antigo (N dias): reconfirmar". Nunca "hoje/recente/atual".
   Data de geração do PDF no rodapé. Limitação conhecida: capturar a data do
   fato no provider fica para depois.
8. **Rota por `opportunity_id`**: o servidor carrega oportunidade, empresa e
   item do portfólio; rejeita qualquer campo monetário no payload.
   `scope_note`/`criticality` já estão gravados na oportunidade.
9. **Guardrail:** reaproveita só a checagem de números e datas de
   `ai/email_guardrails.py`; lista própria de termos (a do e-mail dá falso
   positivo). **Degradação sem IA é código novo** (o `/email-draft` hoje
   devolve erro sem chave).
