---
title: "Fase J — Gate de \"discovery completa\""
order: 30
tags: [lead-tracker, implementacao, spec]
---

# Fase J — Gate de "discovery completa"

Origem: backlog do `docs/implementacao/fases.md` (Discovery Coach). Consulta ao
Discovery Coach feita antes desta spec; decisões abaixo incorporam a resposta.

## Mapa de capacidades (proposto, aguardando confirmação do usuário)

| Ordem | Módulo | Responsabilidade | Especialista |
|---|---|---|---|
| 1 | `discovery-fields` | `Opportunity.root_cause_stated`, `trigger_event`, `champion_stake` (texto, nullable) + `discovery_skipped` (bool) + `discovery_skip_reason` + quem/quando editou. Só escrita humana (rota própria; providers/CSV nunca populam). | Discovery Coach |
| 2 | `discovery-gate` | Função pura em `core/opportunity_engine.py` (padrão `requires_status_change_justification`): `detected→qualified` exige os 3 campos válidos OU `skip_reason`. Erro de domínio amigável (422, pt-br). Aplicada na camada de serviço, não só na rota. | Discovery Coach |
| 3 | `discovery-ui` | Formulário com os 3 rótulos, botão "Qualificar sem discovery" (justificativa obrigatória), selo informativo "discovery pendente" para quem já passou de `detected`. | Sales Engineer |

## Decisões

- **Bloqueia de verdade**, só `detected→qualified`, só no backend. Saída: "Qualificar sem discovery" com justificativa, gravada como `discovery_skipped`.
- **Validação mínima** (função pura, sem IA, sem checagem semântica): após trim ≥15 caracteres e ≥3 palavras; blocklist genérica normalizada (sem acento/pontuação, minúsculas): n/a, na, nao sei, tbd, teste, xxx, sem info, depois vejo; rejeita caractere único repetido. Mensagem diz o que faltou.
- **Grandfather**: oportunidades já em `qualified` ou além não são bloqueadas; campos ficam `NULL` (sem backfill) e o selo cobre a lacuna. Voltar e avançar de novo não exige os campos de novo se já preenchidos. `dismissed→reaberto` segue a justificativa de status existente; o gate vale só ao reentrar em `qualified` sem campos.
- **Configurável**: liga/desliga em Configurações (chave nova em `.env-model`, nunca edição manual). Padrão: ligado.
- **Privacidade**: `champion_stake` é dado de pessoa — fora de exports, logs e prompts de IA.
- **Schema**: colunas novas nullable via `_add_missing_columns` (sem migração manual).

## Rótulos (linguagem de vendedor)

- `root_cause_stated` — "Por que isso acontece hoje?" (causa nas palavras do cliente, não o sintoma)
- `trigger_event` — "Por que agora?" (auditoria, contrato vencendo, incidente, crescimento)
- `champion_stake` — "O que o seu contato ganha ou perde com isso?"

## Fora de escopo

- Validação por IA; métricas de `discovery_skipped`/tempo em `detected` (registrar no backlog se o atrito aparecer).

## Teste

Unit: validador (válidos, blocklist, repetição, curto), gate (avanço, skip, grandfather, voltar/avançar, reabertura). Integração: 422 amigável na rota e no caminho de serviço; providers não escrevem os campos. Dados fictícios.
