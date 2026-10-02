---
title: "Fase N — Conflito entre fontes"
order: 37
tags: [lead-tracker, implementacao, spec]
---

# Fase N — Conflito entre fontes

Item R4 do [`roadmap`](../../roadmap.md). Consulta: `ecc:architect` (menor desenho, riscos, ponto de interceptação), antes de decidir. Status: **proposta, aguardando confirmação do mapa de módulos**. Inspirado no `SyncJudge` do Mautic (o funcionamento interno dele não foi lido); sem código copiado (Mautic é GPL).

## Problema

A reconciliação de uma empresa já gravada usa `merge_pair(persistida, buscada)` (`core/normalization.py`), onde "primeiro valor não vazio vence" e a persistida vem primeiro. Duas consequências, ambas silenciosas:

1. **Dado velho para sempre, mesmo com uma só fonte.** Se o Salesforce muda o setor ou o número de funcionários, o valor já gravado nunca é atualizado.
2. **Fontes que discordam.** Salesforce, Maps e CSV trazem valores diferentes para a mesma empresa e vence quem chegou primeiro, sem aviso.

## Regra (versão 1, deliberadamente pequena)

- **Mesma fonte atualiza.** Valor novo da fonte que gravou o campo substitui o atual, e a troca vai para a auditoria (R3) com `actor = "sync:<fonte>"`, antes e depois. Isso não é sobrescrever em silêncio porque fica registrado.
- **Outra fonte que difere abre conflito.** O valor atual continua valendo até o usuário escolher.
- **Ausência não é discordância.** Valor vazio ou `None` vindo da fonte nunca apaga nem abre conflito. `""` e espaços viram `None` antes de comparar; `0` é valor real.
- **Campo editado à mão** (origem `manual`) nunca é sobrescrito pelo sync; valor diferente da fonte abre conflito.
- **Igualdade ignora formatação:** `normalize_website` e `normalize_name` (caixa, acento, pontuação). Sem helper novo.
- **Resolvido não reabre.** A resolução guarda o par (fonte, valor normalizado) rejeitado; só reabre se a fonte trouxer um valor **diferente** desse.
- **Fora desta versão:** política configurável de "fonte preferida" por campo (só quando houver volume real de conflitos repetidos), tela de política em Configurações, conflito de `is_customer` (continua OU), `last_activity_at` (mais recente), `sources`.

Campos que entram: `legal_name`, `website`, `industry`, `address`, `annual_revenue`, `employee_count`, `customer_status`. `deal_size_hint` fica de fora: vem do mapeamento do usuário depois do merge e entra em `field_sources` como `mapping`, nunca como conflito.

## Mapa de capacidades

| Ordem | Módulo | Responsabilidade |
|---|---|---|
| 1 | `field-sources-model` | `Company.field_sources` (JSON: campo → tipo da fonte; `manual`, `mapping` ou `legacy`) + migração leve. |
| 2 | `reconcile-core` | Função pura `reconcile(persistida, buscada, source_type) -> (Company, conflitos, mudanças)` em `core/normalization.py`. `merge_pair` **não muda** (também é usado dentro da mesma fonte e abriria falsos conflitos). |
| 3 | `conflicts-persistence` | Tabela `field_conflicts`, repositório (abrir sem duplicar, listar, resolver) e escrita do campo + `_audit` na resolução. |
| 4 | `sync-wiring` | Chamar `reconcile` onde já existe empresa gravada: `backend/sync.py`, `backend/routes_csv_import.py`, promoção geo (`backend/routes_sync.py`). Conflito e auditoria na mesma sessão do `save_company`. |
| 5 | `conflicts-api-ui` | `GET /field-conflicts`, `POST /field-conflicts/{id}/resolve`; seção "Conflitos de dados" em Configurações (lista, valor de cada fonte, escolher). |

## Modelo

`field_sources: dict[str, str]` na `Company`. **Empresas já gravadas:** empresa de uma só fonte recebe `sources[0].type`; com várias fontes recebe `legacy` e **não** abre conflito retroativo (evita inundação na primeira sincronização depois da atualização); só divergências futuras abrem.

`FieldConflict`: `id`, `company_id`, `field`, `candidates` (lista de `{source, value, seen_at}`), `status` (`open`/`resolved`), `resolved_value`, `resolved_at`, `rejected` (pares fonte+valor normalizado rejeitados). Quem resolveu fica na auditoria (`_audit`, `actor` = `rep_id` informado), sem coluna própria.

## Resolução

O usuário escolhe um dos valores candidatos (ou mantém o atual). Grava no campo, marca `field_sources[campo]` com a fonte escolhida, registra na auditoria e guarda o(s) rejeitado(s). Escolher o valor de outra fonte passa a tratar essa fonte como a dona do campo daí em diante.

## Pontos de atenção

- `actor` reservado: além de `sync`, o prefixo `sync:` também passa a ser rejeitado nas rotas de edição.
- Os valores dos campos (setor, endereço, site) podem aparecer na lista de conflitos e na auditoria; não incluem texto livre pessoal. Mesmo assim, ficam fora de exports e prompts de IA.
- Achado fora de escopo, para uma correção à parte: o CSV preenche `segment`, `region` e `rep_id`, mas quando a empresa já existe esses valores são descartados sem aviso (`backend/routes_csv_import.py`, `merge_pair` mantém os da base). Entra no roadmap como item próprio, com teste de regressão.

## Teste

`tests/test_reconcile.py`: atualização pela mesma fonte (com mudança auditada), conflito vindo de outra fonte (valor atual mantido), `None`/vazio que não apaga, `manual` não sobrescrito, igualdade ignorando formatação, conflito resolvido que não reabre, migração (uma fonte × várias). Persistência e rotas: abrir sem duplicar, resolver grava campo + auditoria, `rep_id` `sync:x` rejeitado. Dados fictícios.

## Critério de sucesso

- [ ] Valor alterado na própria fonte atualiza a empresa e deixa rastro.
- [ ] Duas fontes que discordam nunca decidem em silêncio: o valor atual fica e o conflito aparece.
- [ ] Rodar o sync de novo depois de resolver não reabre o mesmo conflito.
- [ ] Atualizar uma instalação existente não gera uma enxurrada de conflitos.
