# Fase E — Prospecção geográfica (Google Maps)

Spec viva desta fase (`spec-driven-development`) — atualizada a cada
módulo entregue, não escrita de uma vez no início. Ver `docs/roadmap.md`
pro texto original dos requisitos; este documento registra as decisões
de como implementar cada um, o porquê, e o que cada módulo entrega.

## Capability map (consulta ao agente `Plan`, confirmado pelo usuário)

Fase E cruza pelo menos 4 fronteiras de responsabilidade (config/ICP,
coleta de provider, motor de scoring/anti-spam, apresentação/export) que
hoje não existem como módulos isolados — passou pelo Phase 0 (scope
check) do `spec-driven-development` antes de qualquer spec de módulo.

| Ordem | Módulo | Responsabilidade | Consulta a especialista |
|---|---|---|---|
| 1 | `icp-profile-store` | Critério de ICP por instalação como config genérica (categoria, porte, raio, produto de referência) — schema-less, mesmo padrão da config de Fontes. | Não (mecânica) |
| 2 | `places-signal-collector` | Provider Google Places: coleta bruta (categoria, business_status, reviews) — normaliza, nunca pontua. | Não (mecânica) |
| 3 | `icp-auto-derivation` | Deriva ICP sugerido a partir de Company⋈Opportunity onde `is_customer=true` e `opportunity_score` alto. | Sim — Growth Hacker/Sales Engineer (threshold de score, amostra mínima) |
| 4 | `geo-scoring-rules` | Regras determinísticas em camadas (categoria > business_status=OPERATIONAL > reviews como proxy fraco) dentro do `opportunity_engine` genérico. | Sim — Outbound Strategist (hierarquia de sinais, pesos) |
| 5 | `anti-spam-promotion-gate` | Score mínimo configurável pra sair de `detected`; cap de contatos por lote/dia por rep. | Sim — Outbound Strategist/Sales Engineer (cap errado = spam real) |
| 6 | `icp-wizard-ui` | Assistente de 3-4 passos (produto → raio → revisar → confirmar). | Sim — Discovery Coach/Sales Engineer (fluxo, fricção) |
| 7 | `geo-results-view` | Mapa/lista visual dos resultados — não tabela crua. | Sim — Sales Engineer/Discovery Coach |
| 8 | `geo-export` | Reuso do exportador PDF/Excel já existente em Oportunidades. | Não (mecânica) |

Ordem de construção: `icp-profile-store` → `places-signal-collector`
(paralelizáveis) → `icp-auto-derivation` → `geo-scoring-rules` →
`anti-spam-promotion-gate` → `icp-wizard-ui` → `geo-results-view` →
`geo-export`.

**Riscos arquiteturais registrados pelo Plan:**
- `geo-scoring-rules`/`anti-spam-promotion-gate` são onde é mais fácil
  violar "core nunca hardcode de vendor" (tentação de `if
  business_status == 'OPERATIONAL'` direto no engine) — contrato
  genérico ("sinal de status normalizado") precisa existir antes do
  provider.
- `icp-auto-derivation` corre risco de viés estatístico com amostra
  pequena de clientes satisfeitos — piso mínimo de amostra antes de
  sugerir automaticamente, cai no fluxo manual do wizard abaixo disso.
- Nenhum módulo precisa de dependência ou abstração nova — todos
  reaproveitam padrões já existentes (config de Fontes, exportador de
  Oportunidades, `opportunity_engine`).

## Módulo 1 — `icp-profile-store`

Classificado "mecânico" no capability map — sem consulta a especialista
(é só extensão do padrão de config já validado nas Fases 0-D). Novo
modelo `ICPProfile`: `reference_product_id`, `place_category`,
`company_size_hint`, `radius_km`. **Singleton** — uma linha só por
instalação, `id` sempre fixo `"icp_profile"`, nunca aceito do corpo da
requisição (`ICPProfileIn` não tem campo `id`) — fecha qualquer
possibilidade de o cliente HTTP criar uma 2ª configuração concorrente.
`place_category`/`company_size_hint` são string livre, nunca enum
fechado — núcleo genérico, a UI do wizard (módulo 6, ainda não
construído) é quem restringe as opções mostradas.

`GET /icp-profile` antes de qualquer `PUT` devolve 200 com todos os
campos `None`, nunca 404 — é config opcional de uma feature ainda em
construção, não um recurso que "não existe". `radius_km` negativo é
rejeitado na fronteira HTTP (`Field(ge=0)`), `None` (sem raio
configurado ainda) continua aceito.

Revisão de código: **aprovado sem pendências** — singleton confirmado
inquebrável, contrato GET-antes-de-PUT verificado, ausência de taxonomia
fechada confirmada, escopo mínimo respeitado (nenhuma lógica de
scoring/oportunidade vazou pra este módulo).

### Teste

- Modelo: defaults (`id` fixo, todos os outros `None`).
- Repositório: `get` antes do primeiro `save` retorna `None`; round-trip;
  segundo `save` faz upsert na mesma linha (nunca duplica).
- Rota: `GET` antes de qualquer `PUT` retorna 200 com corpo todo `None`
  (nunca 404); `PUT` round-trip e upsert; `radius_km` negativo rejeitado
  (422).

### Critério de sucesso

- [x] Singleton nunca duplica, `id` nunca vem de input do usuário.
- [x] `place_category`/`company_size_hint` sem taxonomia fechada.
- [x] `GET` antes do primeiro `PUT` nunca 404.
- [x] Suíte completa e revisão de código sem pendências.
