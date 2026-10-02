"""Smoke tests das métricas do dashboard."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date, datetime, timedelta, timezone

from core.dashboard_metrics import (
    RepCoverage, compute_kpis, compute_rep_coverage, compute_weighted_potential, count_aging_opportunities,
    count_zombie_opportunities, customer_vs_prospect, distribution_by_vendor, exclude_zombies,
    financial_potential_by_vendor, funnel_counts, funnel_reach, opportunities_by_service, potential_by_rep,
    potential_by_segment, potential_by_source, NO_CATEGORY_LABEL, rep_category_reach,
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
    defaults = dict(
        opportunity_id="o1", snapshot_date=date(2026, 9, 5), stage=OpportunityStatus.DETECTED,
        first_detected_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
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


def test_count_aging_opportunities_only_counts_detected_beyond_sla():
    now = datetime(2026, 9, 5, tzinfo=timezone.utc)
    snapshot = [
        _snap(opportunity_id="o1", stage=OpportunityStatus.DETECTED, first_detected_at=now - timedelta(days=10)),
        _snap(opportunity_id="o2", stage=OpportunityStatus.DETECTED, first_detected_at=now - timedelta(days=1)),
        _snap(opportunity_id="o3", stage=OpportunityStatus.QUALIFIED, first_detected_at=now - timedelta(days=10)),
    ]

    assert count_aging_opportunities(snapshot, sla_days=7, now=now) == 1  # só o1


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


def test_compute_rep_coverage_rep_without_target_is_none_never_zero_percent():
    result = compute_rep_coverage([("rep-1", 1000.0)], targets={})
    assert result == [RepCoverage(rep_id="rep-1", actual=1000.0, target=None, coverage_ratio=None)]


def test_compute_rep_coverage_computes_ratio_when_target_present():
    result = compute_rep_coverage([("rep-1", 5000.0)], targets={"rep-1": 10000.0})
    assert result[0].target == 10000.0
    assert result[0].coverage_ratio == 0.5


def test_compute_rep_coverage_includes_rep_with_target_but_zero_pipeline():
    """Rep com meta cadastrada mas nenhuma oportunidade no corte atual —
    0% de cobertura é dado real, bem diferente de "sem meta definida"."""
    result = compute_rep_coverage([], targets={"rep-2": 8000.0})
    assert result[0].rep_id == "rep-2"
    assert result[0].actual == 0.0
    assert result[0].target == 8000.0
    assert result[0].coverage_ratio == 0.0


def test_compute_rep_coverage_never_divides_by_zero_target():
    result = compute_rep_coverage([("rep-1", 1000.0)], targets={"rep-1": 0.0})
    assert result[0].target == 0.0
    assert result[0].coverage_ratio is None


def _rep_snaps(rep_id: str, stages: list[OpportunityStatus], prefix: str | None = None) -> list[OpportunitySnapshot]:
    prefix = prefix or rep_id
    return [_snap(opportunity_id=f"{prefix}-{i}", rep_id=rep_id, stage=st) for i, st in enumerate(stages)]


def _cats(snapshot: list[OpportunitySnapshot], category: str | None) -> dict[str, str | None]:
    return {s.opportunity_id: category for s in snapshot}


S = OpportunityStatus


def test_rep_category_reach_is_cumulative_per_pair_and_excludes_dismissed():
    snap = _rep_snaps("rep-1", [S.DETECTED, S.QUALIFIED, S.CONTACTED, S.CONTACTED, S.OPPORTUNITY, S.DISMISSED])

    result = rep_category_reach(snap, _cats(snap, "Backup"), min_sample=5)

    (cell,) = result.cells
    assert (cell.rep_id, cell.category, cell.n, cell.insufficient) == ("rep-1", "Backup", 5, False)  # dismissed fora
    assert cell.reach_counts == {"detected": 5, "qualified": 4, "reviewed": 3, "contacted": 3, "opportunity": 1}
    assert cell.reach_ratios["contacted"] == 3 / 5


def test_rep_category_reach_below_min_sample_is_insufficient_never_zero_percent():
    snap = _rep_snaps("rep-1", [S.DETECTED] * 4)  # nenhum passou de detected: 0 real, mas n=4 < 5

    (cell,) = rep_category_reach(snap, _cats(snap, "Backup"), min_sample=5).cells

    assert cell.insufficient is True and cell.n == 4
    assert all(r is None for r in cell.reach_ratios.values())  # nunca 0.0 nem número
    assert cell.reach_counts["detected"] == 4  # contagem bruta continua pro tooltip


def test_rep_category_reach_boundary_n_equal_min_sample_is_sufficient_and_min_sample_is_configurable():
    snap = _rep_snaps("rep-1", [S.DETECTED] * 5)
    cats = _cats(snap, "Backup")

    assert rep_category_reach(snap, cats, min_sample=5).cells[0].insufficient is False
    assert rep_category_reach(snap, cats, min_sample=6).cells[0].insufficient is True
    assert rep_category_reach(snap, cats, min_sample=2).min_sample == 2


def test_rep_category_reach_real_zero_percent_is_distinct_from_insufficient():
    snap = _rep_snaps("rep-1", [S.DETECTED] * 5)

    (cell,) = rep_category_reach(snap, _cats(snap, "Backup"), min_sample=5).cells

    assert cell.insufficient is False
    assert cell.reach_ratios["qualified"] == 0.0  # 0% real, com amostra suficiente


def test_rep_category_reach_unknown_category_goes_to_neutral_bucket_without_team_reference():
    snaps = []
    for rep in ("rep-1", "rep-2", "rep-3"):
        snaps += _rep_snaps(rep, [S.QUALIFIED] * 5)
    cats = {s.opportunity_id: None for s in snaps}

    result = rep_category_reach(snaps, cats, min_sample=5)

    assert {c.category for c in result.cells} == {NO_CATEGORY_LABEL}
    assert all(v is None for v in result.team_median[NO_CATEGORY_LABEL].values())  # 3 elegíveis, mas sem referência


def test_rep_category_reach_empty_string_category_is_treated_as_unknown():
    snap = _rep_snaps("rep-1", [S.DETECTED] * 5)

    (cell,) = rep_category_reach(snap, _cats(snap, ""), min_sample=5).cells

    assert cell.category == NO_CATEGORY_LABEL


def test_rep_category_reach_team_median_needs_three_eligible_reps():
    snaps = _rep_snaps("rep-1", [S.CONTACTED] * 5) + _rep_snaps("rep-2", [S.DETECTED] * 5)
    cats = _cats(snaps, "Backup")
    assert rep_category_reach(snaps, cats, min_sample=5).team_median["Backup"]["contacted"] is None  # só 2 elegíveis

    snaps += _rep_snaps("rep-3", [S.CONTACTED] * 2 + [S.DETECTED] * 3)
    cats = _cats(snaps, "Backup")
    median_contacted = rep_category_reach(snaps, cats, min_sample=5).team_median["Backup"]["contacted"]
    assert median_contacted == 0.4  # razões 1.0, 0.0, 0.4 -> mediana 0.4


def test_rep_category_reach_insufficient_reps_do_not_count_toward_reference():
    snaps = (
        _rep_snaps("rep-1", [S.CONTACTED] * 5) + _rep_snaps("rep-2", [S.CONTACTED] * 5)
        + _rep_snaps("rep-3", [S.DETECTED] * 2)  # insuficiente: fora da mediana e do mínimo de 3
    )

    result = rep_category_reach(snaps, _cats(snaps, "Backup"), min_sample=5)

    assert result.team_median["Backup"]["contacted"] is None


def test_rep_category_reach_unassigned_rep_is_counted_apart_never_a_fake_rep():
    snaps = _rep_snaps("rep-1", [S.DETECTED] * 5) + [
        _snap(opportunity_id="x1", rep_id=None, stage=S.QUALIFIED),
        _snap(opportunity_id="x2", rep_id=None, stage=S.DISMISSED),  # dismissed sem rep nem conta
    ]

    result = rep_category_reach(snaps, _cats(snaps, "Backup"), min_sample=5)

    assert result.unassigned_count == 1
    assert {c.rep_id for c in result.cells} == {"rep-1"}


def test_rep_category_reach_pairs_are_separated_and_ordered_alphabetically_not_by_performance():
    snaps = _rep_snaps("rep-b", [S.OPPORTUNITY] * 5, prefix="b1") + _rep_snaps("rep-a", [S.DETECTED] * 5, prefix="a1")
    cats = {s.opportunity_id: "Backup" for s in snaps}
    snaps2 = _rep_snaps("rep-a", [S.DETECTED] * 5, prefix="a2")
    cats.update({s.opportunity_id: "Cloud" for s in snaps2})

    result = rep_category_reach(snaps + snaps2, cats, min_sample=5)

    assert [(c.rep_id, c.category) for c in result.cells] == [("rep-a", "Backup"), ("rep-a", "Cloud"), ("rep-b", "Backup")]


def test_rep_category_reach_empty_snapshot_is_empty_result():
    result = rep_category_reach([], {}, min_sample=5)
    assert result.cells == [] and result.team_median == {} and result.unassigned_count == 0


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
    test_count_aging_opportunities_only_counts_detected_beyond_sla()
    test_funnel_reach_is_cumulative_and_excludes_dismissed()
    test_funnel_reach_all_opportunities_in_last_stage_stays_non_increasing()
    test_funnel_reach_first_stage_has_no_ratio_and_zero_reach_never_divides()
    test_compute_rep_coverage_rep_without_target_is_none_never_zero_percent()
    test_compute_rep_coverage_computes_ratio_when_target_present()
    test_compute_rep_coverage_includes_rep_with_target_but_zero_pipeline()
    test_compute_rep_coverage_never_divides_by_zero_target()
    print("OK — todos os testes de métricas do dashboard passaram")
