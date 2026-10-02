---
title: "Fase L — Lista de não contatar"
order: 35
tags: [lead-tracker, implementacao, spec]
---

# Fase L — Lista de "não contatar"

Item R2 do [`roadmap`](../../roadmap.md). Consulta: `ecc:architect` (furos do modelo e caminhos de escape), antes de decidir. Status: **proposta, aguardando confirmação do mapa de módulos**.

## Problema

Não existe o conceito de "não contatar". Hoje o produto sugere o próximo toque, gera rascunho de e-mail e registra envios sem saber que um contato pediu para não ser abordado (ou que o e-mail é inválido). Isso é risco de relacionamento e de LGPD, e contraria a regra de que outreach é sempre sugestão com confirmação humana. Ideia vinda do `DoNotContact` do Mautic (insert-only, com motivo, canal, comentário e data); sem código copiado (Mautic é GPL).

## Mapa de capacidades

| Ordem | Módulo | Responsabilidade |
|---|---|---|
| 1 | `dnc-model-repo` | Entidade `DoNotContact` + persistência (criar, listar, retirar uma única vez). |
| 2 | `dnc-rule` | Função pura `find_active_block(...)` em `core/opportunity_engine.py`. |
| 3 | `dnc-enforcement` | Aplicação no backend: sugestão de toque, silêncio/single-thread, registro de toque, rascunho de e-mail, lista de contatos, e as rotas de criar/listar/retirar. |
| 4 | `dnc-ui` | Seção "Não contatar" no detalhe da oportunidade e estados na sugestão/rascunho. |

## Modelo

`DoNotContact`: `id`, `company_id`, `contact_id` (None = empresa inteira), `contact_email` (snapshot normalizado, `strip().casefold()`; None se não houver), `channel` (None = todos os canais), `reason` (`requested_by_contact` / `invalid_contact_data` / `rep_decision` / `other`), `comment` (≤500 caracteres), `created_by` (rep), `created_at`, `lifted_at`, `lifted_by`, `lift_reason`. Histórico mantido: nada é apagado; retirar grava `lifted_at/by/reason` **uma única vez** (`WHERE lifted_at IS NULL`), aceitável como "insert-only por campo", como o resto do repositório.

## Regra (módulo 2)

`find_active_block(entries, company_id, contact_id, contact_email, channel) -> DoNotContact | None`. Ativo = `lifted_at is None`. Casa quando:
- bloqueio de **empresa inteira** (sem contato) da mesma `company_id`; contato novo que chega depois fica coberto automaticamente; ou
- bloqueio de **contato** com o mesmo `contact_id`, **ou** o mesmo e-mail normalizado (vale globalmente, ignorando `company_id`: sobrevive a reimport do CRM com id novo e a empresa duplicada por mudança de chave de dedup). E-mail só é comparado quando os dois lados são não vazios (nunca `None == None`); e
- canal: o do bloqueio é `None` (todos) ou igual ao canal consultado, ambos normalizados (sem acento, minúsculo, `strip`).

`ponytail:` canais são texto livre (core genérico, sem lista fechada): um sinônimo ("telefone" × "ligação") escapa de um bloqueio **por canal**. Mitigação: o padrão da UI é "todos os canais"; a UI oferece os canais que a cadência já usa. Upgrade: conjunto fechado de canais se isso virar problema real.

## Aplicação (módulo 3)

Sempre no backend, nunca só na UI.

- **`GET /opportunities/{id}/next-suggested-touch`:** bloqueio de empresa inteira (canal `None` ou igual ao canal sugerido) → novo estado `bloqueado` com o motivo, sem sugestão. Bloqueio de contato só alerta (`last_contact_blocked`) sobre o último contato. Com bloqueio de empresa para todos os canais, **suprime** os sinais de silêncio e de single-thread (empurrariam o vendedor a contatar); contatos bloqueados saem do cálculo de cobertura.
- **`POST /opportunities/{id}/outreach-touches`:** passa a **validar que `contact_id` pertence à empresa** da oportunidade (hoje não valida) e, com o contato carregado, checa o bloqueio. Bloqueado → 422 amigável. Com `acknowledge_block=true` grava o toque mesmo assim, marcado `block_acknowledged` para auditoria: o toque é fato consumado e recusá-lo apagaria a evidência de que houve contato apesar do bloqueio.
- **`POST /exports/email-draft`:** passa a exigir `opportunity_id` (hoje só recebe `company_name`, sem como checar) e opcional `contact_id`; carrega a empresa no servidor. Bloqueado (canal e-mail) → 422 amigável.
- **`GET /companies/{id}/contacts`:** cada contato volta com `do_not_contact: bool`.
- **Rotas:** `POST /companies/{id}/do-not-contact`, `GET /companies/{id}/do-not-contact` (ativos primeiro), `POST /do-not-contact/{id}/lift`.
- **Privacidade:** `comment` e `lift_reason` podem ter dado pessoal; ficam fora de exports, logs e prompts de IA (e como o rascunho é bloqueado, nenhum prompt nasce para um bloqueado). Teste de regressão: o comentário não aparece em PDF/Excel.

## UI (módulo 4)

No detalhe da oportunidade: lista dos bloqueios ativos (quem, canal, motivo, data) com "Reativar" (pede motivo), formulário "Marcar como não contatar" (empresa inteira ou um contato da empresa; canal, padrão "todos"; motivo em dropdown; comentário) e, quando bloqueado, a sugestão de toque e o botão de rascunho mostram o porquê em linguagem de negócio em vez de sugerir contato.

## Fora de escopo

Importar lista de bloqueio de CSV; bloqueio em massa; mudança de status "contacted" (não lida; verificar se precisa de alerta); fusão automática de bloqueios entre empresas duplicadas além do casamento por e-mail; conjunto fechado de canais.

## Teste

Unit: `find_active_block` (empresa inteira, contato por id, por e-mail com caixa/espaço diferente, e-mail vazio nunca casa, canal None/igual/diferente/com acento, retirado não bloqueia). Persistência: criar, listar, retirar uma vez (segunda retirada não altera). Rotas: sugestão `bloqueado`, silêncio/single-thread suprimidos, toque rejeitado/aceito com `acknowledge_block`, `contact_id` de outra empresa rejeitado, rascunho rejeitado, `do_not_contact` na lista de contatos, comentário fora dos exports. Dados fictícios.

## Critério de sucesso

- [ ] Nenhum caminho do backend sugere, redige ou registra contato com alvo bloqueado sem aviso explícito.
- [ ] Bloqueio por e-mail sobrevive a reimport do contato com id novo.
- [ ] Retirar um bloqueio nunca apaga o histórico.
