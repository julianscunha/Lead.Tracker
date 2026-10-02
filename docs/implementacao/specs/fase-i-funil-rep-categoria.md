---
title: "Fase I — Funil por rep×categoria e reorganização do dashboard"
order: 29
tags: [lead-tracker, implementacao, spec]
---

# Fase I — Funil por rep×categoria e reorganização do dashboard

Origem: item do backlog do roadmap ("Funil de conversão por rep×categoria
pra coaching", Sales Coach). Depende só do que já existe: `OpportunitySnapshot`
(estágio + `rep_id`), `Opportunity.product_id/service_id` e
`Product.category`/`Service.category`. Não depende de histórico de transição.

## Decisões do usuário

1. **Entregar agora como "visão atual"** (corte transversal), nunca como
   conversão histórica. `OpportunityStatusChange` só existe pra transições
   manuais, então conversão de coorte não é calculável hoje (mesma limitação
   já registrada em `core/dashboard_metrics.py::funnel_reach`).
2. **Amostra mínima N = 5, configurável.** Abaixo disso o par (rep, categoria)
   é "dado insuficiente" (`None`), nunca 0%.
3. **Nova seção no dashboard + reorganização do dashboard inteiro** (visual,
   UX, UI), com consulta a especialistas.

## Consulta a especialistas (resumo do que entrou no spec)

- **Sales Coach**: o dado serve pra levantar pergunta na 1:1, nunca veredito.
  Comparar rep × **mediana do time na mesma categoria**, só com ≥ 3 reps
  elegíveis (senão, sem referência). Nunca agrupar categorias pra atingir o N.
  Sem ranking de reps, sem destaque em vermelho, ordenação alfabética.
  Mostrar o n real ("3 de 5 necessárias"). Clique na célula leva à lista de
  deals (evidência acessível).
- **Data Visualization Engineer**: heatmap rep×categoria com seletor de
  estágio ("chegou a ≥ X", padrão `contacted`); cor de matiz único com domínio
  fixo (não normalizar pelo máximo); "dado insuficiente" = fundo neutro
  hachurado + texto (nunca a rampa, nunca "0%"); 0% real = cor mais clara com
  borda; número em toda célula; abaixo de ~480px vira lista agrupada por rep.
- **Frontend Developer**: dashboard atual tem 12 tiles sem hierarquia, ações
  (zumbi, triagem atrasada) no fim, seletor de período que parece global mas
  é só da tabela de cobertura, nota final expondo caminho de spec interno,
  sem landmarks. Reorganizar em 3 blocos por pergunta (Hoje / Pipeline /
  Representantes), reaproveitar `StatTile`, `.lt-chart-card`, `.lt-empty`,
  `.lt-table`, `.lt-badge--health-dados_insuficientes`; criar só `DashSection`,
  `StatTile tone="attention"` e `RepCategoryMatrix`.

## Mapa de módulos

| Ordem | Módulo | Responsabilidade |
|---|---|---|
| 1 | `rep-category-reach` | Função pura em `core/dashboard_metrics.py`: alcance acumulado por (rep, categoria) + mediana do time por categoria. |
| 2 | `rep-category-min-sample-config` | N mínimo configurável (default 5) pela tela de configurações, nunca `.env` manual. |
| 3 | `rep-category-reach-route` | Rota de leitura do dashboard que expõe o módulo 1. |
| 4 | `dashboard-reorg` | Reorganização em 3 blocos + landmarks + loading/erro (passos 1–4 e 6 do fatiamento). |
| 5 | `rep-category-matrix-ui` | `RepCategoryMatrix` na seção Representantes (passo 5). |

## Módulo 1 — `rep-category-reach`

Função pura, mesmo padrão de `funnel_reach`/`compute_rep_coverage`.

- Entrada: snapshots da data mais recente, mapa `opportunity_id → categoria`
  (derivado de `product_id`/`service_id`; sem fonte de categoria vira o balde
  neutro **"Sem categoria"** — nunca inventar categoria), `min_sample`.
- Saída por par (rep, categoria): `n` (oportunidades vivas, `dismissed` fora),
  `reach_count` por estágio (acumulado: chegou ao estágio X **ou além**, mesma
  ordem de `FUNNEL_REACH_ORDER`), `reach_ratio` por estágio sobre `n`,
  `insufficient: bool` (`n < min_sample`). Quando `insufficient`, as razões
  são `None` (as contagens brutas continuam disponíveis pro tooltip).
- Referência do time por categoria: **mediana** da razão entre os reps
  elegíveis (`n >= min_sample`); `None` se houver menos de 3 elegíveis.
- Oportunidade sem `rep_id`: fica fora da matriz e é contada à parte
  (`unassigned_count`), nunca atribuída a um rep fictício.
- Nunca produz ranking, nota agregada nem ordenação por desempenho; a ordem
  de saída é alfabética (rep, categoria).
- Nunca persistido (derivado na leitura, como `compute_qbr_suggested_days`).

## Módulo 2 — `rep-category-min-sample-config`

Chave de configuração com default 5, validada como inteiro ≥ 1, editável na
tela de configurações. Segue o mecanismo de configuração que o projeto já usa
(`.env` + `.env-model`, diff por chave ausente no startup). A localização
exata da chave é decidida na implementação lendo o padrão existente — **não**
criar um mecanismo de configuração novo.

## Módulo 3 — `rep-category-reach-route`

`GET` de leitura junto às rotas de dashboard existentes (nome e formato
seguem as rotas vizinhas). Devolve a saída do módulo 1 + `min_sample` em uso +
`unassigned_count`. Erros convertidos em erro de domínio amigável.

## Módulo 4 — `dashboard-reorg`

Fatiamento (cada passo: build + testes verdes + commit):

1. Extrair `formatters` e `DashSection`; trocar só os wrappers, sem mudar a
   ordem (testes de render).
2. Reordenar em 3 blocos (`<section aria-labelledby>` com h3 de pergunta) +
   landmarks/hierarquia de headings; trocar a nota com caminho de spec por
   texto de produto (**sem linguagem de fase/módulo** na UI).
   - **Hoje (o que fazer?)**: triagem atrasada, oportunidades zumbi,
     oportunidades identificadas.
   - **Pipeline (como está?)**: KPIs de valor, funil + alcance do funil,
     valor por fabricante/serviço/segmento/fonte, cliente × prospect.
   - **Representantes (como está cada rep?)**: seletor de período no
     cabeçalho do bloco, cobertura de meta, valor por rep, matriz do módulo 5.
   - Colapsado em `<details>`: donut de fabricante (redundante), notas de
     limitação em linguagem de produto.
3. Seletor de período no cabeçalho do bloco Representantes + loading
   (`role="status"`) e erro com "tentar de novo".
4. `StatTile tone="attention"` nos acionáveis + colapsáveis.
6. Ajustes visuais: título de card 12→14px, label do tile 10→12px, espaçamento
   16/24, checagem de contraste nos dois temas.

Riscos conhecidos: testes que dependem de texto/ordem dos tiles; `InfoHint`
cortado por `overflow` dentro de `<details>`; matriz larga em mobile.

## Módulo 5 — `rep-category-matrix-ui`

- `<table>` semântica: `<caption>`, `<th scope="col|row">`; wrapper
  `role="region"` com `tabindex=0` e rolagem horizontal; coluna de rep fixa.
  Resumo textual acima ("N reps, M categorias, K pares sem dado suficiente").
- Seletor de estágio (padrão `contacted`); filtro por rep e categoria;
  ordenação alfabética; sem ranking.
- Célula: percentual com o número visível; tooltip e `aria-label` com
  contagem ("7 de 12 chegaram a contacted") + razão estágio/anterior.
- Insuficiente: hachura neutra + "3 de 5 necessárias"; nunca "0%".
- Referência: mediana do time na categoria só quando existir (≥ 3 reps).
- Legenda com 3 itens: rampa, "0% real", "dado insuficiente".
- Textos (Sales Coach): título "Onde as oportunidades estão hoje, por rep e
  categoria"; aviso "Retrato do momento, não taxa de conversão: mostra quantas
  oportunidades já chegaram a cada estágio, sem histórico de transição. Use
  para decidir o que perguntar ao rep, não para avaliá-lo."
- Clique na célula leva à lista de oportunidades daquele par.
- Abaixo de ~480px: lista agrupada por rep, mesma regra de hachura.

## Não objetivos

- Conversão histórica, forecast calibrado (item separado do backlog).
- Ranking, nota única ou exportação "por rep" sem o aviso.
- Qualquer decisão automática ou ação disparada pelo sinal.
- Categorias hardcoded: vêm sempre do portfólio configurado.

## Perguntas em aberto (resolvidas na implementação, sem bloquear)

- Onde exatamente mora a chave do N mínimo (módulo 2): seguir o padrão atual.
- Se o clique na célula reaproveita um filtro existente da tela de
  Oportunidades ou precisa de parâmetro novo na rota de listagem.

## Teste

- Unitários do módulo 1: acúmulo por estágio; `dismissed` fora; `n` na
  fronteira (4 vs 5, e N configurado diferente); insuficiente → razões `None`;
  mediana com 2 vs 3 elegíveis; "Sem categoria"; `unassigned_count`; ordem
  alfabética; empresas fictícias apenas.
- Rota: contrato, `min_sample` refletido, erro amigável.
- Frontend (vitest): célula insuficiente nunca renderiza "0%", caption e
  `scope`, ordenação, seletor de estágio, loading/erro do período.

## Decisões da implementação

- Categoria da oportunidade: a do produto; sem categoria no produto, a do
  serviço; sem nenhuma, balde "Sem categoria" (confirmado pelo usuário).
- Oportunidade sem rep: fora da matriz, só em `unassigned_count` (confirmado).
- A rota devolve também `opportunity_ids` por célula, pra o clique listar os
  deals por trás do número (pedido do Sales Coach).
- `formatPercent` nunca arredonda um valor real pra "0%"/"100%" ("<1%"/">99%"),
  achado da revisão de React.
- Acessibilidade (achados da auditoria): nome acessível da célula começa pelo
  texto visível; contagens por estágio vão no `aria-label`/descrição, não só no
  `title`; amostra pequena marcada com `*` (não só borda); foco vai pro título
  do painel de deals e volta pra célula ao fechar.
- **Desvios do plano, deliberados:** (1) em tela estreita a matriz rola na
  própria região com a coluna do rep fixa, em vez da lista agrupada por rep
  abaixo de ~480px (menos código, mesma informação); (2) `StatTile` mantém valor
  antes do rótulo no DOM (sugestão de `dl` do auditor não aplicada); (3) os
  passos 1–4 e 6 da reorganização foram entregues num commit só, e o 5 (matriz)
  em outro, com revisão de especialista em cada um.
- Verificado ao vivo numa página de pré-visualização com os componentes reais e
  dados fictícios (tema claro, escuro e 400px). A instalação local do Core não
  foi reiniciada, então as rotas novas ainda não foram exercitadas por ela.

## Critério de sucesso

- [x] Nenhum percentual de conversão histórica aparece em lugar nenhum.
- [x] Par com n < N nunca mostra número de razão nem "0%".
- [x] Nenhuma ordenação nem destaque por desempenho de rep.
- [x] Dashboard sem linguagem de fase/módulo e com landmarks corretos.
- [x] Build e todos os testes (backend + frontend) verdes a cada passo.
- [x] Revisão de especialista após cada fatia, sem achado Importante/Crítico
      pendente.
