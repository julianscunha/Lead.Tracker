"""Smoke tests do motor de regras determinísticas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import Portfolio
from core.opportunity_engine import CorrelationRule, RuleError, evaluate_rules


VDC365_RULE = CorrelationRule(
    id="veeam_m365_sem_vdc365",
    opportunity_type="cross-sell",
    requires=["veeam_vbr", "m365"],
    absent=["vdc365"],
    justification="Cliente tem Veeam VBR e M365, mas não tem VDC365.",
)


def test_rule_fires_when_requires_present_and_absent_missing():
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365"])

    result = evaluate_rules(pf, [VDC365_RULE])

    assert len(result) == 1
    opp = result[0]
    assert opp.company_id == "c1"
    assert opp.type == "cross-sell"
    assert opp.evidence == ["veeam_vbr", "m365"]
    assert opp.status.value == "detected"


def test_rule_does_not_fire_when_absent_item_is_present():
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365", "vdc365"])

    result = evaluate_rules(pf, [VDC365_RULE])

    assert result == []


def test_rule_does_not_fire_when_requires_incomplete():
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr"])

    result = evaluate_rules(pf, [VDC365_RULE])

    assert result == []


def test_opportunity_never_generated_without_evidence():
    try:
        CorrelationRule(id="ruim", opportunity_type="x", requires=[], justification="sem evidência")
        assert False, "deveria rejeitar regra sem 'requires'"
    except RuleError:
        pass


def test_financial_and_strategic_score_are_none_no_ai_layer():
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365"])
    result = evaluate_rules(pf, [VDC365_RULE])
    assert result[0].financial_potential is None
    assert result[0].strategic_score is None


if __name__ == "__main__":
    test_rule_fires_when_requires_present_and_absent_missing()
    test_rule_does_not_fire_when_absent_item_is_present()
    test_rule_does_not_fire_when_requires_incomplete()
    test_opportunity_never_generated_without_evidence()
    test_financial_and_strategic_score_are_none_no_ai_layer()
    print("OK — todos os testes do motor de oportunidades passaram")
