"""Smoke tests do motor de regras determinísticas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta, timezone

from core.models import Company, CompanySignal, Portfolio, Product, ProductRelation, Service, SourceRef
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


# ── Formato de evidência rico (Fase C, Fatia 3) ───────────────────────────────

def test_evidence_summary_follows_fato_oportunidade_fonte_format():
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365"])
    result = evaluate_rules(pf, [VDC365_RULE])
    summary = result[0].evidence_summary
    assert "[FATO]" in summary
    assert "[OPORTUNIDADE]" in summary
    assert "[FONTE]" in summary
    assert "sincronizado em" in summary


def test_evidence_summary_uses_risco_label_for_prerequisite_rule():
    product = Product(
        id="vdc365", vendor_id="v1", name="VDC365",
        related_services=[ProductRelation(service_id="assessment", relation_type="prerequisite")],
    )
    rule = CorrelationRule(
        id="prereq_assessment", opportunity_type="risk", relation_type="prerequisite",
        justification="VDC365 requer assessment prévio.",
    )
    pf = Portfolio(company_id="c1", product_ids=["vdc365"])
    result = evaluate_rules(pf, [rule], products=[product])
    assert "[RISCO]" in result[0].evidence_summary
    assert "[OPORTUNIDADE]" not in result[0].evidence_summary


def test_discovery_prompt_propagates_from_rule_to_opportunity():
    rule = VDC365_RULE.model_copy(update={"discovery_prompt": "Por que o backup nunca virou protegido de fato?"})
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365"])
    result = evaluate_rules(pf, [rule])
    assert result[0].discovery_prompt == "Por que o backup nunca virou protegido de fato?"


def test_evidence_summary_never_blank_for_absent_only_rule():
    """`requires=[]`/`absent=[...]` é mecanismo válido (CorrelationRule só
    exige 'requires OU absent') — evidence fica vazio, [FATO] não pode."""
    rule = CorrelationRule(
        id="sem_legado", opportunity_type="cross-sell", absent=["produto_legado"],
        justification="Sem produto legado nenhum concorrente ocupa o espaço.",
    )
    pf = Portfolio(company_id="c1")
    result = evaluate_rules(pf, [rule])
    assert len(result) == 1
    assert "[FATO] ausência de produto_legado" in result[0].evidence_summary


def test_discovery_prompt_defaults_to_none_without_breaking():
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365"])
    result = evaluate_rules(pf, [VDC365_RULE])
    assert result[0].discovery_prompt is None


# ── Multiplicador de confiança por recência de atividade (Fase C, Fatia 4a) ──

def _company(last_activity_at=None) -> Company:
    return Company(name="Aurora Sistemas", last_activity_at=last_activity_at)


def test_warm_company_keeps_full_confidence_score():
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365"])
    recent = datetime.now(timezone.utc) - timedelta(days=10)
    result = evaluate_rules(pf, [VDC365_RULE], company=_company(recent))
    assert result[0].confidence_score == VDC365_RULE.confidence_score


def test_cold_company_beyond_90_days_gets_penalized_confidence_score():
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365"])
    old = datetime.now(timezone.utc) - timedelta(days=200)
    result = evaluate_rules(pf, [VDC365_RULE], company=_company(old))
    assert result[0].confidence_score == VDC365_RULE.confidence_score * 0.7


def test_company_without_last_activity_at_is_treated_as_cold():
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365"])
    result = evaluate_rules(pf, [VDC365_RULE], company=_company(None))
    assert result[0].confidence_score == VDC365_RULE.confidence_score * 0.7


def test_evaluate_rules_without_company_never_penalizes_retrocompat():
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365"])
    result = evaluate_rules(pf, [VDC365_RULE])
    assert result[0].confidence_score == VDC365_RULE.confidence_score


def test_naive_last_activity_at_never_crashes_the_engine():
    """CLAUDE.md: nunca vazar exceção técnica crua — company.last_activity_at
    sempre chega UTC-aware hoje (repository/provider garantem isso), mas o
    motor não pode confiar cegamente nisso e quebrar com TypeError se algum
    dia vier naive."""
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365"])
    naive = datetime.now() - timedelta(days=10)
    result = evaluate_rules(pf, [VDC365_RULE], company=_company(naive))
    assert result[0].confidence_score == VDC365_RULE.confidence_score


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
    test_evidence_summary_follows_fato_oportunidade_fonte_format()
    test_evidence_summary_uses_risco_label_for_prerequisite_rule()
    test_evidence_summary_never_blank_for_absent_only_rule()
    test_discovery_prompt_propagates_from_rule_to_opportunity()
    test_discovery_prompt_defaults_to_none_without_breaking()
    test_warm_company_keeps_full_confidence_score()
    test_cold_company_beyond_90_days_gets_penalized_confidence_score()
    test_company_without_last_activity_at_is_treated_as_cold()
    test_evaluate_rules_without_company_never_penalizes_retrocompat()
    test_naive_last_activity_at_never_crashes_the_engine()
    print("OK — todos os testes do motor de oportunidades passaram")
