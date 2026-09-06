"""
Derivação automática de critério de ICP (Fase E, módulo 3
`icp-auto-derivation`) — consulta ao agente Growth Hacker antes de
implementar (decisão de negócio, não técnica):

1. "Cliente satisfeito" = `Company.is_customer=True` com pelo menos uma
   `Opportunity.opportunity_score >= 0.7` (threshold fixo — com poucas
   oportunidades no início de uso, estatística sobre amostra pequena
   (top-N%, média±desvio) é ruído; fixo é previsível e auditável).
2. Amostra mínima de 5 clientes satisfeitos pra `confidence="high"` —
   abaixo disso, a sugestão ainda é calculada e devolvida (nunca
   escondida), só marcada `confidence="low"`. Decidir usar ou não já é
   do usuário no wizard (módulo 6, ainda não construído).
3. Moda sempre, nunca recusa sugerir por falta de maioria clara — a
   proporção da moda (`*_share`) acompanha a sugestão pra UI mostrar o
   contexto quando a moda for fraca (ex. 35% de representação).

Achado da revisão de código: o campo derivado se chamava `place_category`
(mesmo nome de `ICPProfile.place_category`), mas são taxonomias
incompatíveis — `ICPProfile.place_category` é um `type` da Google Places
API (ex. "car_dealer"), enquanto o que dá pra derivar aqui é a moda de
`Company.industry` (vertical de negócio livre, ex. "Varejo"). Nomes
iguais sugeririam ao wizard (módulo 6) que dá pra jogar a sugestão direto
em `ICPProfile.place_category`, quebrando `discover()` silenciosamente
(a Places API receberia "Varejo" como `includedTypes`, um tipo
inexistente). Renomeado pra `industry_hint` — o wizard decide como (ou
se) traduzir isso pra uma categoria real do Places, nunca automático.
4. `company_size_hint` deriva de `Company.segment` (já é string livre
   existente), não de `Company.employee_count` (dado parcial, só
   populado por Salesforce desde a Fase A — usar hoje enviesaria a
   amostra pra quem só tem Salesforce habilitado).

Nunca decide sozinho, nunca auto-aplica: só calcula e devolve a
sugestão, sempre revisada/confirmada pelo usuário no wizard antes de
qualquer uso real (mesmo princípio de "IA/heurística nunca decide
sozinha" do resto do projeto).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from core.models import Company, Opportunity

_SATISFIED_SCORE_THRESHOLD = 0.7
_MIN_SAMPLE_FOR_HIGH_CONFIDENCE = 5


@dataclass
class ICPSuggestion:
    industry_hint: str | None
    industry_hint_share: float | None
    company_size_hint: str | None
    company_size_hint_share: float | None
    sample_size: int
    confidence: str  # "low" | "high"


def _mode_with_share(values: list[str]) -> tuple[str | None, float | None]:
    if not values:
        return None, None
    counts = Counter(values)
    value, count = counts.most_common(1)[0]
    return value, count / len(values)


def derive_icp_suggestion(companies: list[Company], opportunities: list[Opportunity]) -> ICPSuggestion | None:
    """`None` quando não há nenhum cliente satisfeito ainda — não é
    "baixa confiança", é "nada pra derivar" (distinção deliberada:
    confidence="low" sempre carrega uma sugestão real, ainda que fraca)."""
    scores_by_company: dict[str, float] = {}
    for opp in opportunities:
        if opp.opportunity_score is None:
            continue
        current = scores_by_company.get(opp.company_id, 0.0)
        scores_by_company[opp.company_id] = max(current, opp.opportunity_score)

    satisfied = [
        c for c in companies
        if c.is_customer and scores_by_company.get(c.id, 0.0) >= _SATISFIED_SCORE_THRESHOLD
    ]
    if not satisfied:
        return None

    industries = [c.industry for c in satisfied if c.industry]
    segments = [c.segment for c in satisfied if c.segment]
    industry_hint, industry_hint_share = _mode_with_share(industries)
    company_size_hint, company_size_hint_share = _mode_with_share(segments)

    return ICPSuggestion(
        industry_hint=industry_hint, industry_hint_share=industry_hint_share,
        company_size_hint=company_size_hint, company_size_hint_share=company_size_hint_share,
        sample_size=len(satisfied),
        confidence="high" if len(satisfied) >= _MIN_SAMPLE_FOR_HIGH_CONFIDENCE else "low",
    )
