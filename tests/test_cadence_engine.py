"""Testes do motor de cadência sugerida (Fase G, módulo 6) — função pura,
sem sessão/rede/IA."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import OutreachTouch
from core.opportunity_engine import (
    CADENCE_AWAITING_INTERVAL, CADENCE_DAILY_CAP_REACHED, CADENCE_EXHAUSTED, CadenceSuggestion,
    compute_next_suggested_touch,
)

_NOW = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)


def _touch(sent_at: datetime, opportunity_id: str = "o1") -> OutreachTouch:
    return OutreachTouch(opportunity_id=opportunity_id, rep_id="rep-1", channel="email", reason_label="x", sent_at=sent_at)


def test_customer_first_touch_due_immediately_at_detection():
    suggestion = compute_next_suggested_touch(
        is_customer=True, touches=[], first_detected_at=_NOW, now=_NOW, touches_today_for_rep=0,
    )
    assert suggestion == CadenceSuggestion(channel="email", reason_category="continuidade_uso_atual")


def test_customer_second_touch_awaits_seven_day_interval():
    first_touch_at = _NOW - timedelta(days=3)
    suggestion = compute_next_suggested_touch(
        is_customer=True, touches=[_touch(first_touch_at)], first_detected_at=_NOW - timedelta(days=3),
        now=_NOW, touches_today_for_rep=0,
    )
    assert suggestion == CADENCE_AWAITING_INTERVAL


def test_customer_second_touch_due_after_seven_days():
    first_touch_at = _NOW - timedelta(days=7)
    suggestion = compute_next_suggested_touch(
        is_customer=True, touches=[_touch(first_touch_at)], first_detected_at=first_touch_at,
        now=_NOW, touches_today_for_rep=0,
    )
    assert suggestion == CadenceSuggestion(channel="ligação", reason_category="gap_portfolio")


def test_customer_third_touch_due_seven_days_after_second():
    second_touch_at = _NOW - timedelta(days=7)
    first_touch_at = second_touch_at - timedelta(days=7)
    suggestion = compute_next_suggested_touch(
        is_customer=True, touches=[_touch(first_touch_at), _touch(second_touch_at)],
        first_detected_at=first_touch_at, now=_NOW, touches_today_for_rep=0,
    )
    assert suggestion == CadenceSuggestion(channel="linkedin", reason_category="prova_social_urgencia")


def test_customer_cadence_exhausted_after_three_touches():
    touches = [_touch(_NOW - timedelta(days=d)) for d in (14, 7, 0)]
    suggestion = compute_next_suggested_touch(
        is_customer=True, touches=touches, first_detected_at=_NOW - timedelta(days=14),
        now=_NOW, touches_today_for_rep=0,
    )
    assert suggestion == CADENCE_EXHAUSTED


def test_prospect_first_touch_due_immediately_at_detection():
    suggestion = compute_next_suggested_touch(
        is_customer=False, touches=[], first_detected_at=_NOW, now=_NOW, touches_today_for_rep=0,
    )
    assert suggestion == CadenceSuggestion(channel="email", reason_category="abertura_sinal")


def test_prospect_second_touch_due_after_four_days():
    first_touch_at = _NOW - timedelta(days=4)
    suggestion = compute_next_suggested_touch(
        is_customer=False, touches=[_touch(first_touch_at)], first_detected_at=first_touch_at,
        now=_NOW, touches_today_for_rep=0,
    )
    assert suggestion == CadenceSuggestion(channel="ligação", reason_category="reforco_angulo_novo")


def test_prospect_cadence_exhausted_after_two_touches():
    touches = [_touch(_NOW - timedelta(days=4)), _touch(_NOW)]
    suggestion = compute_next_suggested_touch(
        is_customer=False, touches=touches, first_detected_at=_NOW - timedelta(days=4),
        now=_NOW, touches_today_for_rep=0,
    )
    assert suggestion == CADENCE_EXHAUSTED


def test_daily_cap_reached_blocks_suggestion_even_when_touch_is_due():
    suggestion = compute_next_suggested_touch(
        is_customer=True, touches=[], first_detected_at=_NOW, now=_NOW, touches_today_for_rep=25, daily_cap=25,
    )
    assert suggestion == CADENCE_DAILY_CAP_REACHED


def test_daily_cap_check_happens_before_exhaustion_check():
    """Ordem importa: cota do rep é checada antes de qualquer coisa por
    oportunidade — mesmo uma cadência já esgotada não muda o resultado se o
    cap já estourou primeiro (achado de design, não achado de bug)."""
    touches = [_touch(_NOW - timedelta(days=d)) for d in (14, 7, 0)]
    suggestion = compute_next_suggested_touch(
        is_customer=True, touches=touches, first_detected_at=_NOW - timedelta(days=14),
        now=_NOW, touches_today_for_rep=25, daily_cap=25,
    )
    assert suggestion == CADENCE_DAILY_CAP_REACHED


def test_daily_cap_below_threshold_never_blocks():
    suggestion = compute_next_suggested_touch(
        is_customer=True, touches=[], first_detected_at=_NOW, now=_NOW, touches_today_for_rep=24, daily_cap=25,
    )
    assert suggestion == CadenceSuggestion(channel="email", reason_category="continuidade_uso_atual")


def test_custom_daily_cap_value_is_actually_used_not_just_the_default():
    """Achado da revisão de código: nenhum teste anterior provava que
    `daily_cap` como parâmetro realmente substitui o default — todos
    passavam 25 (igual ao `OUTREACH_DAILY_CAP`)."""
    blocked = compute_next_suggested_touch(
        is_customer=True, touches=[], first_detected_at=_NOW, now=_NOW, touches_today_for_rep=5, daily_cap=5,
    )
    assert blocked == CADENCE_DAILY_CAP_REACHED

    allowed = compute_next_suggested_touch(
        is_customer=True, touches=[], first_detected_at=_NOW, now=_NOW, touches_today_for_rep=4, daily_cap=5,
    )
    assert allowed == CadenceSuggestion(channel="email", reason_category="continuidade_uso_atual")


def test_out_of_order_touches_never_pick_the_wrong_anchor():
    """Achado da revisão de código: `list_outreach_touches` não garante
    ordem — a função ordena internamente por `sent_at`, então uma lista
    fora de ordem nunca escolhe silenciosamente o toque errado como "mais
    recente"."""
    older = _touch(_NOW - timedelta(days=7))
    newer = _touch(_NOW - timedelta(days=1))
    suggestion_in_order = compute_next_suggested_touch(
        is_customer=True, touches=[older, newer], first_detected_at=_NOW - timedelta(days=7),
        now=_NOW, touches_today_for_rep=0,
    )
    suggestion_out_of_order = compute_next_suggested_touch(
        is_customer=True, touches=[newer, older], first_detected_at=_NOW - timedelta(days=7),
        now=_NOW, touches_today_for_rep=0,
    )
    assert suggestion_in_order == suggestion_out_of_order == CADENCE_AWAITING_INTERVAL


def test_customer_and_prospect_cadences_never_share_a_category():
    """Garante estruturalmente que nenhuma categoria se repete DENTRO da
    mesma cadência (a garantia central pedida pelo Outbound Strategist)."""
    from core.opportunity_engine import _CUSTOMER_CADENCE, _PROSPECT_CADENCE
    customer_categories = [c for _, _, c in _CUSTOMER_CADENCE]
    prospect_categories = [c for _, _, c in _PROSPECT_CADENCE]
    assert len(customer_categories) == len(set(customer_categories))
    assert len(prospect_categories) == len(set(prospect_categories))


if __name__ == "__main__":
    test_customer_first_touch_due_immediately_at_detection()
    test_customer_second_touch_awaits_seven_day_interval()
    test_customer_second_touch_due_after_seven_days()
    test_customer_third_touch_due_seven_days_after_second()
    test_customer_cadence_exhausted_after_three_touches()
    test_prospect_first_touch_due_immediately_at_detection()
    test_prospect_second_touch_due_after_four_days()
    test_prospect_cadence_exhausted_after_two_touches()
    test_daily_cap_reached_blocks_suggestion_even_when_touch_is_due()
    test_daily_cap_check_happens_before_exhaustion_check()
    test_daily_cap_below_threshold_never_blocks()
    test_custom_daily_cap_value_is_actually_used_not_just_the_default()
    test_out_of_order_touches_never_pick_the_wrong_anchor()
    test_customer_and_prospect_cadences_never_share_a_category()
    print("OK — todos os testes do motor de cadência passaram")
