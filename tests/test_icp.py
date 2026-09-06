"""Smoke tests da derivação automática de ICP (Fase E, módulo 3
`icp-auto-derivation`)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.icp import derive_icp_suggestion
from core.models import Company, Opportunity


def _satisfied_company(**kwargs) -> Company:
    defaults = dict(name="Cliente", is_customer=True)
    defaults.update(kwargs)
    return Company(**defaults)


def _high_score_opp(company_id: str, score: float = 0.9) -> Opportunity:
    return Opportunity(company_id=company_id, type="cross-sell", opportunity_score=score)


def test_returns_none_when_no_satisfied_customer_exists():
    companies = [Company(name="Prospect", is_customer=False)]
    assert derive_icp_suggestion(companies, []) is None


def test_returns_none_when_customer_has_no_high_score_opportunity():
    company = _satisfied_company()
    opps = [_high_score_opp(company.id, score=0.5)]  # abaixo do threshold 0.7
    assert derive_icp_suggestion([company], opps) is None


def test_customer_without_any_opportunity_is_never_counted_as_satisfied():
    company = _satisfied_company()
    assert derive_icp_suggestion([company], []) is None


def test_low_confidence_below_minimum_sample_still_returns_suggestion():
    """Achado da consulta ao Growth Hacker: abaixo do piso de amostra a
    sugestão continua sendo calculada e devolvida, nunca escondida —
    só marcada confidence='low'."""
    companies = [_satisfied_company(industry="Varejo", segment="pequena") for _ in range(3)]
    opps = [_high_score_opp(c.id) for c in companies]

    suggestion = derive_icp_suggestion(companies, opps)

    assert suggestion is not None
    assert suggestion.sample_size == 3
    assert suggestion.confidence == "low"
    assert suggestion.industry_hint == "Varejo"


def test_high_confidence_at_or_above_minimum_sample():
    companies = [_satisfied_company(industry="Varejo", segment="pequena") for _ in range(5)]
    opps = [_high_score_opp(c.id) for c in companies]

    suggestion = derive_icp_suggestion(companies, opps)

    assert suggestion.sample_size == 5
    assert suggestion.confidence == "high"


def test_mode_and_share_computed_correctly_with_weak_majority():
    companies = [
        _satisfied_company(industry="Varejo"), _satisfied_company(industry="Varejo"),
        _satisfied_company(industry="Saúde"), _satisfied_company(industry="Manufatura"),
        _satisfied_company(industry="Educação"),
    ]
    opps = [_high_score_opp(c.id) for c in companies]

    suggestion = derive_icp_suggestion(companies, opps)

    assert suggestion.industry_hint == "Varejo"
    assert suggestion.industry_hint_share == 2 / 5


def test_uses_max_opportunity_score_per_company_not_first_found():
    """Uma empresa com uma oportunidade fraca e outra forte ainda conta
    como satisfeita — o critério é "tem pelo menos uma boa", não "todas
    boas"."""
    company = _satisfied_company(industry="Varejo")
    opps = [_high_score_opp(company.id, score=0.2), _high_score_opp(company.id, score=0.9)]

    suggestion = derive_icp_suggestion([company], opps)

    assert suggestion is not None
    assert suggestion.sample_size == 1


def test_non_customer_with_high_score_opportunity_never_counts():
    prospect = Company(name="Prospect", is_customer=False)
    opps = [_high_score_opp(prospect.id)]
    assert derive_icp_suggestion([prospect], opps) is None


def test_company_size_hint_derived_from_segment_omitted_when_all_blank():
    companies = [_satisfied_company(industry="Varejo", segment=None) for _ in range(2)]
    opps = [_high_score_opp(c.id) for c in companies]

    suggestion = derive_icp_suggestion(companies, opps)

    assert suggestion.company_size_hint is None
    assert suggestion.company_size_hint_share is None


def test_opportunity_score_none_is_never_treated_as_satisfied():
    company = _satisfied_company(industry="Varejo")
    opps = [Opportunity(company_id=company.id, type="cross-sell", opportunity_score=None)]
    assert derive_icp_suggestion([company], opps) is None


if __name__ == "__main__":
    test_returns_none_when_no_satisfied_customer_exists()
    test_returns_none_when_customer_has_no_high_score_opportunity()
    test_customer_without_any_opportunity_is_never_counted_as_satisfied()
    test_low_confidence_below_minimum_sample_still_returns_suggestion()
    test_high_confidence_at_or_above_minimum_sample()
    test_mode_and_share_computed_correctly_with_weak_majority()
    test_uses_max_opportunity_score_per_company_not_first_found()
    test_non_customer_with_high_score_opportunity_never_counts()
    test_company_size_hint_derived_from_segment_omitted_when_all_blank()
    test_opportunity_score_none_is_never_treated_as_satisfied()
    print("OK — todos os testes de derivação de ICP passaram")
