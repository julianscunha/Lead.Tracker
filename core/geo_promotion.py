"""
Trava anti-spam de prospecção geográfica (Fase E, módulo 5
`anti-spam-promotion-gate`) — consulta ao agente Outbound Strategist
antes de implementar (cap errado aqui é o risco mais caro da fase:
gerar contato real em excesso).

Decisões (registradas por escrito, configuráveis via `.env`, nunca
hardcoded):

1. **Score mínimo de promoção = 0.75.** Acima do "bate categoria puro"
   (0.7, `core/geo_scoring.py`) — exige pelo menos um sinal extra
   (reviews/rating) além de match de categoria pra virar `Company`/
   `Opportunity` real. Abaixo disso, o sinal nunca é persistido (nem
   como `detected` órfão) — não há evidência suficiente pra existir no
   sistema (mesmo princípio de "sem oportunidade sem evidência" do
   resto do projeto).
2. **Cap de 20 promoções por rep/dia** (default configurável). Quando a
   busca gera mais elegíveis (score >= mínimo) do que a cota restante
   permite, os excedentes são **descartados desta seleção** (nunca
   promovidos por essa run) — quem decide o que promover primeiro é o
   score (maior primeiro). Isso NUNCA bloqueia a busca em si (buscar e
   pontuar é grátis, não é "contato" — bloquear a busca confundiria
   descoberta com abordagem, que o projeto já separa claramente:
   "IA/heurística nunca decide sozinha, nunca aborda automaticamente").
3. **Um contador único diário por rep**, não caps separados por lote e
   por dia — "o mais restritivo vale" nos dois, então um contador só
   (quota restante = cap - já promovido hoje) tem o mesmo efeito com
   menos estado pra sincronizar.
4. Este módulo entrega só a DECISÃO pura (quem entra na cota, quem não
   entra) — a contagem de "já promovido hoje" é responsabilidade de
   quem chama (repositório/rota), e a criação de fato de `Company`/
   `Opportunity` a partir de um sinal promovido é responsabilidade do
   módulo 6 (wizard, ainda não construído) — ele é quem decide qual rep
   está rodando a busca, informação que este módulo não tem.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from providers.google_maps import PlaceSignal

GEO_PROMOTION_MIN_SCORE_ENV_KEY = "GEO_PROMOTION_MIN_SCORE"
_DEFAULT_MIN_SCORE = 0.75
GEO_PROMOTION_DAILY_CAP_ENV_KEY = "GEO_PROMOTION_DAILY_CAP"
_DEFAULT_DAILY_CAP = 20


def parse_promotion_min_score(env: dict[str, str]) -> float:
    """Valor ausente, vazio ou inválido cai no default (0.75), nunca
    quebra a leitura da configuração — mesmo padrão de `parse_aging_sla_days`."""
    raw = env.get(GEO_PROMOTION_MIN_SCORE_ENV_KEY, "")
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_MIN_SCORE
    return value if 0.0 <= value <= 1.0 else _DEFAULT_MIN_SCORE


def parse_promotion_daily_cap(env: dict[str, str]) -> int:
    raw = env.get(GEO_PROMOTION_DAILY_CAP_ENV_KEY, "")
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_DAILY_CAP
    return value if value > 0 else _DEFAULT_DAILY_CAP


@dataclass
class PromotionDecision:
    """`promoted` = vira `Company`/`Opportunity` real agora (score
    suficiente e dentro da cota). `deferred` = score suficiente mas cota
    do dia já esgotada — nunca promovido por esta seleção (quem chama
    decide se tenta de novo depois; este módulo não guarda fila). `rejected`
    = score insuficiente, nunca vira registro nenhum."""
    promoted: list[PlaceSignal] = field(default_factory=list)
    deferred: list[PlaceSignal] = field(default_factory=list)
    rejected: list[PlaceSignal] = field(default_factory=list)


def select_promotions(
    scored_signals: list[tuple[PlaceSignal, float | None]],
    min_score: float, daily_cap: int, already_promoted_today: int,
) -> PromotionDecision:
    """Nunca bloqueia a busca inteira: todo sinal é classificado (mesmo
    que a decisão final seja `rejected`/`deferred`). `score=None`
    (descarte determinístico de `score_place_signal`, ex. lugar fechado)
    conta como `rejected` — mesmo efeito de "nunca vira registro", nunca
    consome cota."""
    eligible = sorted(
        [(s, sc) for s, sc in scored_signals if sc is not None and sc >= min_score],
        key=lambda pair: pair[1], reverse=True,
    )
    rejected = [s for s, sc in scored_signals if sc is None or sc < min_score]

    remaining_quota = max(0, daily_cap - already_promoted_today)
    promoted = [s for s, _ in eligible[:remaining_quota]]
    deferred = [s for s, _ in eligible[remaining_quota:]]

    return PromotionDecision(promoted=promoted, deferred=deferred, rejected=rejected)
