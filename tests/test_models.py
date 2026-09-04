"""Smoke tests dos modelos de domínio."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import (
    Company, CompanySignal, ContextNote, Product, ProductRelation, Service, SourceRef, Vendor,
    Opportunity, OpportunityStatus, OpportunityStatusChange, Portfolio,
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


def test_company_fase_b_fields_default_to_none_or_empty():
    c = Company(name="Empresa Fictícia")
    assert c.rep_id is None
    assert c.segment is None
    assert c.region is None
    assert c.trigger_event is None
    assert c.attempted_solutions == []
    assert c.strategic_context is None


def test_context_note_requires_source():
    note = ContextNote(text="Renovação de contrato em 30 dias", source=SourceRef(type="salesforce"))
    assert note.text
    assert note.source.type == "salesforce"
    assert note.observed_at is not None


def test_contact_impacted_area_defaults_to_none():
    from core.models import Contact
    contact = Contact(company_id="c1", name="Fulano")
    assert contact.impacted_area is None


def test_product_relation_default_type_is_complementary():
    rel = ProductRelation(service_id="s1")
    assert rel.relation_type == "complementary"


def test_product_and_service_have_optional_category():
    v = Vendor(name="Veeam")
    p = Product(vendor_id=v.id, name="VBR", category="backup")
    s = Service(name="Assessment de DR", category="dr")
    assert p.category == "backup"
    assert s.category == "dr"
    assert p.related_services == []


def test_company_signal_requires_source_and_defaults_open():
    signal = CompanySignal(
        company_id="c1", signal_type="renewal_upcoming",
        source=SourceRef(type="salesforce"),
    )
    assert signal.status == "open"
    assert signal.confidence == 1.0


def test_opportunity_status_change_captures_status_and_timestamp():
    change = OpportunityStatusChange(opportunity_id="o1", status=OpportunityStatus.QUALIFIED)
    assert change.status == OpportunityStatus.QUALIFIED
    assert change.entered_at is not None


if __name__ == "__main__":
    test_company_defaults_and_sources()
    test_source_confidence_bounds()
    test_product_belongs_to_vendor()
    test_opportunity_default_status_is_detected()
    test_opportunity_status_flow_values()
    test_portfolio_scoped_to_company()
    test_company_fase_b_fields_default_to_none_or_empty()
    test_context_note_requires_source()
    test_contact_impacted_area_defaults_to_none()
    test_product_relation_default_type_is_complementary()
    test_product_and_service_have_optional_category()
    test_company_signal_requires_source_and_defaults_open()
    test_opportunity_status_change_captures_status_and_timestamp()
    print("OK — todos os testes de modelos passaram")
