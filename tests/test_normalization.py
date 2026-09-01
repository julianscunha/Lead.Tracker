"""Smoke tests de normalização e deduplicação de empresas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import Company, SourceRef
from core.normalization import merge_companies, normalize_domain, normalize_name


def test_normalize_domain_strips_protocol_www_and_path():
    assert normalize_domain("https://www.Acme.com/sobre") == "acme.com"
    assert normalize_domain("acme.com") == "acme.com"
    assert normalize_domain(None) is None


def test_normalize_name_collapses_whitespace_and_case():
    assert normalize_name("  Acme   Ltda  ") == "acme ltda"


def test_same_domain_from_different_sources_merges_into_one_company():
    a = Company(name="Acme Corp", website="https://acme.com", sources=[SourceRef(type="salesforce")])
    b = Company(name="ACME", website="https://www.acme.com", sources=[SourceRef(type="website", confidence=0.8)])

    result = merge_companies([a, b])

    assert len(result) == 1
    merged = result[0]
    source_types = {s.type for s in merged.sources}
    assert source_types == {"salesforce", "website"}


def test_different_domains_stay_separate():
    a = Company(name="Acme", website="https://acme.com")
    b = Company(name="Beta", website="https://beta.com")

    result = merge_companies([a, b])

    assert len(result) == 2


def test_no_website_falls_back_to_normalized_name():
    a = Company(name="Acme Corp", sources=[SourceRef(type="manual")])
    b = Company(name="  acme   corp  ", sources=[SourceRef(type="salesforce")])

    result = merge_companies([a, b])

    assert len(result) == 1


def test_merge_never_loses_existing_true_is_customer():
    a = Company(name="Acme", website="https://acme.com", is_customer=True)
    b = Company(name="Acme", website="https://acme.com", is_customer=False)

    result = merge_companies([a, b])

    assert result[0].is_customer is True


if __name__ == "__main__":
    test_normalize_domain_strips_protocol_www_and_path()
    test_normalize_name_collapses_whitespace_and_case()
    test_same_domain_from_different_sources_merges_into_one_company()
    test_different_domains_stay_separate()
    test_no_website_falls_back_to_normalized_name()
    test_merge_never_loses_existing_true_is_customer()
    print("OK — todos os testes de normalização passaram")
