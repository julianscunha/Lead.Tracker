"""Fase N — reconciliação com a empresa já gravada (função pura)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import Address, Company, SourceRef  # noqa: E402
from core.normalization import comparable, effective_field_source, reconcile  # noqa: E402


def _company(**kw):
    kw.setdefault("name", "Acme")
    kw.setdefault("sources", [SourceRef(type="salesforce")])
    return Company(**kw)


def test_same_source_refreshes_value_and_reports_the_change():
    persisted = _company(industry="Software", employee_count=10)
    result = reconcile(persisted, _company(industry="Serviços", employee_count=10), "salesforce")
    assert result.company.industry == "Serviços" and result.company.field_sources["industry"] == "salesforce"
    assert [(c.field, c.old, c.new) for c in result.changes] == [("industry", "Software", "Serviços")]
    assert result.conflicts == []


def test_other_source_that_differs_opens_conflict_and_keeps_current_value():
    persisted = _company(industry="Software")
    result = reconcile(persisted, _company(industry="Varejo", sources=[SourceRef(type="csv")]), "csv")
    assert result.company.industry == "Software" and result.changes == []
    assert [(c.field, c.current_source, c.incoming_source, c.incoming_value) for c in result.conflicts] == [
        ("industry", "salesforce", "csv", "Varejo")]


def test_empty_incoming_never_erases_or_conflicts_and_empty_current_is_filled():
    persisted = _company(industry="Software", website=None)
    incoming = _company(industry="  ", website="https://acme.com.br", sources=[SourceRef(type="google_maps")])
    result = reconcile(persisted, incoming, "google_maps")
    assert result.company.industry == "Software"  # vazio da fonte não apaga
    assert result.company.website == "https://acme.com.br" and result.company.field_sources["website"] == "google_maps"
    assert result.conflicts == [] and result.changes == []


def test_formatting_differences_are_not_conflicts_and_zero_is_a_real_value():
    persisted = _company(industry="Tecnologia da Informação", website="https://www.acme.com.br/")
    incoming = _company(industry="tecnologia da informacao!", website="ACME.com.br", sources=[SourceRef(type="csv")])
    assert reconcile(persisted, incoming, "csv").conflicts == []
    zero = _company(employee_count=0)
    assert reconcile(zero, _company(employee_count=5, sources=[SourceRef(type="csv")]), "csv").conflicts[0].field == "employee_count"
    assert reconcile(_company(employee_count=5), _company(employee_count=0), "salesforce").company.employee_count == 0


def test_mapping_owned_field_is_never_contested_by_the_standard_fetch():
    persisted = _company(industry="Setor escolhido pelo usuário", field_sources={"industry": "mapping"})
    result = reconcile(persisted, _company(industry="Outro"), "salesforce")
    assert result.company.industry == "Setor escolhido pelo usuário" and result.conflicts == []


def test_manual_owned_field_is_not_overwritten_and_opens_conflict():
    persisted = _company(industry="Editado à mão", field_sources={"industry": "manual"})
    result = reconcile(persisted, _company(industry="Da fonte"), "salesforce")
    assert result.company.industry == "Editado à mão" and len(result.conflicts) == 1


def test_resolved_conflict_does_not_reopen_unless_the_source_brings_a_new_value():
    persisted = _company(industry="Software")
    incoming = _company(industry="Varejo", sources=[SourceRef(type="csv")])
    rejected = frozenset({("industry", "csv", comparable("industry", "Varejo"))})
    assert reconcile(persisted, incoming, "csv", rejected).conflicts == []
    other_value = _company(industry="Indústria", sources=[SourceRef(type="csv")])
    assert len(reconcile(persisted, other_value, "csv", rejected).conflicts) == 1


def test_owner_is_derived_for_legacy_rows_single_source_and_multi_source():
    assert effective_field_source(_company(), "industry") == "salesforce"
    multi = _company(sources=[SourceRef(type="salesforce"), SourceRef(type="csv")])
    assert effective_field_source(multi, "industry") == "legacy"
    # legacy: nenhuma fonte "é a dona" -> divergência vira conflito, sem inundação retroativa na migração
    assert len(reconcile(_company(industry="A", sources=multi.sources), _company(industry="B"), "salesforce").conflicts) == 1


def test_address_is_compared_by_content_and_is_customer_still_uses_or_semantics():
    persisted = _company(address=Address(city="São Paulo", state="SP"), is_customer=True)
    incoming = _company(address=Address(city="sao paulo", state="sp"), is_customer=False, sources=[SourceRef(type="csv")])
    result = reconcile(persisted, incoming, "csv")
    assert result.conflicts == [] and result.company.is_customer is True
