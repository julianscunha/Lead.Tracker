---
title: "Fase K — URL da empresa"
order: 34
tags: [lead-tracker, implementacao, spec]
---

# Fase K — URL da empresa

Item R1 do [`roadmap`](../../roadmap.md). Consultas: `ecc:architect` (sanitização e reconciliação), antes de decidir. Status: **concluída** (5 módulos). Revisão de segurança (`ecc:security-reviewer`) aplicada.

## Problema

`Company.website` existe no modelo e no banco, mas só o Salesforce o preenche. O Google Maps não pede `websiteUri`, a promoção geográfica não grava site, a API não o devolve e a tela não o mostra. Achado extra na leitura do código: a promoção (`backend/routes_sync.py`, `POST /geo-discovery/run`) cria uma `Company` nova a cada busca, sem reconciliar com as existentes, então rodar a busca duas vezes duplica empresas e oportunidades.

## Mapa de capacidades

| Ordem | Módulo | Responsabilidade |
|---|---|---|
| 1 | `normalize-website` | Função pura `normalize_website(raw) -> str \| None` em `core/normalization.py` (ao lado de `normalize_domain`). |
| 2 | `places-website-capture` | `PlaceSignal.website` + `places.websiteUri` no field mask + helper aplicado na entrada (Maps e Salesforce). |
| 3 | `geo-reconcile` | Promoção geo reconcilia com empresas existentes **antes** de `select_promotions`; grava `Company.website`; cota passa a contar oportunidades geo do dia. |
| 4 | `opportunity-website-api` | `OpportunityOut.company_website` (helper reaplicado na saída). |
| 5 | `opportunity-website-ui` | Link no detalhe da oportunidade. |

## Decisões

- **Sanitização nos dois lados, um helper só.** Entrada (provider) para o banco nunca guardar lixo e o `dedup_key` usar valor limpo; saída (API) para cobrir dado antigo, CSV e fonte futura.
- **Regra do helper:** `strip()`; rejeita vazio, espaço ou caractere de controle, mais de 2048 caracteres; sem esquema → prefixa `https://` (o teste de esquema é `^[a-z][a-z0-9+.-]*:`, não `://`, porque `javascript:alert(1)` não tem `//`); aceita só `http`/`https` com host contendo ponto e sem `user:pass@`. Qualquer outro caso vira `None`, sem erro (dado opcional).
- **Nunca buscamos a URL** (sem SSRF). Única exceção (implementada na Fase P): o `COMPANY_WEBSITE` informado pelo operador, lido com `core/safe_fetch.py`. Qualquer enriquecimento futuro (roadmap R5) precisará validar IP privado.
- **Reconciliação geo:** monta `existing_by_key` uma vez; com match, `merge_pair(existente, nova)`; sem match, usa a nova. Roda antes de `select_promotions`, para empresa conhecida não gastar vaga da cota.
  - Chave: domínio quando houver site; sem site, **nome normalizado só entre empresas que já têm fonte `google_maps`** (nunca funde com cliente do Salesforce só por nome). `ponytail:` filiais homônimas dentro do mesmo raio podem fundir; upgrade: guardar `place_id` (muda o schema de `SourceRef`) e reconciliar por ele.
  - Blocklist de domínios genéricos no dedup (`facebook.com`, `instagram.com`, `wa.me`, `linktr.ee`, `sites.google.com`): o link continua exibido, mas não serve de chave.
  - Empresa que já é cliente (`is_customer`): não cria oportunidade geo.
  - Já existe oportunidade `geo-discovery` não descartada para a empresa: **pula** (sem duplicar). Se não existir, cria com `company_id` da empresa existente.
  - **Rep:** empresa de **outro** rep não vira prospect de quem buscou (vai para "já na base", sem oportunidade nem cota); empresa **sem dono** passa a ser do rep que a descobriu. Achado da revisão: sem isso, a oportunidade caía na carteira de outro rep e burlava a cota de quem buscou.
  - **Mesma busca:** dois lugares com a mesma chave (filiais com o mesmo site) viram um só, para não gerar 2 oportunidades/vagas de cota na mesma empresa.
  - **Subdomínios de plataforma** (`m.facebook.com`, `l.instagram.com`) também não servem de chave (comparação por sufixo).
  - Empresas já conhecidas voltam numa lista própria ("já na base") no resultado, não em `rejected`.
- **Cota diária** (`core/repository.py::count_geo_discoveries_today`) hoje conta `Company` criada hoje com fonte `google_maps`; com merge isso erra. Passa a contar `Opportunity` `type=geo-discovery` criada hoje pelo rep.
- **Custo:** `places.websiteUri` na busca por proximidade muda a faixa de preço da Places API (Enterprise). A cota diária por rep limita o gasto, que sobe um pouco por busca.
- **Retroativo:** os prospects já gravados não ganham URL. Preencher exigiria consulta de detalhes por empresa; fora de escopo.
- **Exports:** PDF/Excel que passarem a incluir o site devem usar o mesmo helper (não faz parte desta fase incluir a coluna).

## UI

Link no detalhe da oportunidade, rotulado pelo domínio (sem esquema), `target="_blank"` e `rel="noopener noreferrer"`, renderizado só se a API devolver `http(s)://`. Sem site, a linha não aparece.

## Fora de escopo

`place_id` em `SourceRef`; enriquecimento por domínio (R5); coluna de site nos exports; mudar o rep de empresa existente.

## Teste

Unit: `normalize_website` (válidos, sem esquema, `javascript:`, `data:`, userinfo, espaço, 2049 caracteres, host sem ponto), blocklist, reconciliação (match por domínio, nome só entre fontes Maps, cliente não vira prospect, rerun não duplica, oportunidade geo existente é pulada), cota por oportunidade. Integração: `PlaceSignal` lê `websiteUri` de resposta mockada e o field mask o inclui; API devolve `company_website` limpo; frontend renderiza link só com `http(s)`. Dados fictícios.

## Critério de sucesso

- [x] Rodar a busca duas vezes não duplica empresa nem oportunidade.
- [x] Nenhum esquema além de `http`/`https` chega à tela.
- [x] Site do Salesforce nunca é sobrescrito por um do Maps.

## Resíduos aceitos

IP privado (`http://10.0.0.1`) é aceito como URL: só vira link, nada o busca (se um enriquecimento futuro buscar, precisa validar). `place_id` continua sem ser guardado.
