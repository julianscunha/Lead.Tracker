"""Smoke tests do motor de regras determinísticas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import CompanySignal, Portfolio, Product, ProductRelation, Service, SourceRef
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


def test_inactive_rule_never_fires():
    inactive = VDC365_RULE.model_copy(update={"active": False})
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365"])
    assert evaluate_rules(pf, [inactive]) == []


# ── Regra por categoria (Fase C) ──────────────────────────────────────────────

BACKUP_PRODUCT = Product(id="veeam_vbr", vendor_id="v1", name="Veeam VBR", category="backup")
MONITORING_SERVICE = Service(id="zabbix", name="Zabbix", category="monitoring")

CATEGORY_RULE = CorrelationRule(
    id="backup_sem_monitoring", opportunity_type="cross-sell",
    requires_category=["backup"], absent_category=["monitoring"],
    justification="Tem solução de backup, mas nenhuma de monitoramento.",
)


def test_category_rule_fires_when_category_present_and_absent_category_missing():
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr"])
    result = evaluate_rules(pf, [CATEGORY_RULE], products=[BACKUP_PRODUCT], services=[MONITORING_SERVICE])
    assert len(result) == 1
    assert result[0].evidence == ["backup"]


def test_category_rule_does_not_fire_when_absent_category_present():
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr"], service_ids=["zabbix"])
    result = evaluate_rules(pf, [CATEGORY_RULE], products=[BACKUP_PRODUCT], services=[MONITORING_SERVICE])
    assert result == []


def test_category_rule_never_fires_without_catalog_retrocompat():
    """Sem passar products/services, regra de categoria nunca acha nada —
    não quebra quem só usa regra simples e não passa catálogo."""
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr"])
    result = evaluate_rules(pf, [CATEGORY_RULE])
    assert result == []


# ── Regra de relação tipada (Fase C) ──────────────────────────────────────────

def test_prerequisite_relation_generates_risk_flag_not_fake_opportunity():
    product = Product(
        id="vdc365", vendor_id="v1", name="VDC365",
        related_services=[ProductRelation(service_id="assessment", relation_type="prerequisite")],
    )
    rule = CorrelationRule(
        id="prereq_assessment", opportunity_type="risk", relation_type="prerequisite",
        justification="VDC365 requer assessment prévio.",
    )
    pf = Portfolio(company_id="c1", product_ids=["vdc365"])  # sem "assessment"

    result = evaluate_rules(pf, [rule], products=[product])

    assert len(result) == 1
    assert result[0].risk_flag is not None
    assert "vdc365" in result[0].risk_flag


def test_prerequisite_relation_does_not_fire_when_prerequisite_present():
    product = Product(
        id="vdc365", vendor_id="v1", name="VDC365",
        related_services=[ProductRelation(service_id="assessment", relation_type="prerequisite")],
    )
    rule = CorrelationRule(
        id="prereq_assessment", opportunity_type="risk", relation_type="prerequisite",
        justification="VDC365 requer assessment prévio.",
    )
    pf = Portfolio(company_id="c1", product_ids=["vdc365"], service_ids=["assessment"])

    result = evaluate_rules(pf, [rule], products=[product])
    assert result == []


def test_substitute_relation_generates_consolidation_opportunity():
    product = Product(
        id="antivirus_a", vendor_id="v1", name="Antivírus A",
        related_services=[ProductRelation(service_id="antivirus_b_service", relation_type="substitute")],
    )
    rule = CorrelationRule(
        id="consolidar_antivirus", opportunity_type="consolidation", relation_type="substitute",
        justification="Dois antivírus concorrentes coexistindo.",
    )
    pf = Portfolio(company_id="c1", product_ids=["antivirus_a"], service_ids=["antivirus_b_service"])

    result = evaluate_rules(pf, [rule], products=[product])

    assert len(result) == 1
    assert result[0].type == "consolidation"
    assert result[0].risk_flag is None


# ── Sinais de expansão (Fase C, Fatia 2) ──────────────────────────────────────

RENEWAL_RULE = CorrelationRule(
    id="renovacao_proxima", opportunity_type="renewal",
    requires=["renewal_upcoming"],
    justification="Sinal de renovação próxima em aberto.",
)


def _signal(company_id: str, signal_type: str, status: str = "open") -> CompanySignal:
    return CompanySignal(
        company_id=company_id, signal_type=signal_type, status=status,
        source=SourceRef(type="manual", confidence=1.0),
    )


def test_open_signal_triggers_rule_via_requires():
    pf = Portfolio(company_id="c1")
    signals = [_signal("c1", "renewal_upcoming")]

    result = evaluate_rules(pf, [RENEWAL_RULE], signals=signals)

    assert len(result) == 1
    assert result[0].type == "renewal"


def test_resolved_signal_never_triggers_rule():
    pf = Portfolio(company_id="c1")
    signals = [_signal("c1", "renewal_upcoming", status="resolved")]

    result = evaluate_rules(pf, [RENEWAL_RULE], signals=signals)

    assert result == []


def test_evaluate_rules_without_signals_still_works_retrocompat():
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365"])
    result = evaluate_rules(pf, [VDC365_RULE])
    assert len(result) == 1


if __name__ == "__main__":
    test_rule_fires_when_requires_present_and_absent_missing()
    test_rule_does_not_fire_when_absent_item_is_present()
    test_rule_does_not_fire_when_requires_incomplete()
    test_opportunity_never_generated_without_evidence()
    test_financial_and_strategic_score_are_none_no_ai_layer()
    test_inactive_rule_never_fires()
    test_category_rule_fires_when_category_present_and_absent_category_missing()
    test_category_rule_does_not_fire_when_absent_category_present()
    test_category_rule_never_fires_without_catalog_retrocompat()
    test_prerequisite_relation_generates_risk_flag_not_fake_opportunity()
    test_prerequisite_relation_does_not_fire_when_prerequisite_present()
    test_substitute_relation_generates_consolidation_opportunity()
    test_open_signal_triggers_rule_via_requires()
    test_resolved_signal_never_triggers_rule()
    test_evaluate_rules_without_signals_still_works_retrocompat()
    print("OK — todos os testes do motor de oportunidades passaram")
