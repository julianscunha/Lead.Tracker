"""Smoke tests dos modelos de domínio."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import (
    Address, Company, CompanySignal, ContextNote, CorrelationRule, Product, ProductRelation, RuleError,
    Service, SourceRef, Vendor, Opportunity, OpportunityStatus, OpportunityStatusChange, Portfolio,
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


def test_company_account_standard_fields_default_to_none():
    c = Company(name="Empresa Fictícia")
    assert c.industry is None
    assert c.annual_revenue is None
    assert c.employee_count is None
    assert c.address is None


def test_address_accepts_all_optional_fields():
    addr = Address(city="São Paulo", state="SP", postal_code="01310-100", country="Brasil")
    assert addr.city == "São Paulo"
    c = Company(name="Empresa Fictícia", industry="Varejo", annual_revenue=1_000_000.0, employee_count=250, address=addr)
    assert c.industry == "Varejo"
    assert c.address.country == "Brasil"


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


# ── CorrelationRule (Fase C) ──────────────────────────────────────────────────

def test_correlation_rule_accepts_single_mechanism():
    CorrelationRule(id="r1", opportunity_type="x", requires=["a"], justification="j")
    CorrelationRule(id="r2", opportunity_type="x", requires_category=["backup"], justification="j")
    CorrelationRule(id="r3", opportunity_type="x", relation_type="prerequisite", justification="j")


def test_correlation_rule_rejects_no_mechanism():
    try:
        CorrelationRule(id="r", opportunity_type="x", justification="j")
        assert False, "deveria rejeitar regra sem nenhum mecanismo"
    except RuleError:
        pass


def test_correlation_rule_rejects_combined_mechanisms():
    try:
        CorrelationRule(
            id="r", opportunity_type="x", justification="j",
            requires=["a"], requires_category=["backup"],
        )
        assert False, "deveria rejeitar regra combinando dois mecanismos"
    except RuleError:
        pass

    try:
        CorrelationRule(
            id="r2", opportunity_type="x", justification="j",
            requires=["a"], relation_type="prerequisite",
        )
        assert False, "deveria rejeitar requires + relation_type combinados"
    except RuleError:
        pass


def test_correlation_rule_rejects_unknown_relation_type():
    try:
        CorrelationRule(id="r", opportunity_type="x", justification="j", relation_type="lixo")
        assert False, "deveria rejeitar relation_type desconhecido — regra morta silenciosa"
    except RuleError:
        pass


def test_correlation_rule_accepts_known_relation_types():
    CorrelationRule(id="r1", opportunity_type="x", justification="j", relation_type="prerequisite")
    CorrelationRule(id="r2", opportunity_type="x", justification="j", relation_type="substitute")


if __name__ == "__main__":
    test_company_defaults_and_sources()
    test_source_confidence_bounds()
    test_product_belongs_to_vendor()
    test_opportunity_default_status_is_detected()
    test_opportunity_status_flow_values()
    test_portfolio_scoped_to_company()
    test_company_fase_b_fields_default_to_none_or_empty()
    test_company_account_standard_fields_default_to_none()
    test_address_accepts_all_optional_fields()
    test_context_note_requires_source()
    test_contact_impacted_area_defaults_to_none()
    test_product_relation_default_type_is_complementary()
    test_product_and_service_have_optional_category()
    test_company_signal_requires_source_and_defaults_open()
    test_opportunity_status_change_captures_status_and_timestamp()
    test_correlation_rule_accepts_single_mechanism()
    test_correlation_rule_rejects_no_mechanism()
    test_correlation_rule_rejects_combined_mechanisms()
    test_correlation_rule_rejects_unknown_relation_type()
    test_correlation_rule_accepts_known_relation_types()
    print("OK — todos os testes de modelos passaram")
