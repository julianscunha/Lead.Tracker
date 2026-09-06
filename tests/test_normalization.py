"""Smoke tests de normalização e deduplicação de empresas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone

from core.models import Address, Company, SourceRef
from core.normalization import merge_companies, merge_pair, normalize_domain, normalize_name


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


def test_merge_pair_refreshes_last_activity_at_from_new_fetch():
    """Fase C, Fatia 4a — ao contrário dos outros campos (que preservam o
    valor já persistido), last_activity_at precisa refletir o fetch mais
    recente, senão o sinal de momentum nunca se move após o primeiro sync."""
    old = datetime(2026, 1, 1, tzinfo=timezone.utc)
    new = datetime(2026, 8, 1, tzinfo=timezone.utc)
    persisted = Company(name="Acme", website="https://acme.com", last_activity_at=old)
    freshly_fetched = Company(name="Acme", website="https://acme.com", last_activity_at=new)

    result = merge_pair(persisted, freshly_fetched)

    assert result.last_activity_at == new


def test_merge_pair_keeps_old_last_activity_at_when_new_fetch_has_none():
    """Fonte sem esse dado (ex.: Manual) não deve apagar o que já foi
    aprendido de uma fonte anterior."""
    old = datetime(2026, 1, 1, tzinfo=timezone.utc)
    persisted = Company(name="Acme", website="https://acme.com", last_activity_at=old)
    freshly_fetched = Company(name="Acme", website="https://acme.com", last_activity_at=None)

    result = merge_pair(persisted, freshly_fetched)

    assert result.last_activity_at == old


def test_merge_pair_keeps_base_account_standard_fields_when_present():
    """Ao contrário de last_activity_at, industry/annual_revenue/
    employee_count/address não são sinal de momentum — primeiro valor
    não-nulo vence, mesmo padrão de legal_name/website."""
    base = Company(
        name="Acme", industry="Varejo", annual_revenue=1000.0, employee_count=10,
        address=Address(city="São Paulo"),
    )
    other = Company(
        name="Acme", industry="Manufatura", annual_revenue=2000.0, employee_count=20,
        address=Address(city="Rio de Janeiro"),
    )

    result = merge_pair(base, other)

    assert result.industry == "Varejo"
    assert result.annual_revenue == 1000.0
    assert result.employee_count == 10
    assert result.address.city == "São Paulo"


def test_merge_pair_preserves_zero_annual_revenue_and_employee_count():
    """Regressão: `or` é errado pra numérico — 0 é falsy em Python, então
    annual_revenue=0.0 (empresa pré-receita) ou employee_count=0 em base
    seria sobrescrito por other mesmo sendo valor real, não ausência."""
    base = Company(name="Acme", annual_revenue=0.0, employee_count=0)
    other = Company(name="Acme", annual_revenue=5000.0, employee_count=50)

    result = merge_pair(base, other)

    assert result.annual_revenue == 0.0
    assert result.employee_count == 0


def test_merge_pair_preserves_zero_deal_size_hint():
    """Mesma regressão de annual_revenue/employee_count, agora pro campo
    novo da Fase F (módulo 4) — 0.0 é um valor real (negócio de valor
    residual), não ausência de dado."""
    base = Company(name="Acme", deal_size_hint=0.0)
    other = Company(name="Acme", deal_size_hint=5000.0)

    result = merge_pair(base, other)

    assert result.deal_size_hint == 0.0


def test_merge_pair_never_zeroes_deal_size_hint_when_freshly_fetched_company_has_none():
    """fetch_companies() nunca popula deal_size_hint (só o split de
    mapeamento escreve nele, depois do merge) — resincronizar não pode
    apagar um valor já promovido por um FieldMapping."""
    base = Company(name="Acme", deal_size_hint=42000.0)
    other = Company(name="Acme")  # fresh fetch, sem deal_size_hint

    result = merge_pair(base, other)

    assert result.deal_size_hint == 42000.0


def test_merge_pair_fills_account_standard_fields_from_other_when_base_is_none():
    base = Company(name="Acme")
    other = Company(name="Acme", industry="Manufatura", annual_revenue=2000.0, employee_count=20, address=Address(city="Rio de Janeiro"))

    result = merge_pair(base, other)

    assert result.industry == "Manufatura"
    assert result.annual_revenue == 2000.0
    assert result.employee_count == 20
    assert result.address.city == "Rio de Janeiro"


if __name__ == "__main__":
    test_normalize_domain_strips_protocol_www_and_path()
    test_normalize_name_collapses_whitespace_and_case()
    test_same_domain_from_different_sources_merges_into_one_company()
    test_different_domains_stay_separate()
    test_no_website_falls_back_to_normalized_name()
    test_merge_never_loses_existing_true_is_customer()
    test_merge_pair_refreshes_last_activity_at_from_new_fetch()
    test_merge_pair_keeps_old_last_activity_at_when_new_fetch_has_none()
    test_merge_pair_keeps_base_account_standard_fields_when_present()
    test_merge_pair_preserves_zero_annual_revenue_and_employee_count()
    test_merge_pair_preserves_zero_deal_size_hint()
    test_merge_pair_never_zeroes_deal_size_hint_when_freshly_fetched_company_has_none()
    test_merge_pair_fills_account_standard_fields_from_other_when_base_is_none()
    print("OK — todos os testes de normalização passaram")
