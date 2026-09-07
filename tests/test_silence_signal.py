"""Testes do sinal de silêncio (Fase G, módulo 8) — função pura,
sem sessão/rede/IA. Nunca chama update_opportunity_status."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import OutreachTouch
from core.opportunity_engine import (
    SILENCE_CADENCE_EXHAUSTED, SILENCE_NEVER_CONTACTED, compute_silence_signal,
)

_NOW = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
_SLA_DAYS = 7


def _touch(sent_at: datetime, opportunity_id: str = "o1") -> OutreachTouch:
    return OutreachTouch(opportunity_id=opportunity_id, rep_id="rep-1", channel="email", reason_label="x", sent_at=sent_at)


def test_no_signal_when_status_is_past_early_stage():
    for status in ("reviewed", "contacted", "opportunity", "dismissed"):
        signal = compute_silence_signal(
            status=status, touches=[], first_detected_at=_NOW - timedelta(days=30),
            is_customer=True, now=_NOW, sla_days=_SLA_DAYS,
        )
        assert signal is None


def test_never_contacted_below_sla_is_not_silent():
    signal = compute_silence_signal(
        status="detected", touches=[], first_detected_at=_NOW - timedelta(days=3),
        is_customer=True, now=_NOW, sla_days=_SLA_DAYS,
    )
    assert signal is None


def test_never_contacted_exactly_at_sla_boundary_is_not_yet_silent():
    """`> sla_days`, nunca `>=` — mesma semântica estrita de
    is_aging_opportunity (achado da revisão de código: nenhum teste antigo
    provava o limite exato)."""
    signal = compute_silence_signal(
        status="detected", touches=[], first_detected_at=_NOW - timedelta(days=_SLA_DAYS),
        is_customer=True, now=_NOW, sla_days=_SLA_DAYS,
    )
    assert signal is None


def test_never_contacted_past_sla_is_silent_in_detected():
    signal = compute_silence_signal(
        status="detected", touches=[], first_detected_at=_NOW - timedelta(days=8),
        is_customer=True, now=_NOW, sla_days=_SLA_DAYS,
    )
    assert signal.reason == SILENCE_NEVER_CONTACTED
    assert signal.days_silent == 8


def test_never_contacted_past_sla_is_silent_in_qualified_too():
    """is_aging_opportunity só cobre 'detected' — compute_silence_signal
    cobre 'qualified' também (achado da consulta ao Sales Coach: mesmo fato
    de "sentou sem ninguém mexer", um estágio adiante)."""
    signal = compute_silence_signal(
        status="qualified", touches=[], first_detected_at=_NOW - timedelta(days=8),
        is_customer=True, now=_NOW, sla_days=_SLA_DAYS,
    )
    assert signal.reason == SILENCE_NEVER_CONTACTED


def test_touched_but_cadence_not_yet_exhausted_is_not_silent():
    signal = compute_silence_signal(
        status="qualified", touches=[_touch(_NOW - timedelta(days=20))],
        first_detected_at=_NOW - timedelta(days=20), is_customer=True, now=_NOW, sla_days=_SLA_DAYS,
    )
    assert signal is None


def test_customer_cadence_exhausted_within_buffer_is_not_silent():
    touches = [_touch(_NOW - timedelta(days=d)) for d in (14, 7, 2)]
    signal = compute_silence_signal(
        status="qualified", touches=touches, first_detected_at=_NOW - timedelta(days=14),
        is_customer=True, now=_NOW, sla_days=_SLA_DAYS,
    )
    assert signal is None


def test_customer_cadence_exhausted_exactly_at_buffer_boundary_is_not_yet_silent():
    touches = [_touch(_NOW - timedelta(days=d)) for d in (17, 10, 3)]
    signal = compute_silence_signal(
        status="qualified", touches=touches, first_detected_at=_NOW - timedelta(days=17),
        is_customer=True, now=_NOW, sla_days=_SLA_DAYS,
    )
    assert signal is None


def test_customer_cadence_exhausted_past_three_day_buffer_is_silent():
    touches = [_touch(_NOW - timedelta(days=d)) for d in (18, 11, 4)]
    signal = compute_silence_signal(
        status="qualified", touches=touches, first_detected_at=_NOW - timedelta(days=18),
        is_customer=True, now=_NOW, sla_days=_SLA_DAYS,
    )
    assert signal.reason == SILENCE_CADENCE_EXHAUSTED
    assert signal.days_silent == 4


def test_prospect_cadence_exhausted_past_two_day_buffer_is_silent():
    touches = [_touch(_NOW - timedelta(days=d)) for d in (7, 3)]
    signal = compute_silence_signal(
        status="detected", touches=touches, first_detected_at=_NOW - timedelta(days=7),
        is_customer=False, now=_NOW, sla_days=_SLA_DAYS,
    )
    assert signal.reason == SILENCE_CADENCE_EXHAUSTED
    assert signal.days_silent == 3


def test_prospect_cadence_exhausted_within_two_day_buffer_is_not_silent():
    touches = [_touch(_NOW - timedelta(days=d)) for d in (7, 1)]
    signal = compute_silence_signal(
        status="detected", touches=touches, first_detected_at=_NOW - timedelta(days=7),
        is_customer=False, now=_NOW, sla_days=_SLA_DAYS,
    )
    assert signal is None


def test_out_of_order_touches_never_pick_the_wrong_last_touch():
    older = _touch(_NOW - timedelta(days=18))
    middle = _touch(_NOW - timedelta(days=11))
    newer = _touch(_NOW - timedelta(days=4))
    in_order = compute_silence_signal(
        status="qualified", touches=[older, middle, newer], first_detected_at=_NOW - timedelta(days=18),
        is_customer=True, now=_NOW, sla_days=_SLA_DAYS,
    )
    out_of_order = compute_silence_signal(
        status="qualified", touches=[newer, older, middle], first_detected_at=_NOW - timedelta(days=18),
        is_customer=True, now=_NOW, sla_days=_SLA_DAYS,
    )
    assert in_order == out_of_order == compute_silence_signal(
        status="qualified", touches=[older, middle, newer], first_detected_at=_NOW - timedelta(days=18),
        is_customer=True, now=_NOW, sla_days=_SLA_DAYS,
    )


if __name__ == "__main__":
    test_no_signal_when_status_is_past_early_stage()
    test_never_contacted_below_sla_is_not_silent()
    test_never_contacted_exactly_at_sla_boundary_is_not_yet_silent()
    test_never_contacted_past_sla_is_silent_in_detected()
    test_never_contacted_past_sla_is_silent_in_qualified_too()
    test_touched_but_cadence_not_yet_exhausted_is_not_silent()
    test_customer_cadence_exhausted_within_buffer_is_not_silent()
    test_customer_cadence_exhausted_exactly_at_buffer_boundary_is_not_yet_silent()
    test_customer_cadence_exhausted_past_three_day_buffer_is_silent()
    test_prospect_cadence_exhausted_past_two_day_buffer_is_silent()
    test_prospect_cadence_exhausted_within_two_day_buffer_is_not_silent()
    test_out_of_order_touches_never_pick_the_wrong_last_touch()
    print("OK — todos os testes do sinal de silêncio passaram")
