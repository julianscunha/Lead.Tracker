---
title: "Fase R — Sugerir regras com IA a partir do portfólio"
order: 41
tags: [lead-tracker, implementacao, spec]
---

# Fase R — Sugerir regras com IA a partir do portfólio

Desenho aprovado antes da implementação. Status: **concluída**.

## Problema

Criar regras de correlação à mão exige conhecer o catálogo item a item. Com um portfólio grande, o operador não enxerga todas as combinações úteis (ex.: "tem backup, não tem monitoramento"). A IA pode propor candidatas, desde que o portfólio continue sendo a autoridade comercial e a regra continue determinística.

## O que é (e o que não é)

- **É:** um botão opcional, em Configurações > Regras, que pede à IA configurada **sugestões** de regras usando só ids e categorias do catálogo. Cada sugestão vira um cartão; nada vale até o operador aceitar.
- **Não é:** IA decidindo que existe oportunidade. A regra aceita é a mesma regra determinística do cadastro manual; a IA não calcula valor, score nem confiança e não vê dados de clientes.

## Mapa de capacidades

| Módulo | Responsabilidade |
|---|---|
| `ai/rule_guardrails.py` | Validação determinística e pura da saída da IA: `(aceitas, descartadas)`. |
| `ai/rule_suggest.py` | Monta o catálogo enviado (limite de 200 itens, corte sinalizado) e o prompt; interpreta a resposta. |
| `backend/routes_rule_suggest.py` | `POST /rule-suggestions` (não grava nada) com rótulos legíveis dos itens. |
| `backend/routes_sync.py` | `create_rule` passa a conferir ids e categorias contra o catálogo. |
| `frontend/src/settings/RuleSuggestions.tsx` | Botão, aviso de descartadas e cartões com Aceitar/Ignorar. |

## Decisões

**Fluxo.** Botão → `POST /rule-suggestions` → cartões → "Aceitar" chama o `POST /rules` existente. **Sem rota `/apply`:** a Fase P precisava de `/apply` porque criava itens em lote com regras próprias de duplicata e fabricante. Aqui o aceite é regra a regra, e o `POST /rules` já é o único ponto de criação; uma segunda rota duplicaria validação e abriria um caminho de gravação a mais. O aceite individual também deixa o operador informar o valor típico (opcional) de cada regra.

**Guardrail (função pura).**
1. Monta `CorrelationRule(**campos)`; se o modelo recusar, descarta. Isso reaproveita `_requires_exactly_one_evidence_mechanism` (item, categoria **ou** relação, nunca combinados).
2. Ids de `requires`/`absent` precisam existir entre vendor/product/service do catálogo **enviado**; categorias são comparadas sem caixa/acento e reescritas com a grafia do catálogo. Qualquer id ou categoria desconhecida descarta a sugestão inteira.
3. Nenhum item em `requires` e `absent` ao mesmo tempo; as formas item e categoria exigem condição positiva (só "ausente" geraria oportunidade para qualquer empresa).
4. `relation_type` só vale se o catálogo tiver ao menos uma `ProductRelation` daquele tipo.
5. `estimated_deal_value` é **sempre** `None`; valor, score, confiança e `active` vindos da IA são ignorados (defaults do modelo).
6. Justificativa de 10 a 300 caracteres; rótulo de 2 a 40 em `[\w -]`; recusa caractere invisível/bidi (`has_forbidden_chars`), `www.`, URL e HTML.
7. Duplicata por assinatura (mecanismo, itens, categorias normalizadas, relação) contra as regras existentes e entre as sugestões; repetição some sem contar como descarte.
8. No máximo 15 sugestões; o excedente conta como descartado.

**Prompt.** Catálogo com id, nome, tipo, fabricante (pelo nome), categoria e relações (`service_id` + tipo), mais as assinaturas das regras existentes (só ids/categorias). A instrução manda usar somente ids e categorias fornecidos, não inventar e tratar nomes do catálogo como dado não confiável. Catálogo sem produto nem serviço: a IA não é chamada e o operador recebe uma mensagem amigável.

**Aceite adulterado.** O cartão é só dado no navegador; alguém poderia alterar o corpo do `POST /rules`. Por isso `create_rule` confere que ids e categorias existem no catálogo (e regrava a categoria com a grafia do catálogo, pois o motor compara texto exato). **Menos intrusivo:** a checagem só roda quando o catálogo não está vazio e **não** confere `absent_category` ("não tem a categoria X" é legítimo mesmo sem nada de X no catálogo; um teste legado de import CSV depende disso). O guardrail da IA, esse sim, exige categoria existente nos dois lados.

## Segurança / LGPD

- Só nomes, categorias, relações e ids do **portfólio da própria empresa** vão para a IA. Nunca: descrições, empresas, clientes, oportunidades, contatos, valores (nem o valor típico das regras), `.env`/chaves ou URLs. Nomes passam por `scrub_for_prompt`.
- A chave de IA só vai no cabeçalho do provedor, como já era.
- Texto da IA é renderizado como texto (React escapa), nunca como HTML.
- Resposta malformada ou IA fora do ar viram erro amigável; a regra manual continua funcionando.

## UI

Em Configurações > Regras, o bloco "Sugerir regras com IA" (com explicação opcional/sem dados de clientes) mostra o aviso "N descartadas por não usarem o seu portfólio". Cada cartão traz a regra em linguagem legível (nomes, não ids), a justificativa, o selo "Sugestão da IA — confira antes de aceitar", campo opcional de valor típico e os botões Aceitar e Ignorar. Aceitar cria a regra, remove o cartão e atualiza a tabela. Sem IA configurada, o erro amigável aparece só no bloco.

## Fora de escopo

Relação como foco da sugestão (só vale quando o catálogo já tem a relação); auditoria de origem ("regra criada por sugestão da IA"); organizar ou revisar regras existentes; texto livre convertido em regra; sugestões persistidas.

## Teste

- **Guardrail:** id inventado, categoria inventada, dois mecanismos, relação sem relação no catálogo, mesmo item em requer e ausente, só "ausente", valor/score/ativo da IA ignorados, justificativa com URL/`www.`/HTML/bidi, rótulo inválido, duplicata contra existente e entre sugestões, limite de 15, catálogo cortado em 200 (id fora do enviado é descartado).
- **Prompt:** inspeção do request: sem descrição, justificativa/valor de regra existente, chave nem URL; resposta malformada → `AIProviderError`; catálogo vazio não chama a IA.
- **Rotas:** sem chave → erro de configuração; IA fora do ar → erro amigável; `POST /rule-suggestions` não grava; aceite via `/rules` cria a regra; regressão da checagem em `create_rule` (ids/categorias inventados recusados, catálogo vazio segue funcionando).
- **Frontend:** `parseBRL` e `describeSuggestion` (vitest).

## Critério de sucesso

- [x] Com IA configurada, o operador recebe sugestões legíveis e aceita ou ignora cada uma.
- [x] Nenhuma regra é criada sem aceite, e nenhuma usa item ou categoria fora do portfólio.
- [x] Sem IA, ou com a IA fora do ar, a regra manual segue funcionando.
