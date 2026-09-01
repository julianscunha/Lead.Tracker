"""Smoke tests dos modelos de domínio."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import (
    Company, SourceRef, Vendor, Product, Service,
    Opportunity, OpportunityStatus, Portfolio,
)


def test_company_defaults_and_sources():
    c = Company(name="Empresa Fictícia", sources=[SourceRef(type="salesforce", confidence=1.0)])
    assert c.id
    assert c.is_customer is False
    assert c.sources[0].type == "salesforce"


def test_source_confidence_bounds():
    try:
        SourceRef(type="manual", confidence=1.5)
        assert False, "deveria rejeitar confidence > 1.0"
    except Exception:
        pass


def test_product_belongs_to_vendor():
    v = Vendor(name="Veeam")
    p = Product(vendor_id=v.id, name="VBR")
    assert p.vendor_id == v.id


def test_opportunity_default_status_is_detected():
    o = Opportunity(company_id="c1", type="cross-sell")
    assert o.status == OpportunityStatus.DETECTED


def test_opportunity_status_flow_values():
    expected = ["detected", "qualified", "reviewed", "contacted", "opportunity", "dismissed"]
    assert [s.value for s in OpportunityStatus] == expected


def test_portfolio_scoped_to_company():
    pf = Portfolio(company_id="c1", vendor_ids=["v1"], product_ids=["p1"])
    assert pf.company_id == "c1"
    assert pf.vendor_ids == ["v1"]


if __name__ == "__main__":
    test_company_defaults_and_sources()
    test_source_confidence_bounds()
    test_product_belongs_to_vendor()
    test_opportunity_default_status_is_detected()
    test_opportunity_status_flow_values()
    test_portfolio_scoped_to_company()
    print("OK — todos os testes de modelos passaram")
