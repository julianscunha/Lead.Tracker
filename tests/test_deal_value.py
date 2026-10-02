"""Fase O (R12) — valor típico informado na regra vira `financial_potential`; o sistema só copia."""
import asyncio
import sys
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.dashboard_metrics import compute_kpis, financial_potential_by_vendor  # noqa: E402
from core.models import Company, CorrelationRule, Opportunity, Portfolio  # noqa: E402
from core.opportunity_engine import evaluate_rules  # noqa: E402
from core.repository import list_rules, save_opportunity, save_rule, list_opportunities, save_company  # noqa: E402
from tests.test_persistence import _fresh_session_factory  # noqa: E402


def _rule(**kw):
    base = dict(opportunity_type="cross-sell", justification="Tem Veeam e falta DR.", requires=["veeam"], absent=["dr"])
    base.update(kw)
    return CorrelationRule(**base)


def _evaluate(rule):
    portfolio = Portfolio(company_id="c1", product_ids=["veeam"])
    return evaluate_rules(portfolio, [rule])


def test_rule_with_value_copies_it_and_explains_the_origin():
    opp = _evaluate(_rule(estimated_deal_value=40000))[0]
    assert opp.financial_potential == 40000
    assert opp.financial_potential_basis == "Valor típico informado na regra «cross-sell»: R$ 40.000"


def test_rule_without_value_leaves_potential_empty_never_a_default():
    opp = _evaluate(_rule())[0]
    assert opp.financial_potential is None and opp.financial_potential_basis is None


def test_zero_or_negative_values_are_rejected_so_zero_never_means_unknown():
    for bad in (0, -1, -0.01):
        with pytest.raises(ValidationError):
            _rule(estimated_deal_value=bad)


def test_cents_are_shown_and_big_numbers_use_brazilian_separators():
    assert _evaluate(_rule(estimated_deal_value=1234567.5))[0].financial_potential_basis.endswith("R$ 1.234.567,50")


def test_value_round_trips_through_the_database_for_rule_and_opportunity():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            sf = await _fresh_session_factory(tmp)
            rule = _rule(estimated_deal_value=25000)
            opp = _evaluate(rule)[0]
            async with sf() as session:
                await save_company(session, Company(id="c1", name="Aurora"))
                await save_rule(session, rule)
                await save_opportunity(session, opp)
                loaded_rule = (await list_rules(session))[0]
                loaded_opp = (await list_opportunities(session))[0]
            assert loaded_rule.estimated_deal_value == 25000
            assert loaded_opp.financial_potential == 25000 and "R$ 25.000" in loaded_opp.financial_potential_basis
    asyncio.run(run())


def test_resync_after_the_rule_value_changes_updates_the_opportunity_value_and_basis():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            sf = await _fresh_session_factory(tmp)
            rule = _rule(estimated_deal_value=10000)
            async with sf() as session:
                await save_company(session, Company(id="c1", name="Aurora"))
                await save_opportunity(session, _evaluate(rule)[0])
                # a mesma regra (mesmo id) com outro valor: o id da oportunidade é determinístico
                changed = rule.model_copy(update={"estimated_deal_value": 55000})
                await save_opportunity(session, _evaluate(changed)[0])
                opps = await list_opportunities(session)
            assert len(opps) == 1 and opps[0].financial_potential == 55000 and "R$ 55.000" in opps[0].financial_potential_basis
    asyncio.run(run())


def test_dashboard_sums_only_informed_values_counts_the_rest_and_two_rules_on_one_company_add_up():
    a = Opportunity(company_id="c1", type="cross-sell", financial_potential=40000.0)
    b = Opportunity(company_id="c1", type="up-sell", financial_potential=10000.0)  # mesma empresa: soma (sobreposição possível)
    c = Opportunity(company_id="c2", type="cross-sell")
    kpis = compute_kpis([Company(id="c1", name="A"), Company(id="c2", name="B")], [a, b, c], {}, {})
    assert kpis.financial_potential_total == 50000.0 and kpis.opportunities_without_value == 1


def test_geo_discovery_opportunity_never_inherits_a_value():
    from core.geo_discovery import build_discovery_records
    from providers.google_maps import PlaceSignal
    signal = PlaceSignal(place_id="p", name="Loja", category="x", business_status="OPERATIONAL", rating=4.0, review_count=10, formatted_address=None)
    _, opportunity = build_discovery_records(signal, 0.8, "rep-1", None, "produto-ref")
    assert opportunity.financial_potential is None and opportunity.financial_potential_basis is None
