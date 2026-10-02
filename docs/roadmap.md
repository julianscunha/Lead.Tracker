---
title: "Lead.Tracker — Roadmap"
order: 6
tags: [lead-tracker, roadmap, backlog]
---

# Roadmap

Só o que **ainda falta**. Tudo que já foi entregue está em [`implementacao/`](implementacao/README.md); as regras que valem para qualquer item novo estão em [`principios.md`](principios.md). Cada item, quando for a vez, ganha a sua spec em `implementacao/specs/` antes de qualquer código.

## Em aberto

### 1. URL da empresa (proposta, Fase K)
Hoje `Company.website` existe no modelo e no banco, mas só o Salesforce o preenche. Lacunas: (a) a busca do Google Maps não pede `websiteUri`, então prospects do Maps ficam sem URL e não deduplicam por domínio; (b) o site não vai da descoberta para a `Company` na promoção; (c) a API de oportunidades não devolve o site e a tela não o mostra. Módulos propostos: captura no Maps (só preenche se vazio, nunca sobrescreve o Salesforce) → `company_website` na API → link seguro na UI (`http(s)` apenas, `rel="noopener noreferrer"`). Atenção: pedir `websiteUri` na busca por proximidade muda a faixa de preço da Places API.

### 2. Forecast calibrado por conversão histórica
Taxa de conversão real por estágio/segmento no lugar de probabilidade estática, cruzada com velocidade no estágio, para Commit/Best Case/Upside baseado em dado. **Antes de especificar**, medir quantas transições de estágio já existem (hoje só há foto diária e o histórico de `OpportunityStatusChange`); com pouco histórico o forecast sai enganoso — nesse caso, aguardar volume.

### 3. Autoria das edições
Registrar *quem* editou a discovery (hoje só *quando*). Depende de o produto ter identidade de usuário/autenticação.

### 4. Novos conectores de fonte
HubSpot, Pipedrive e LinkedIn (no radar). O provider "Website" (coleta de texto do site) aparece como "em breve" nas Configurações e ainda não existe.

### 4a. Conflito entre fontes
Hoje, quando Salesforce, Maps e CSV trazem a mesma empresa, `core/normalization.py` fica com o primeiro valor não vazio, sem avisar. Proposta: precedência configurável por campo (fonte preferida e/ou mais recente) e, quando não der para decidir, mostrar o conflito ao usuário em vez de escolher em silêncio — mesma regra de "nunca sobrescrever em silêncio" do portfólio. Ideia do `SyncJudge` do Mautic (modos `BestEvidence`/`FuzzyEvidence`/`HardEvidence` e `ConflictUnresolvedException`); detalhes do funcionamento dele não foram lidos.

### 4b. Provider de enriquecimento
Completar uma empresa a partir do domínio (porte, setor, site) por API externa, como os plugins Clearbit e FullContact do Mautic. Provider só coleta e normaliza, como os demais. Depende do item 1 (URL da empresa).

### 4c. Entrada genérica por webhook
Receber empresas e contatos de qualquer CRM via webhook (estilo Zapier), sem escrever um provider novo por conector. Inferido pelo nome do plugin Zapier do Mautic; não verificado. Precisa de autenticação da entrada e validação estrita do payload (dado externo é não confiável).

### 5. Registro de auditoria geral
Hoje só a mudança de status tem histórico (`OpportunityStatusChange`). Falta registrar edições de qualificação, discovery, data de renovação e postura do contato: entidade, campo, valor anterior e novo, quando (e quem, quando houver autenticação — item 3). É também a base de dado para o forecast (item 2). Ideia vinda da leitura do Mautic (`LeadEventLog`), adaptada ao nosso modelo; sem código copiado (Mautic é GPL).

### 6. Visões salvas na lista de oportunidades
O vendedor guarda combinações de filtro com nome ("renovação em 60 dias + severidade alta") e reabre com um clique; opcionalmente exporta pelo PDF/Excel que já existe. Ideia dos segmentos do Mautic. Só leitura e filtro: nada dispara sozinho.

### 7. Lista de "não contatar"
Hoje não existe esse conceito. Registro por contato ou empresa e por canal, com motivo (pedido do contato, e-mail inválido, decisão do vendedor), comentário e data, mantendo o histórico (insert-only, como no Mautic: `DoNotContact` tem `reason` unsubscribed/bounced/manual, `channel`, `comments`, `dateAdded`). Quando ativo, as sugestões de outreach daquele contato/canal são bloqueadas e a tela explica o porquê. Reforça o limite diário por rep e ajuda na conformidade com a LGPD.

## Fora de escopo (mencionado pelas personas, descartado por ora)

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
