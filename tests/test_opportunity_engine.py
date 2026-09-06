"""Smoke tests do motor de regras determinísticas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta, timezone

from core.models import Company, CompanySignal, Portfolio, Product, ProductRelation, Service, SourceRef
from core.opportunity_engine import (
    CorrelationRule, RuleError, compute_account_health, compute_qbr_suggested_days,
    compute_severity_band, evaluate_rules, is_aging_opportunity, is_zombie_opportunity,
    parse_aging_sla_days, requires_status_change_justification,
)


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


def test_lukewarm_company_between_120_and_270_days_gets_15_percent_penalty():
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365"])
    lukewarm = datetime.now(timezone.utc) - timedelta(days=200)
    result = evaluate_rules(pf, [VDC365_RULE], company=_company(lukewarm))
    assert result[0].confidence_score == VDC365_RULE.confidence_score * 0.85


def test_very_cold_company_beyond_270_days_gets_50_percent_penalty():
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365"])
    very_old = datetime.now(timezone.utc) - timedelta(days=400)
    result = evaluate_rules(pf, [VDC365_RULE], company=_company(very_old))
    assert result[0].confidence_score == VDC365_RULE.confidence_score * 0.5


def test_company_without_last_activity_at_is_treated_as_very_cold():
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365"])
    result = evaluate_rules(pf, [VDC365_RULE], company=_company(None))
    assert result[0].confidence_score == VDC365_RULE.confidence_score * 0.5


def test_evaluate_rules_without_company_never_penalizes_retrocompat():
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365"])
    result = evaluate_rules(pf, [VDC365_RULE])
    assert result[0].confidence_score == VDC365_RULE.confidence_score


# ── Banda de severidade (Fase C, Fatia 5) ─────────────────────────────────────

def test_compute_severity_band_covers_all_nine_combinations():
    expected = {
        ("isolado", "nao_critico"): "baixo",
        ("isolado", "critico_interno"): "medio",
        ("isolado", "critico_exposto"): "alto",
        ("parcial", "nao_critico"): "medio",
        ("parcial", "critico_interno"): "alto",
        ("parcial", "critico_exposto"): "alto",
        ("generalizado", "nao_critico"): "medio",
        ("generalizado", "critico_interno"): "alto",
        ("generalizado", "critico_exposto"): "critico",
    }
    for (scope, criticality), band in expected.items():
        assert compute_severity_band(scope, criticality) == band


def test_compute_severity_band_falls_back_to_nao_avaliado_when_any_field_blank():
    assert compute_severity_band(None, "critico_exposto") == "nao_avaliado"
    assert compute_severity_band("isolado", None) == "nao_avaliado"
    assert compute_severity_band(None, None) == "nao_avaliado"


def test_naive_last_activity_at_never_crashes_the_engine():
    """CLAUDE.md: nunca vazar exceção técnica crua — company.last_activity_at
    sempre chega UTC-aware hoje (repository/provider garantem isso), mas o
    motor não pode confiar cegamente nisso e quebrar com TypeError se algum
    dia vier naive."""
    pf = Portfolio(company_id="c1", product_ids=["veeam_vbr", "m365"])
    naive = datetime.now() - timedelta(days=10)
    result = evaluate_rules(pf, [VDC365_RULE], company=_company(naive))
    assert result[0].confidence_score == VDC365_RULE.confidence_score


def test_compute_account_health_takes_the_worse_of_recency_and_confidence():
    assert compute_account_health(recency_days=10, avg_open_confidence=0.9) == "verde"
    assert compute_account_health(recency_days=10, avg_open_confidence=0.3) == "vermelha"
    assert compute_account_health(recency_days=300, avg_open_confidence=0.9) == "vermelha"
    assert compute_account_health(recency_days=150, avg_open_confidence=0.5) == "amarela"


def test_compute_account_health_only_one_axis_present_still_works():
    assert compute_account_health(recency_days=10, avg_open_confidence=None) == "verde"
    assert compute_account_health(recency_days=None, avg_open_confidence=0.2) == "vermelha"


def test_compute_account_health_is_dados_insuficientes_never_verde_by_absence():
    assert compute_account_health(recency_days=None, avg_open_confidence=None) == "dados_insuficientes"


def test_compute_qbr_suggested_days_vermelha_is_always_urgent():
    days, reason = compute_qbr_suggested_days("vermelha", renewal_days=10, open_signal_count=0)
    assert days == 0
    assert reason == "imediata"

    days, _ = compute_qbr_suggested_days("vermelha", renewal_days=None, open_signal_count=0)
    assert days == 15


def test_compute_qbr_suggested_days_verde_aligns_to_real_renewal_date():
    days, reason = compute_qbr_suggested_days("verde", renewal_days=75, open_signal_count=0)
    assert days == 75
    assert reason == "alinhada_a_renovacao"

    days, _ = compute_qbr_suggested_days("verde", renewal_days=None, open_signal_count=0)
    assert days == 180


def test_compute_qbr_suggested_days_dados_insuficientes_treated_as_amarela():
    days, reason = compute_qbr_suggested_days("dados_insuficientes", renewal_days=None, open_signal_count=0)
    assert (days, reason) == compute_qbr_suggested_days("amarela", renewal_days=None, open_signal_count=0)


def test_compute_qbr_suggested_days_two_or_more_open_signals_escalates_one_row():
    calm = compute_qbr_suggested_days("verde", renewal_days=None, open_signal_count=0)
    escalated = compute_qbr_suggested_days("verde", renewal_days=None, open_signal_count=2)
    assert escalated == compute_qbr_suggested_days("amarela", renewal_days=None, open_signal_count=0)
    assert escalated != calm

    # vermelha já é o pior estado — escalonar não pode piorar além disso
    already_worst = compute_qbr_suggested_days("vermelha", renewal_days=None, open_signal_count=5)
    assert already_worst == compute_qbr_suggested_days("vermelha", renewal_days=None, open_signal_count=0)


def test_requires_status_change_justification_for_one_step_advance_is_false():
    assert requires_status_change_justification("detected", "qualified") is False
    assert requires_status_change_justification("qualified", "reviewed") is False


def test_requires_status_change_justification_for_two_or_more_stage_skip_is_true():
    assert requires_status_change_justification("detected", "contacted") is True
    assert requires_status_change_justification("detected", "opportunity") is True


def test_requires_status_change_justification_going_backward_is_false():
    assert requires_status_change_justification("contacted", "qualified") is False


def test_requires_status_change_justification_dismissed_reopen_is_always_true():
    assert requires_status_change_justification("dismissed", "detected") is True
    assert requires_status_change_justification("dismissed", "opportunity") is True


def test_requires_status_change_justification_advancing_to_dismissed_is_false():
    assert requires_status_change_justification("detected", "dismissed") is False
    assert requires_status_change_justification("opportunity", "dismissed") is False


def test_requires_status_change_justification_same_status_is_false():
    assert requires_status_change_justification("qualified", "qualified") is False
    assert requires_status_change_justification("dismissed", "dismissed") is False


def test_is_zombie_opportunity_flags_stagnation_beyond_30_days():
    now = datetime(2026, 9, 5, tzinfo=timezone.utc)
    fresh = now - timedelta(days=10)
    stale = now - timedelta(days=31)
    assert is_zombie_opportunity("qualified", fresh, now) is False
    assert is_zombie_opportunity("qualified", stale, now) is True


def test_is_zombie_opportunity_dismissed_is_never_zombie():
    now = datetime(2026, 9, 5, tzinfo=timezone.utc)
    stale = now - timedelta(days=400)
    assert is_zombie_opportunity("dismissed", stale, now) is False


def test_is_zombie_opportunity_handles_naive_last_touch_at():
    now = datetime(2026, 9, 5, tzinfo=timezone.utc)
    naive_stale = datetime(2026, 7, 1)  # sem tzinfo
    assert is_zombie_opportunity("qualified", naive_stale, now) is True


def test_is_aging_opportunity_only_flags_detected_beyond_sla():
    now = datetime(2026, 9, 5, tzinfo=timezone.utc)
    stale = now - timedelta(days=10)
    fresh = now - timedelta(days=3)
    assert is_aging_opportunity("detected", stale, now, sla_days=7) is True
    assert is_aging_opportunity("detected", fresh, now, sla_days=7) is False


def test_is_aging_opportunity_never_flags_non_detected_status():
    now = datetime(2026, 9, 5, tzinfo=timezone.utc)
    stale = now - timedelta(days=400)
    assert is_aging_opportunity("qualified", stale, now, sla_days=7) is False
    assert is_aging_opportunity("dismissed", stale, now, sla_days=7) is False


def test_parse_aging_sla_days_falls_back_to_default_when_missing_or_invalid():
    assert parse_aging_sla_days({}) == 7
    assert parse_aging_sla_days({"AGING_SLA_DAYS": "lixo"}) == 7
    assert parse_aging_sla_days({"AGING_SLA_DAYS": "0"}) == 7
    assert parse_aging_sla_days({"AGING_SLA_DAYS": "-5"}) == 7


def test_parse_aging_sla_days_reads_valid_configured_value():
    assert parse_aging_sla_days({"AGING_SLA_DAYS": "14"}) == 14


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
    test_lukewarm_company_between_120_and_270_days_gets_15_percent_penalty()
    test_very_cold_company_beyond_270_days_gets_50_percent_penalty()
    test_company_without_last_activity_at_is_treated_as_very_cold()
    test_evaluate_rules_without_company_never_penalizes_retrocompat()
    test_naive_last_activity_at_never_crashes_the_engine()
    test_compute_severity_band_covers_all_nine_combinations()
    test_compute_severity_band_falls_back_to_nao_avaliado_when_any_field_blank()
    test_compute_account_health_takes_the_worse_of_recency_and_confidence()
    test_compute_account_health_only_one_axis_present_still_works()
    test_compute_account_health_is_dados_insuficientes_never_verde_by_absence()
    test_compute_qbr_suggested_days_vermelha_is_always_urgent()
    test_compute_qbr_suggested_days_verde_aligns_to_real_renewal_date()
    test_compute_qbr_suggested_days_dados_insuficientes_treated_as_amarela()
    test_compute_qbr_suggested_days_two_or_more_open_signals_escalates_one_row()
    test_requires_status_change_justification_for_one_step_advance_is_false()
    test_requires_status_change_justification_for_two_or_more_stage_skip_is_true()
    test_requires_status_change_justification_going_backward_is_false()
    test_requires_status_change_justification_dismissed_reopen_is_always_true()
    test_requires_status_change_justification_advancing_to_dismissed_is_false()
    test_requires_status_change_justification_same_status_is_false()
    test_is_zombie_opportunity_flags_stagnation_beyond_30_days()
    test_is_zombie_opportunity_dismissed_is_never_zombie()
    test_is_zombie_opportunity_handles_naive_last_touch_at()
    test_is_aging_opportunity_only_flags_detected_beyond_sla()
    test_is_aging_opportunity_never_flags_non_detected_status()
    test_parse_aging_sla_days_falls_back_to_default_when_missing_or_invalid()
    test_parse_aging_sla_days_reads_valid_configured_value()
    print("OK — todos os testes do motor de oportunidades passaram")
