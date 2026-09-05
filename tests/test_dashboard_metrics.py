"""Smoke tests das métricas do dashboard."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date

from core.dashboard_metrics import (
    compute_kpis, compute_weighted_potential, count_zombie_opportunities, customer_vs_prospect,
    distribution_by_vendor, exclude_zombies, financial_potential_by_vendor, funnel_counts, funnel_reach,
    opportunities_by_service, potential_by_rep, potential_by_segment, potential_by_source,
)
from core.models import Company, Opportunity, OpportunitySnapshot, OpportunityStatus

VENDOR_NAMES = {"v1": "Veeam", "v2": "VMware"}
SERVICE_NAMES = {"s1": "FinOps", "s2": "Assessment de DR"}


def _opp(**kwargs) -> Opportunity:
    defaults = dict(company_id="c1", type="cross-sell")
    defaults.update(kwargs)
    return Opportunity(**defaults)


def test_kpis_never_invent_financial_potential_for_none():
    companies = [Company(name="A", is_customer=True), Company(name="B", is_customer=False)]
    opps = [_opp(financial_potential=1000.0), _opp(financial_potential=None)]

    kpis = compute_kpis(companies, opps, VENDOR_NAMES, SERVICE_NAMES)

    assert kpis.financial_potential_total == 1000.0  # None não vira 0 somado, só é ignorado
    assert kpis.customers_analyzed == 1
    assert kpis.prospects_analyzed == 1
    assert kpis.opportunities_identified == 2


def test_distribution_by_vendor_ignores_unknown_vendor_id():
    opps = [_opp(vendor_id="v1"), _opp(vendor_id="v1"), _opp(vendor_id="v2"), _opp(vendor_id="v_desconhecido")]

    result = distribution_by_vendor(opps, VENDOR_NAMES)

    assert result == [("Veeam", 2), ("VMware", 1)]


def test_financial_potential_by_vendor_skips_none_never_treats_as_zero():
    opps = [_opp(vendor_id="v1", financial_potential=500.0), _opp(vendor_id="v1", financial_potential=None)]

    result = financial_potential_by_vendor(opps, VENDOR_NAMES)

    assert result == [("Veeam", 500.0)]


def test_opportunities_by_service():
    opps = [_opp(service_id="s1"), _opp(service_id="s2"), _opp(service_id="s1")]

    result = opportunities_by_service(opps, SERVICE_NAMES)

    assert result == [("FinOps", 2), ("Assessment de DR", 1)]


def test_customer_vs_prospect():
    companies = [Company(name="A", is_customer=True), Company(name="B", is_customer=True), Company(name="C", is_customer=False)]

    result = customer_vs_prospect(companies)

    assert result == {"clientes": 2, "prospects": 1}


def test_funnel_counts_maps_status_and_excludes_reviewed_and_dismissed():
    opps = [
        _opp(status=OpportunityStatus.DETECTED),
        _opp(status=OpportunityStatus.QUALIFIED),
        _opp(status=OpportunityStatus.CONTACTED),
        _opp(status=OpportunityStatus.OPPORTUNITY),
        _opp(status=OpportunityStatus.REVIEWED),
        _opp(status=OpportunityStatus.DISMISSED),
    ]

    result = funnel_counts(opps)

    assert result == {"Detectadas": 1, "Qualificadas": 1, "Abordadas": 1, "Em negociação": 1}


def _snap(**kwargs) -> OpportunitySnapshot:
    defaults = dict(opportunity_id="o1", snapshot_date=date(2026, 9, 5), stage=OpportunityStatus.DETECTED)
    defaults.update(kwargs)
    return OpportunitySnapshot(**defaults)


def test_exclude_zombies_filters_only_flagged_rows():
    snapshot = [_snap(opportunity_id="o1", is_zombie=True), _snap(opportunity_id="o2", is_zombie=False)]
    result = exclude_zombies(snapshot)
    assert [s.opportunity_id for s in result] == ["o2"]


def test_compute_weighted_potential_separates_evaluated_from_estimated():
    snapshot = [
        _snap(financial_potential=1000.0, confidence_score=0.8),  # avaliada
        _snap(financial_potential=2000.0, confidence_score=None),  # sem confidence -> estimada (0.5)
        _snap(financial_potential=None, confidence_score=0.9),  # sem potencial, nunca soma nada
    ]

    result = compute_weighted_potential(snapshot)

    assert result.gross_total == 3000.0
    assert result.weighted_evaluated_total == 800.0  # 1000*0.8
    assert result.weighted_estimated_total == 800.0 + 1000.0  # + 2000*0.5


def test_potential_by_rep_segment_source_always_pre_segmented_and_skips_missing_key():
    snapshot = [
        _snap(rep_id="rep-1", segment="enterprise", source="salesforce", financial_potential=1000.0),
        _snap(rep_id="rep-2", segment="enterprise", source="manual", financial_potential=500.0),
        _snap(rep_id=None, segment=None, source=None, financial_potential=999.0),  # sem atribuição, fora de qualquer corte
    ]

    assert potential_by_rep(snapshot) == [("rep-1", 1000.0), ("rep-2", 500.0)]
    assert potential_by_segment(snapshot) == [("enterprise", 1500.0)]
    assert set(potential_by_source(snapshot)) == {("salesforce", 1000.0), ("manual", 500.0)}


def test_count_zombie_opportunities():
    snapshot = [_snap(is_zombie=True), _snap(is_zombie=True), _snap(is_zombie=False)]
    assert count_zombie_opportunities(snapshot) == 2


def test_funnel_reach_is_cumulative_and_excludes_dismissed():
    snapshot = [
        _snap(opportunity_id="o1", stage=OpportunityStatus.DETECTED),
        _snap(opportunity_id="o2", stage=OpportunityStatus.QUALIFIED),
        _snap(opportunity_id="o3", stage=OpportunityStatus.CONTACTED),
        _snap(opportunity_id="o4", stage=OpportunityStatus.DISMISSED),  # fora da sequência de progresso
    ]

    result = {r.stage: r.reach_count for r in funnel_reach(snapshot)}

    # 3 oportunidades reais no funil (o4 é dismissed, fora); alcance cumulativo:
    # detected: todas as 3 chegaram lá (o1 está lá, o2/o3 já passaram)
    assert result == {"detected": 3, "qualified": 2, "reviewed": 1, "contacted": 1, "opportunity": 0}


def test_funnel_reach_all_opportunities_in_last_stage_stays_non_increasing():
    """Caso-limite verificado na revisão de código: se TODAS as
    oportunidades já chegaram no último estágio, o alcance cumulativo tem
    que ficar igual em toda a sequência (nunca crescente ao longo do
    funil), com ratio 1.0 em cada etapa."""
    snapshot = [_snap(opportunity_id=f"o{i}", stage=OpportunityStatus.OPPORTUNITY) for i in range(3)]

    result = funnel_reach(snapshot)

    assert [r.reach_count for r in result] == [3, 3, 3, 3, 3]
    assert result[0].reach_ratio_from_previous is None
    assert all(r.reach_ratio_from_previous == 1.0 for r in result[1:])


def test_funnel_reach_first_stage_has_no_ratio_and_zero_reach_never_divides():
    result = funnel_reach([])
    assert result[0].reach_ratio_from_previous is None
    assert all(r.reach_ratio_from_previous is None for r in result)  # tudo zero, nunca ZeroDivisionError


if __name__ == "__main__":
    test_kpis_never_invent_financial_potential_for_none()
    test_distribution_by_vendor_ignores_unknown_vendor_id()
    test_financial_potential_by_vendor_skips_none_never_treats_as_zero()
    test_opportunities_by_service()
    test_customer_vs_prospect()
    test_funnel_counts_maps_status_and_excludes_reviewed_and_dismissed()
    test_exclude_zombies_filters_only_flagged_rows()
    test_compute_weighted_potential_separates_evaluated_from_estimated()
    test_potential_by_rep_segment_source_always_pre_segmented_and_skips_missing_key()
    test_count_zombie_opportunities()
    test_funnel_reach_is_cumulative_and_excludes_dismissed()
    test_funnel_reach_all_opportunities_in_last_stage_stays_non_increasing()
    test_funnel_reach_first_stage_has_no_ratio_and_zero_reach_never_divides()
    print("OK — todos os testes de métricas do dashboard passaram")
