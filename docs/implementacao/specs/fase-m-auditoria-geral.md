---
title: "Fase M — Registro de auditoria geral"
order: 36
tags: [lead-tracker, implementacao, spec]
---

# Fase M — Registro de auditoria geral

Item R3 do [`roadmap`](../../roadmap.md). Consulta: `ecc:architect` (escrita explícita × listener, privacidade, furos, autoria), antes de decidir. Status: **proposta, aguardando confirmação do mapa de módulos**. Ideia do `LeadEventLog` do Mautic; sem código copiado (Mautic é GPL).

## Problema

Só a mudança de status tem histórico (`OpportunityStatusChange`). Edições de qualificação, discovery e data de renovação sobrescrevem o valor sem rastro, e o sync pode mudar `renewal_date`, `industry` e `deal_size_hint` (`apply_field_mapping_updates`, `core/repository.py`) sem que ninguém saiba. Sem isso não dá para explicar "por que esse número mudou" nem alimentar o forecast (R7).

## Mapa de capacidades

| Ordem | Módulo | Responsabilidade |
|---|---|---|
| 1 | `audit-model-repo` | Tabela `audit_log`, modelo `AuditEntry`, helper `_audit(...)` e leitura `list_audit_entries(...)`. |
| 2 | `audit-writes` | Chamar `_audit` nos caminhos de escrita: qualificação, discovery, renovação, postura do contato, mapeamento no sync e `discovery_skipped`. |
| 3 | `audit-read-api` | `GET /opportunities/{id}/audit` e `GET /companies/{id}/audit`; rotas de edição passam a aceitar `rep_id` opcional. |
| 4 | `audit-ui` | Lista "Histórico de alterações" no detalhe da oportunidade. |

## Decisões

- **Escrita explícita, não listener do ORM.** Cada `update_*` já carrega a linha antes de mudar, então o valor antigo está na mão. Os upserts do Core (`save_company`, `save_contact`, `save_opportunity`) não passam por listener de ORM, e um listener registraria escrita de máquina (`synced_at`, `discovery_edited_at`) e esconderia a regra. Um helper `_audit(session, ...)` é chamado antes do `commit` de cada função: auditoria e mudança na **mesma transação**.
- **Sem entrada quando o valor não muda**, comparando depois da normalização (na discovery o `strip()` vem antes de gravar).
- **Modelo `AuditEntry`:** `id`, `entity_type` (`opportunity` / `company` / `contact`), `entity_id`, `company_id`, `field`, `old_value`, `new_value` (texto; data em ISO UTC; enum pelo `.value`), `changed_at`, `actor` (anulável). Índices `(entity_type, entity_id, changed_at)` e `(company_id, changed_at)`.
- **Privacidade (LGPD):** texto livre nunca é gravado. `root_cause_stated`, `trigger_event`, `champion_stake` (discovery) e `severity_note` registram só `preenchido` / `alterado` / `removido`. Não registra `discovery_edited_at` nem nada que o motor grava.
- **O que entra:**
  - qualificação: `scope_note`, `criticality` (valor), `severity_note` (marcador);
  - discovery: os 3 campos (marcador);
  - `Company.renewal_date`; e `industry` / `deal_size_hint` quando o sync os altera (`actor = "sync"`), porque esse caminho contorna o `update_company_renewal_date`;
  - `Contact.stance` (a função existe, ainda sem rota; auditar é barato);
  - `discovery_skipped` ao qualificar sem discovery (`update_opportunity_status`), motivo como marcador.
- **Fora:** status (já tem `OpportunityStatusChange`), bloqueios de "não contatar" (histórico próprio), qualquer escrita do motor.
- **Autoria:** coluna anulável, nunca inventada. As rotas de qualificação, discovery e renovação passam a aceitar `rep_id` **opcional** (o mesmo id que o usuário informa na tela para o resto do produto, autodeclarado, sem autenticação); ausente = `NULL`, e a UI mostra "não identificado". Escrita automática usa `"sync"`. Não usa o `rep_id` da empresa.
- **Retenção:** volume pequeno (só edição manual e mudança real do sync), sem expurgo nesta fase. Como o texto pessoal nunca é gravado, não há obrigação de expurgo por LGPD agora.
- **Concorrência:** o SQLite serializa as escritas; "último vence" fica visível no log, sem lock.

## UI

No detalhe da oportunidade, lista "Histórico de alterações" (mais recentes primeiro): data, o que mudou em linguagem de negócio (rótulos, não nome de campo), de → para (ou "preenchido/alterado"), e quem ("não identificado" quando vazio). Mostra as entradas da oportunidade e da empresa dela.

## Fora de escopo

Desfazer a partir do log; exportar o log; retenção/expurgo; autenticação (R8); buscar o log de todas as empresas numa tela só.

## Teste

Unit/persistência: cada `update_*` grava 1 entrada com antigo/novo certos; mesmo valor não grava; texto livre nunca aparece no log; `apply_field_mapping_updates` grava com `actor="sync"` só quando muda; auditoria e mudança na mesma transação (falha no commit não deixa entrada solta). Rotas: `rep_id` opcional vira `actor`; sem ele, `NULL`; leitura devolve oportunidade + empresa em ordem. Dados fictícios.

## Critério de sucesso

- [ ] Toda edição manual de qualificação, discovery e renovação deixa rastro com antes/depois.
- [ ] Nenhum texto livre pessoal é gravado no log.
- [ ] O sync deixa de poder mudar `renewal_date` sem rastro.
