"""
Regras determinísticas de pontuação de sinal geográfico (Fase E, módulo 4
`geo-scoring-rules`) — consulta ao agente Outbound Strategist antes de
implementar (hierarquia de sinais e pesos são decisão de negócio, não
técnica).

Camadas, da mais forte pra mais fraca (mesma ordem do roadmap):
1. `business_status` em `CLOSED_TEMPORARILY`/`CLOSED_PERMANENTLY` →
   **descarte determinístico**, `None` (não `0.0`) — decisão deliberada:
   se o descarte fosse só um score baixo dentro da mesma escala 0-1, um
   threshold mal configurado no `anti-spam-promotion-gate` (módulo 5,
   ainda não construído) poderia reverter isso e reativar um lugar
   fechado. Separar o TIPO de retorno (`None` vs. `float`) torna a regra
   impossível de contornar por configuração. `None` (campo ausente) e
   `"BUSINESS_STATUS_UNSPECIFIED"` (valor real do enum da Places API,
   achado da revisão de código) NUNCA são tratados como fechado — os
   dois significam "não sabemos", nunca "sabemos que fechou"; mesmo
   princípio de "ausência de dado é neutra, nunca penalidade" da camada 3.
2. Categoria batendo com `icp_category` → `base=0.7`; não batendo →
   `base=0.2` (score baixo, mas NUNCA descarte — só `business_status` tem
   a garantia "ponto final"; categoria vem de config e pode ter falso
   negativo por má categorização no Google, então descartar
   deterministicamente aqui seria regra de negócio embutida no código).
   Sem `icp_category` configurado ainda, categoria é neutra (`base=0.5`).
3. `rating`/`review_count` — proxy fraco de porte, NUNCA decide sozinho:
   o gap entre 0.7 (bate) e 0.2 (não bate) é maior que o bônus máximo
   combinado dos dois (0.15+0.15=0.30), então nenhuma combinação de
   reviews faz um "não bate" (0.2+0.30=0.50) alcançar um "bate" (0.7) —
   a hierarquia nunca se inverte. Ausência de rating/reviews é NEUTRA
   (bônus 0.0, nunca penalidade) — negócio novo/pouco avaliado no Google
   não é sinal de porte pequeno, é ausência de dado.
"""
from __future__ import annotations

from providers.google_maps import PlaceSignal

_CATEGORY_MATCH_BASE = 0.7
_CATEGORY_MISMATCH_BASE = 0.2
_CATEGORY_NEUTRAL_BASE = 0.5  # sem icp_category configurado ainda
_RATING_BONUS_MAX = 0.15
_REVIEW_BONUS_MAX = 0.15
_REVIEW_COUNT_CAP = 50  # evita que porte gigante infle o score além do que a camada fraca deveria valer


def category_matches(place_category: str | None, icp_category: str | None) -> bool:
    if not place_category or not icp_category:
        return False
    return place_category.strip().lower() == icp_category.strip().lower()


def score_place_signal(signal: PlaceSignal, icp_category: str | None) -> float | None:
    """`None` = descarte determinístico (lugar fechado). `float` 0.0-1.0
    = score normal, mesma escala de `Opportunity.opportunity_score` já
    usada no resto do sistema — quem decide o corte pra virar oportunidade
    de verdade é `anti-spam-promotion-gate` (módulo 5), nunca esta função."""
    if signal.business_status not in (None, "OPERATIONAL", "BUSINESS_STATUS_UNSPECIFIED"):
        return None

    if icp_category is None:
        base = _CATEGORY_NEUTRAL_BASE
    elif category_matches(signal.category, icp_category):
        base = _CATEGORY_MATCH_BASE
    else:
        base = _CATEGORY_MISMATCH_BASE

    rating_bonus = 0.0 if signal.rating is None else max(0.0, min(1.0, (signal.rating - 1) / 4)) * _RATING_BONUS_MAX
    # review_count nunca é None (PlaceSignal usa 0 como default do provider,
    # ver providers/google_maps.py) — 0 já produz bônus 0.0 naturalmente,
    # sem precisar de checagem extra.
    review_bonus = min(signal.review_count, _REVIEW_COUNT_CAP) / _REVIEW_COUNT_CAP * _REVIEW_BONUS_MAX

    return min(1.0, base + rating_bonus + review_bonus)
