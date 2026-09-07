"""Testes do sinal de risco de single-thread (Fase H, módulo 3) — função
pura, sem sessão/rede/IA. Nunca chama update_opportunity_status."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import Contact, OutreachTouch
from core.opportunity_engine import (
    NO_ECONOMIC_BUYER_CONTACT, SINGLE_THREADED_RISK, compute_threading_risk_signal,
)

_NOW = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)


def _touch(contact_id: str | None, sent_at: datetime = _NOW) -> OutreachTouch:
    return OutreachTouch(
        opportunity_id="o1", rep_id="rep-1", contact_id=contact_id, channel="email",
        reason_label="x", sent_at=sent_at,
    )


def _contact(id_: str, seniority_tier: str | None = None) -> Contact:
    return Contact(id=id_, company_id="c1", name="Fulano", seniority_tier=seniority_tier)


def test_dismissed_status_never_signals():
    signal = compute_threading_risk_signal(
        status="dismissed", contacts=[_contact("k1", "decisor")],
        touches=[_touch("k1")], now=_NOW,
    )
    assert signal is None


def test_no_touches_at_all_is_insufficient_data_not_risk():
    signal = compute_threading_risk_signal(status="qualified", contacts=[], touches=[], now=_NOW)
    assert signal is None


def test_touches_without_any_contact_id_is_insufficient_data_not_risk():
    """Achado do Deal Strategist: contact_id é opcional — toques sem ele
    não podem virar "0 contato ativo" fabricado."""
    signal = compute_threading_risk_signal(
        status="qualified", contacts=[_contact("k1", "decisor")],
        touches=[_touch(None), _touch(None)], now=_NOW,
    )
    assert signal is None


def test_single_active_contact_flags_single_threaded_risk():
    signal = compute_threading_risk_signal(
        status="qualified", contacts=[_contact("k1", "decisor")],
        touches=[_touch("k1")], now=_NOW,
    )
    assert signal.reasons == (SINGLE_THREADED_RISK,)
    assert signal.active_contact_count == 1
    assert signal.has_active_decisor is True


def test_single_active_contact_without_decisor_flags_both_reasons():
    signal = compute_threading_risk_signal(
        status="qualified", contacts=[_contact("k1", "influenciador_tecnico")],
        touches=[_touch("k1")], now=_NOW,
    )
    assert set(signal.reasons) == {SINGLE_THREADED_RISK, NO_ECONOMIC_BUYER_CONTACT}


def test_two_active_contacts_with_decisor_never_signals():
    signal = compute_threading_risk_signal(
        status="qualified",
        contacts=[_contact("k1", "decisor"), _contact("k2", "operacional")],
        touches=[_touch("k1"), _touch("k2")], now=_NOW,
    )
    assert signal is None


def test_two_active_contacts_without_decisor_flags_only_no_economic_buyer():
    signal = compute_threading_risk_signal(
        status="qualified",
        contacts=[_contact("k1", "operacional"), _contact("k2", "influenciador_tecnico")],
        touches=[_touch("k1"), _touch("k2")], now=_NOW,
    )
    assert signal.reasons == (NO_ECONOMIC_BUYER_CONTACT,)
    assert signal.active_contact_count == 2


def test_touch_referencing_unknown_contact_id_never_crashes():
    """Módulo 1 não valida contact_id contra Contact real — a função
    precisa tolerar um id que não bate com nenhum Contact da lista."""
    signal = compute_threading_risk_signal(
        status="qualified", contacts=[_contact("k1", "decisor")],
        touches=[_touch("id-que-nao-existe")], now=_NOW,
    )
    assert signal.reasons == (SINGLE_THREADED_RISK, NO_ECONOMIC_BUYER_CONTACT)
    assert signal.has_active_decisor is False


def test_touch_outside_active_window_does_not_count():
    signal = compute_threading_risk_signal(
        status="qualified", contacts=[_contact("k1", "decisor")],
        touches=[_touch("k1", _NOW - timedelta(days=91))], now=_NOW,
    )
    assert signal is None  # sem toque na janela -> dado insuficiente, não risco


def test_touch_exactly_at_window_boundary_still_counts():
    signal = compute_threading_risk_signal(
        status="qualified", contacts=[_contact("k1", "decisor")],
        touches=[_touch("k1", _NOW - timedelta(days=90))], now=_NOW,
    )
    assert signal is not None


def test_all_active_statuses_except_dismissed_are_eligible():
    for status in ("detected", "qualified", "reviewed", "contacted", "opportunity"):
        signal = compute_threading_risk_signal(
            status=status, contacts=[_contact("k1", "decisor")], touches=[_touch("k1")], now=_NOW,
        )
        assert signal is not None, f"status {status} deveria ser elegível"


def test_custom_window_days_is_actually_used():
    signal = compute_threading_risk_signal(
        status="qualified", contacts=[_contact("k1", "decisor")],
        touches=[_touch("k1", _NOW - timedelta(days=10))], now=_NOW, window_days=5,
    )
    assert signal is None


if __name__ == "__main__":
    test_dismissed_status_never_signals()
    test_no_touches_at_all_is_insufficient_data_not_risk()
    test_touches_without_any_contact_id_is_insufficient_data_not_risk()
    test_single_active_contact_flags_single_threaded_risk()
    test_single_active_contact_without_decisor_flags_both_reasons()
    test_two_active_contacts_with_decisor_never_signals()
    test_two_active_contacts_without_decisor_flags_only_no_economic_buyer()
    test_touch_referencing_unknown_contact_id_never_crashes()
    test_touch_outside_active_window_does_not_count()
    test_touch_exactly_at_window_boundary_still_counts()
    test_all_active_statuses_except_dismissed_are_eligible()
    test_custom_window_days_is_actually_used()
    print("OK — todos os testes do sinal de risco de single-thread passaram")
