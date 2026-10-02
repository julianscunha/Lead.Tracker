"""
Métricas do Dashboard Executivo.

Tudo aqui é derivado dos dados recebidos — nenhum número é inventado, gráficos
são sempre derivados de dado real, IA não pode inventar métrica. "Tendência"
(série histórica) e "segmentação por região/segmento" (sem campo
correspondente em Company) ficam fora — não há dado pra sustentá-las.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from statistics import median

from core.models import Company, Opportunity, OpportunitySnapshot, OpportunityStatus
from core.opportunity_engine import is_aging_opportunity

# Doc usa 4 estágios; nosso enum tem 6. Mapeamento explícito — 'reviewed' e
# 'dismissed' não têm estágio de funil correspondente (não são progresso linear).
FUNNEL_STAGES = ["Detectadas", "Qualificadas", "Abordadas", "Em negociação"]
_FUNNEL_MAP = {
    OpportunityStatus.DETECTED: "Detectadas",
    OpportunityStatus.QUALIFIED: "Qualificadas",
    OpportunityStatus.CONTACTED: "Abordadas",
    OpportunityStatus.OPPORTUNITY: "Em negociação",
}


@dataclass
class DashboardKPIs:
    opportunities_identified: int
    customers_analyzed: int
    prospects_analyzed: int
    financial_potential_total: float
    product_opportunities: int
    service_opportunities: int
    top_vendor: str | None
    top_service: str | None
    # Fase O (R12): quantas oportunidades não têm valor típico informado (o total acima não as inclui).
    opportunities_without_value: int = 0


def compute_kpis(
    companies: list[Company],
    opportunities: list[Opportunity],
    vendor_names: dict[str, str],
    service_names: dict[str, str],
) -> DashboardKPIs:
    customers = sum(1 for c in companies if c.is_customer)
    prospects = len(companies) - customers

    financial_total = sum(o.financial_potential for o in opportunities if o.financial_potential is not None)

    product_opps = sum(1 for o in opportunities if o.product_id is not None)
    service_opps = sum(1 for o in opportunities if o.service_id is not None)

    vendor_dist = distribution_by_vendor(opportunities, vendor_names)
    top_vendor = vendor_dist[0][0] if vendor_dist else None

    service_dist = opportunities_by_service(opportunities, service_names)
    top_service = service_dist[0][0] if service_dist else None

    return DashboardKPIs(
        opportunities_identified=len(opportunities),
        customers_analyzed=customers,
        prospects_analyzed=prospects,
        financial_potential_total=financial_total,
        product_opportunities=product_opps,
        service_opportunities=service_opps,
        top_vendor=top_vendor,
        top_service=top_service,
        opportunities_without_value=sum(1 for o in opportunities if o.financial_potential is None),
    )


def distribution_by_vendor(opportunities: list[Opportunity], vendor_names: dict[str, str]) -> list[tuple[str, int]]:
    """Contagem de oportunidades por fabricante, ordenada desc. Sem vendor_id, não entra."""
    counts = Counter(vendor_names[o.vendor_id] for o in opportunities if o.vendor_id in vendor_names)
    return sorted(counts.items(), key=lambda item: item[1], reverse=True)


def financial_potential_by_vendor(opportunities: list[Opportunity], vendor_names: dict[str, str]) -> list[tuple[str, float]]:
    """Soma de potencial financeiro por fabricante. Oportunidade sem potencial (None) não soma nada — nunca vira 0 fingindo dado."""
    totals: Counter[str] = Counter()
    for o in opportunities:
        if o.vendor_id in vendor_names and o.financial_potential is not None:
            totals[vendor_names[o.vendor_id]] += o.financial_potential
    return sorted(totals.items(), key=lambda item: item[1], reverse=True)


def opportunities_by_service(opportunities: list[Opportunity], service_names: dict[str, str]) -> list[tuple[str, int]]:
    counts = Counter(service_names[o.service_id] for o in opportunities if o.service_id in service_names)
    return sorted(counts.items(), key=lambda item: item[1], reverse=True)


def customer_vs_prospect(companies: list[Company]) -> dict[str, int]:
    customers = sum(1 for c in companies if c.is_customer)
    return {"clientes": customers, "prospects": len(companies) - customers}


def funnel_counts(opportunities: list[Opportunity]) -> dict[str, int]:
    """Conta oportunidades por estágio de funil. Status sem estágio
    correspondente (reviewed, dismissed) não entram no funil."""
    counts = {stage: 0 for stage in FUNNEL_STAGES}
    for o in opportunities:
        stage = _FUNNEL_MAP.get(o.status)
        if stage:
            counts[stage] += 1
    return counts


# ── Fase D — leitura via snapshot diário (nunca tempo real das tabelas
# transacionais, decisão de arquitetura do roadmap) ──────────────────────────

# Confiança padrão pra oportunidade sem confidence_score avaliado — nem
# otimista (1.0) nem pessimista (0.0), sinalizado à parte na UI como
# "estimado" (decisão do Pipeline Analyst). Nunca silenciosamente igual a
# uma oportunidade realmente avaliada.
_DEFAULT_CONFIDENCE_WHEN_UNKNOWN = 0.5


def exclude_zombies(snapshot: list[OpportunitySnapshot]) -> list[OpportunitySnapshot]:
    """Blindagem obrigatória do roadmap: oportunidade zumbi nunca entra em
    métrica de "pipeline saudável" — quem calcula esse tipo de métrica
    filtra por aqui antes."""
    return [s for s in snapshot if not s.is_zombie]


@dataclass
class WeightedPotential:
    gross_total: float
    weighted_evaluated_total: float
    weighted_estimated_total: float


def compute_weighted_potential(snapshot: list[OpportunitySnapshot]) -> WeightedPotential:
    """Potencial bruto ao lado do ponderado, nunca substituindo (princípio
    3 do roadmap). Duas somas ponderadas, nunca uma só: `_evaluated` conta
    só oportunidade com confidence_score real; `_estimated` soma isso mais
    as sem confidence_score usando a confiança padrão — misturar as duas
    sem rótulo esconderia quanto do pipeline é estimativa (decisão do
    Pipeline Analyst)."""
    gross = 0.0
    evaluated = 0.0
    estimated_extra = 0.0
    for s in snapshot:
        if s.financial_potential is None:
            continue
        gross += s.financial_potential
        if s.confidence_score is not None:
            evaluated += s.financial_potential * s.confidence_score
        else:
            estimated_extra += s.financial_potential * _DEFAULT_CONFIDENCE_WHEN_UNKNOWN
    return WeightedPotential(
        gross_total=gross, weighted_evaluated_total=evaluated,
        weighted_estimated_total=evaluated + estimated_extra,
    )


def _potential_by(snapshot: list[OpportunitySnapshot], key: str) -> list[tuple[str, float]]:
    totals: Counter[str] = Counter()
    for s in snapshot:
        value = getattr(s, key)
        if value and s.financial_potential is not None:
            totals[value] += s.financial_potential
    return sorted(totals.items(), key=lambda item: item[1], reverse=True)


def potential_by_rep(snapshot: list[OpportunitySnapshot]) -> list[tuple[str, float]]:
    """Sempre segmentado, nunca um total misturado (blindagem do
    roadmap) — conta sem rep_id (`None`, nenhuma fonte atribuiu ainda)
    fica de fora, nunca vira uma categoria "sem rep" fingida."""
    return _potential_by(snapshot, "rep_id")


def potential_by_segment(snapshot: list[OpportunitySnapshot]) -> list[tuple[str, float]]:
    return _potential_by(snapshot, "segment")


def potential_by_source(snapshot: list[OpportunitySnapshot]) -> list[tuple[str, float]]:
    return _potential_by(snapshot, "source")


def count_zombie_opportunities(snapshot: list[OpportunitySnapshot]) -> int:
    return sum(1 for s in snapshot if s.is_zombie)


def count_aging_opportunities(snapshot: list[OpportunitySnapshot], sla_days: int, now: datetime) -> int:
    """Contagem pro card do dashboard — a lista acionável por oportunidade
    vive em `GET /opportunities` (`OpportunityOut.is_aging`), não aqui."""
    return sum(1 for s in snapshot if is_aging_opportunity(s.stage.value, s.first_detected_at, now, sla_days))


@dataclass
class RepCoverage:
    rep_id: str
    actual: float
    target: float | None
    coverage_ratio: float | None  # None = "sem meta definida" (rep sem cadastro pro período), nunca 0%/erro


def compute_rep_coverage(
    potential_by_rep_rows: list[tuple[str, float]], targets: dict[str, float],
) -> list[RepCoverage]:
    """Roadmap: "sem meta configurada, 'potencial financeiro total' é
    número sem contexto" — cobertura = pipeline atual (mesmo corte de
    `potential_by_rep`, já exclui zumbi) dividido pela meta manual do
    período. Rep sem meta cadastrada NUNCA vira meta=0 (isso inflaria um
    "déficit" fictício) — `coverage_ratio=None`, UI mostra "sem meta
    definida". União dos reps de `potential_by_rep_rows` e `targets`: um
    rep com meta cadastrada mas pipeline zerado no período também aparece
    (0% de cobertura é dado real, bem diferente de "sem meta")."""
    actuals = dict(potential_by_rep_rows)
    rep_ids = sorted(set(actuals) | set(targets))
    result = []
    for rep_id in rep_ids:
        actual = actuals.get(rep_id, 0.0)
        target = targets.get(rep_id)
        ratio = (actual / target) if target else None
        result.append(RepCoverage(rep_id=rep_id, actual=actual, target=target, coverage_ratio=ratio))
    return result


# Sequência de progresso — "dismissed" fica fora (é saída do funil, não um
# estágio a mais). Nomeação em inglês (chaves internas) — rótulo em
# português vem do frontend, mesmo padrão de FUNNEL_STAGES.
FUNNEL_REACH_ORDER = ["detected", "qualified", "reviewed", "contacted", "opportunity"]


@dataclass
class FunnelReachStage:
    stage: str
    reach_count: int
    reach_ratio_from_previous: float | None  # None no primeiro estágio (sem "anterior")


def funnel_reach(snapshot: list[OpportunitySnapshot]) -> list[FunnelReachStage]:
    """"Alcance do funil hoje" — NUNCA chamar de "taxa de conversão"
    (decisão do Pipeline Analyst): sem histórico completo de por quais
    estágios cada oportunidade já passou (`OpportunityStatusChange` só
    existe pra transições manuais, a maioria das oportunidades ainda não
    tem nenhuma), não dá pra calcular conversão de coorte de verdade. Isso
    aqui é um corte transversal do snapshot mais recente: `reach_count[i]`
    = quantas oportunidades estão HOJE no estágio `i` ou além.
    `reach_ratio_from_previous[i]` = `reach_count[i] / reach_count[i-1]`.
    Mistura oportunidades de idades bem diferentes — é a limitação
    conhecida, não escondida (rótulo da UI precisa deixar isso explícito:
    "visão atual", nunca "conversão histórica")."""
    stage_index = {stage: i for i, stage in enumerate(FUNNEL_REACH_ORDER)}
    reach = [0] * len(FUNNEL_REACH_ORDER)
    for s in snapshot:
        idx = stage_index.get(s.stage.value)
        if idx is None:
            continue  # dismissed (ou qualquer status fora da sequência) não entra
        for i in range(idx + 1):
            reach[i] += 1

    result = []
    previous = None
    for i, stage in enumerate(FUNNEL_REACH_ORDER):
        ratio = (reach[i] / previous) if previous else None
        result.append(FunnelReachStage(stage=stage, reach_count=reach[i], reach_ratio_from_previous=ratio))
        previous = reach[i]
    return result


NO_CATEGORY_LABEL = "Sem categoria"
MIN_ELIGIBLE_REPS_FOR_REFERENCE = 3


@dataclass
class RepCategoryReach:
    rep_id: str
    category: str
    n: int
    insufficient: bool  # n < min_sample — razões ficam None, contagens brutas continuam (tooltip)
    reach_counts: dict[str, int]
    reach_ratios: dict[str, float | None]  # reach_counts[s] / n; None quando insufficient, nunca 0%
    opportunity_ids: list[str]  # evidência por trás da célula: a UI lista esses deals ao clicar


@dataclass
class RepCategoryReachResult:
    cells: list[RepCategoryReach]
    # categoria -> estágio -> mediana das razões dos reps elegíveis; None sem ≥3 elegíveis
    team_median: dict[str, dict[str, float | None]]
    unassigned_count: int
    min_sample: int


def rep_category_reach(
    snapshot: list[OpportunitySnapshot], category_by_opportunity: dict[str, str | None], min_sample: int,
) -> RepCategoryReachResult:
    """Alcance acumulado por (rep, categoria) — mesma leitura "visão atual"
    de `funnel_reach` (mesmo corte do snapshot, `dismissed` fora): NUNCA é
    conversão histórica. Par com `n < min_sample` é "dado insuficiente"
    (razões `None`), nunca 0%. Sem categoria conhecida cai no balde neutro
    `NO_CATEGORY_LABEL` (nada de categoria inventada) e não recebe referência
    de time (produtos sem relação entre si não têm mediana com sentido).
    Referência = MEDIANA entre reps elegíveis da categoria, só com
    `MIN_ELIGIBLE_REPS_FOR_REFERENCE`+ deles. Oportunidade sem rep nunca vira
    rep fictício: só entra em `unassigned_count`. Sem ranking: saída em ordem
    alfabética (rep, categoria)."""
    stage_index = {stage: i for i, stage in enumerate(FUNNEL_REACH_ORDER)}
    n_by_pair: dict[tuple[str, str], int] = {}
    reach_by_pair: dict[tuple[str, str], list[int]] = {}
    ids_by_pair: dict[tuple[str, str], list[str]] = {}
    unassigned = 0
    for s in snapshot:
        idx = stage_index.get(s.stage.value)
        if idx is None:
            continue
        if not s.rep_id:
            unassigned += 1
            continue
        pair = (s.rep_id, category_by_opportunity.get(s.opportunity_id) or NO_CATEGORY_LABEL)
        n_by_pair[pair] = n_by_pair.get(pair, 0) + 1
        ids_by_pair.setdefault(pair, []).append(s.opportunity_id)
        reach = reach_by_pair.setdefault(pair, [0] * len(FUNNEL_REACH_ORDER))
        for i in range(idx + 1):
            reach[i] += 1

    cells = []
    for pair in sorted(n_by_pair):
        n = n_by_pair[pair]
        insufficient = n < min_sample
        counts = dict(zip(FUNNEL_REACH_ORDER, reach_by_pair[pair]))
        ratios = {stage: (None if insufficient else count / n) for stage, count in counts.items()}
        cells.append(RepCategoryReach(
            rep_id=pair[0], category=pair[1], n=n, insufficient=insufficient, reach_counts=counts, reach_ratios=ratios,
            opportunity_ids=sorted(ids_by_pair[pair]),
        ))

    team_median: dict[str, dict[str, float | None]] = {}
    for category in sorted({c.category for c in cells}):
        eligible = [c for c in cells if c.category == category and not c.insufficient]
        has_reference = category != NO_CATEGORY_LABEL and len(eligible) >= MIN_ELIGIBLE_REPS_FOR_REFERENCE
        team_median[category] = {
            stage: (median(c.reach_ratios[stage] for c in eligible) if has_reference else None)
            for stage in FUNNEL_REACH_ORDER
        }
    return RepCategoryReachResult(cells=cells, team_median=team_median, unassigned_count=unassigned, min_sample=min_sample)
