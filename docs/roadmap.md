---
title: "Lead.Tracker — Roadmap"
order: 6
tags: [lead-tracker, roadmap, backlog]
---

# Roadmap

Só o que **ainda falta**, na ordem sugerida de execução. O que já foi entregue está em [`implementacao/`](implementacao/README.md); as regras que valem para qualquer item estão em [`principios.md`](principios.md). Cada item, quando chegar a vez, ganha a spec em `implementacao/specs/` antes de qualquer código. Esforço: P (dias), M (1–2 semanas), G (mais) — estimativa, não compromisso.

## Visão geral

| # | Item | Valor | Esforço | Depende de | Horizonte |
|---|---|---|---|---|---|
| R1 | URL da empresa | Alto: dedup dos prospects do Maps, destrava R5 | P | — | Agora |
| R2 | Lista de "não contatar" | Alto: segurança do outreach e LGPD | P–M | — | Agora |
| R3 | Registro de auditoria geral | Médio: rastro de edições, base de R7 e R8 | P | — | Agora |
| R4 | Conflito entre fontes | Médio: qualidade do dado com 3+ fontes | M | — | Depois |
| R5 | Provider de enriquecimento | Médio | M | R1 | Depois |
| R6 | Visões salvas na lista | Médio: produtividade do vendedor | P–M | — | Depois |
| R7 | Forecast por conversão histórica | Alto, mas só com dado | G | R3 e volume de histórico | Condicionado |
| R8 | Autoria das edições | Baixo hoje | P | autenticação no produto | Condicionado |
| R9 | Novos conectores (HubSpot, Pipedrive, Website) | Depende do cliente | M cada | — | Sob demanda |
| R10 | Entrada genérica por webhook | Médio | M | R4 (ideal) | Sob demanda |

Dependências: `R1 → R5`; `R3 → R7`; `R3 + autenticação → R8`; `R4 → R10` (recomendado). Os demais são independentes e podem andar em paralelo.

## Agora

### R1. URL da empresa
`Company.website` existe no modelo e no banco, mas só o Salesforce o preenche. Lacunas: a busca do Google Maps não pede `websiteUri` (prospects ficam sem URL e não deduplicam por domínio); o site não vai da descoberta para a `Company` na promoção; a API de oportunidades não o devolve e a tela não o mostra. Módulos: captura no Maps (só preenche se vazio, nunca sobrescreve o Salesforce) → `company_website` na API → link seguro na UI (`http(s)` apenas, `rel="noopener noreferrer"`). Atenção: `websiteUri` na busca por proximidade muda a faixa de preço da Places API.

### R2. Lista de "não contatar"
Não existe hoje. Registro por contato ou empresa e por canal, com motivo (pedido do contato, e-mail inválido, decisão do vendedor), comentário e data, insert-only (padrão do `DoNotContact` do Mautic: `reason`, `channel`, `comments`, `dateAdded`). Quando ativo, sugestões de outreach daquele contato/canal são bloqueadas e a tela explica o porquê. Reforça o limite diário por rep e ajuda na conformidade com a LGPD.

### R3. Registro de auditoria geral
Só a mudança de status tem histórico (`OpportunityStatusChange`). Falta registrar edições de qualificação, discovery, data de renovação e postura do contato: entidade, campo, valor anterior e novo, quando (e quem, após R8). Base de dado para R7. Ideia do `LeadEventLog` do Mautic; sem código copiado (Mautic é GPL).

## Depois

### R4. Conflito entre fontes
Quando Salesforce, Maps e CSV trazem a mesma empresa, `core/normalization.py` fica com o primeiro valor não vazio, sem avisar. Proposta: precedência configurável por campo (fonte preferida e/ou mais recente) e, quando não der para decidir, mostrar o conflito ao usuário em vez de escolher em silêncio ("nunca sobrescrever em silêncio"). Inspirado no `SyncJudge` do Mautic (modos `BestEvidence`/`FuzzyEvidence`/`HardEvidence`); o funcionamento interno não foi lido.

### R5. Provider de enriquecimento
Completar a empresa a partir do domínio (porte, setor, site) por API externa, como os plugins Clearbit e FullContact do Mautic. Provider só coleta e normaliza, como os demais.

### R6. Visões salvas na lista de oportunidades
O vendedor guarda combinações de filtro com nome ("renovação em 60 dias + severidade alta") e reabre com um clique; pode exportar pelo PDF/Excel que já existe. Ideia dos segmentos do Mautic. Só leitura e filtro: nada dispara sozinho.

## Condicionado

### R7. Forecast calibrado por conversão histórica
Taxa de conversão real por estágio/segmento no lugar de probabilidade estática, cruzada com velocidade no estágio, para Commit/Best Case/Upside baseado em dado. **Antes de especificar**, medir quantas transições de estágio existem (hoje: foto diária e `OpportunityStatusChange`). Com pouco histórico o forecast sai enganoso; nesse caso, aguardar volume.

### R8. Autoria das edições
Registrar *quem* editou (hoje só *quando*). Depende de o produto ter identidade de usuário/autenticação.

## Sob demanda

### R9. Novos conectores de fonte
HubSpot, Pipedrive e o provider "Website" (coleta de texto do site, que aparece como "em breve" nas Configurações). Cada um quando houver cliente que precise.

### R10. Entrada genérica por webhook
Receber empresas e contatos de qualquer CRM via webhook (estilo Zapier), sem um provider novo por conector. Inferido pelo nome do plugin Zapier do Mautic; não verificado. Exige autenticação da entrada e validação estrita do payload (dado externo é não confiável).

## Fora de escopo
 (mencionado pelas personas, descartado por ora)

- Scraping de LinkedIn/job postings, sentiment analysis de e-mail — alto
  esforço, baixo ROI enquanto os sinais estruturados (CRM, Maps) ainda nem
  estão implementados.
- "Regra builder" livre (AND/OR arbitrário) — as 6 personas convergem em
  evitar isso; 3 tipos fixos de regra bastam.
- Pontuação combinada única ("deal score" agregado) — o domínio proíbe
  colapsar os 4 números; fica só como ordenação de exibição.
- Campos personalizados de `Contact` (só `Account` por ora) — mudaria o
  contrato `DataProvider` inteiro; se necessário, é spec própria.
- **Custo de inação em R$ calculado pelo sistema** — permanentemente fora de
  escopo, não só "por ora". O valor exato sempre fica como pergunta em
  aberto na justificativa (Fase C), nunca um número que a IA ou uma regra
  determinística calcula sozinha — é a mesma linha vermelha de "nunca
  inventar fato", só que fácil de escorregar porque parece útil.
- Pipeline de streaming/CDC pra atualizar o dashboard em tempo real — o
  motor de regras já roda em lote/sob demanda; snapshot diário (Fase D)
  resolve sem essa complexidade. Reconsiderar só se surgir requisito de
  dashboard "ao vivo" com o motor rodando continuamente.
- Sequenciador automático de e-mail/disparo em lote — o produto é
  explicitamente "sugestão + confirmação humana", nunca "fila de
  outreach automatizada" (Fase G).
- Sincronização bidirecional (escrever de volta no Salesforce ou em outra fonte) — os providers só coletam, nunca alteram a fonte (ideia do Mautic descartada por conflitar com esta regra).
- Relatórios agendados enviados por e-mail e automação de campanha/pontuação automática — disparo automático contraria "sugestão + confirmação humana".
