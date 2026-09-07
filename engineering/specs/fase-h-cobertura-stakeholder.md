# Fase H — Cobertura de stakeholder e risco de single-thread

Depende só da Fase A (`Contact` já existe, com `seniority_tier` inferido de
`role` desde a Fase C). Pode rodar em paralelo às demais fases, não depende
delas. Ver `engineering/roadmap.md` pro texto original dos requisitos e a
origem da escolha (convergência de Deal Strategist + Account Strategist).

## Mapa de capacidades (confirmado pelo usuário)

| Ordem | Módulo | Responsabilidade | Consulta a especialista |
|---|---|---|---|
| 1 | `outreach-touch-contact-link` | `OutreachTouch.contact_id` opcional — permite (nunca exige) atribuir um toque a um contato específico da conta. | Não (mecânico) |
| 2 | `contact-stance-field` | `Contact.stance` (enum aberto: `champion`/`neutro`/`detrator`/desconhecido) — eixo de DISPOSIÇÃO, distinto de `seniority_tier` (eixo de AUTORIDADE). | Deal Strategist |
| 3 | `single-threaded-risk-signal` | Função pura — oportunidade qualificada+ OU conta com renovação próxima, com cobertura de contato fraca → sinaliza risco. Nunca muda status/dispara ação sozinha. | Deal Strategist + Account Strategist |
| 4 | `stakeholder-coverage-ui` | Sinal exposto na tela de Oportunidades — linguagem de decisão, nunca alarme genérico. | Sales Engineer |

## Módulo 1 — `outreach-touch-contact-link`

Mecânico, sem consulta a especialista.

### Implementação

- `core/models.py` — `OutreachTouch.contact_id: str | None = None`. Nunca
  obrigatório: toques antigos continuam válidos sem ele, e o rep pode
  registrar um toque sem saber (ou sem querer detalhar) com qual contato
  específico da conta falou.
- `core/db_models.py` — `OutreachTouchORM.contact_id` (nullable) — coluna
  nova adicionada automaticamente via `core/db.py::_add_missing_columns`
  em qualquer instalação existente, sem migração manual.
- `core/repository.py` — `save_outreach_touch`/`list_outreach_touches`
  atualizados pra ler/gravar o campo.
- `backend/routes_sync.py` — `OutreachTouchIn.contact_id` (opcional) no
  corpo de `POST .../outreach-touches`, repassado pro `OutreachTouch`
  construído na rota.

**Deliberadamente fora deste módulo**: nenhuma validação de que
`contact_id` referencia um `Contact` real, muito menos um `Contact` da
mesma `Company` da oportunidade. É só a "plumbing" — a checagem de
referência (e o próprio cálculo de cobertura) é responsabilidade do
módulo 3 (`single-threaded-risk-signal`).

### Achado da revisão de código

Nenhum — revisão aprovou sem achados Importantes/Críticos. Uma sugestão
não-bloqueante (comentário explicando a ausência de validação de
referência) foi aplicada.

### Teste

- `tests/test_persistence.py` (+1, +1 assert no teste existente): toque
  sem `contact_id` continua `None` por padrão; toque com `contact_id`
  round-trips corretamente.
- `tests/test_routes_sync.py` (+1): `POST .../outreach-touches` aceita e
  devolve `contact_id`.

### Critério de sucesso

- [x] `contact_id` nunca obrigatório — toda chamada existente (testes,
      rota) continua funcionando sem passar o campo.
- [x] Nenhuma validação de referência prematura — módulo 1 é só
      persistência do dado bruto.
- [x] Coluna nova adicionada sem migração manual (mesmo mecanismo já
      testado de `_add_missing_columns`).
- [x] Revisão de código sem achados Importantes/Críticos.
