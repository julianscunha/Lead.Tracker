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

from core.models import Company, Opportunity, OpportunityStatus

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
