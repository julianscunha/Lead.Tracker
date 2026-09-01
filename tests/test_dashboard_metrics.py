"""Smoke tests das métricas do dashboard."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.dashboard_metrics import (
    compute_kpis, customer_vs_prospect, distribution_by_vendor,
    financial_potential_by_vendor, funnel_counts, opportunities_by_service,
)
from core.models import Company, Opportunity, OpportunityStatus

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


if __name__ == "__main__":
    test_kpis_never_invent_financial_potential_for_none()
    test_distribution_by_vendor_ignores_unknown_vendor_id()
    test_financial_potential_by_vendor_skips_none_never_treats_as_zero()
    test_opportunities_by_service()
    test_customer_vs_prospect()
    test_funnel_counts_maps_status_and_excludes_reviewed_and_dismissed()
    print("OK — todos os testes de métricas do dashboard passaram")
