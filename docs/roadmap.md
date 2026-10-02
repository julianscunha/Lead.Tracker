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
