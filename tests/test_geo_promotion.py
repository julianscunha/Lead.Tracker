"""Smoke tests da trava anti-spam de prospecção geográfica (Fase E,
módulo 5 `anti-spam-promotion-gate`)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.geo_promotion import (
    parse_promotion_daily_cap, parse_promotion_min_score, select_promotions,
)
from providers.google_maps import PlaceSignal

_MIN_SCORE = 0.75
_DAILY_CAP = 20


def _signal(place_id: str) -> PlaceSignal:
    return PlaceSignal(
        place_id=place_id, name=f"Lugar {place_id}", category="car_dealer", business_status="OPERATIONAL",
        rating=None, review_count=0, formatted_address=None,
    )


def test_parse_promotion_min_score_falls_back_to_default_when_missing_or_invalid():
    assert parse_promotion_min_score({}) == 0.75
    assert parse_promotion_min_score({"GEO_PROMOTION_MIN_SCORE": "abc"}) == 0.75
    assert parse_promotion_min_score({"GEO_PROMOTION_MIN_SCORE": "1.5"}) == 0.75  # fora de 0-1
    assert parse_promotion_min_score({"GEO_PROMOTION_MIN_SCORE": "-0.1"}) == 0.75


def test_parse_promotion_min_score_reads_valid_configured_value():
    assert parse_promotion_min_score({"GEO_PROMOTION_MIN_SCORE": "0.8"}) == 0.8


def test_parse_promotion_min_score_accepts_both_range_boundaries():
    assert parse_promotion_min_score({"GEO_PROMOTION_MIN_SCORE": "0.0"}) == 0.0
    assert parse_promotion_min_score({"GEO_PROMOTION_MIN_SCORE": "1.0"}) == 1.0


def test_parse_promotion_daily_cap_falls_back_to_default_when_missing_or_invalid():
    assert parse_promotion_daily_cap({}) == 20
    assert parse_promotion_daily_cap({"GEO_PROMOTION_DAILY_CAP": "abc"}) == 20
    assert parse_promotion_daily_cap({"GEO_PROMOTION_DAILY_CAP": "0"}) == 20
    assert parse_promotion_daily_cap({"GEO_PROMOTION_DAILY_CAP": "-5"}) == 20


def test_parse_promotion_daily_cap_reads_valid_configured_value():
    assert parse_promotion_daily_cap({"GEO_PROMOTION_DAILY_CAP": "50"}) == 50


def test_score_below_minimum_is_always_rejected_never_promoted_or_deferred():
    scored = [(_signal("a"), 0.5), (_signal("b"), 0.74)]
    decision = select_promotions(scored, min_score=_MIN_SCORE, daily_cap=_DAILY_CAP, already_promoted_today=0)
    assert decision.promoted == []
    assert decision.deferred == []
    assert len(decision.rejected) == 2


def test_none_score_discarded_by_scoring_layer_is_rejected_never_consumes_quota():
    scored = [(_signal("a"), None), (_signal("b"), 0.9)]
    decision = select_promotions(scored, min_score=_MIN_SCORE, daily_cap=_DAILY_CAP, already_promoted_today=0)
    assert len(decision.rejected) == 1
    assert len(decision.promoted) == 1


def test_score_exactly_at_minimum_is_eligible_inclusive_boundary():
    scored = [(_signal("a"), _MIN_SCORE)]
    decision = select_promotions(scored, min_score=_MIN_SCORE, daily_cap=_DAILY_CAP, already_promoted_today=0)
    assert len(decision.promoted) == 1
    assert decision.rejected == []


def test_eligible_signals_within_quota_are_all_promoted():
    scored = [(_signal("a"), 0.8), (_signal("b"), 0.9)]
    decision = select_promotions(scored, min_score=_MIN_SCORE, daily_cap=_DAILY_CAP, already_promoted_today=0)
    assert len(decision.promoted) == 2
    assert decision.deferred == []


def test_search_never_blocked_by_exhausted_quota_excess_becomes_deferred_not_rejected():
    """Achado da consulta ao Outbound Strategist: a busca nunca é
    bloqueada — tudo é classificado, o excedente da cota vira `deferred`
    (nunca `rejected`, que é reservado pra score insuficiente)."""
    scored = [(_signal(str(i)), 0.9) for i in range(5)]
    decision = select_promotions(scored, min_score=_MIN_SCORE, daily_cap=_DAILY_CAP, already_promoted_today=18)
    assert len(decision.promoted) == 2  # só 2 de cota restante (20-18)
    assert len(decision.deferred) == 3
    assert decision.rejected == []


def test_quota_already_fully_consumed_defers_everything_eligible():
    scored = [(_signal("a"), 0.9)]
    decision = select_promotions(scored, min_score=_MIN_SCORE, daily_cap=_DAILY_CAP, already_promoted_today=20)
    assert decision.promoted == []
    assert len(decision.deferred) == 1


def test_already_promoted_today_above_cap_never_produces_negative_quota_crash():
    """Estado inconsistente (ex.: cap reduzido depois de já ter promovido
    mais que o novo limite) nunca gera quota negativa nem erro."""
    scored = [(_signal("a"), 0.9)]
    decision = select_promotions(scored, min_score=_MIN_SCORE, daily_cap=_DAILY_CAP, already_promoted_today=999)
    assert decision.promoted == []
    assert len(decision.deferred) == 1


def test_promotion_prioritizes_highest_score_first_when_quota_is_limited():
    signals_by_score = {"low": 0.76, "high": 0.95, "mid": 0.85}
    scored = [(_signal(pid), score) for pid, score in signals_by_score.items()]
    decision = select_promotions(scored, min_score=_MIN_SCORE, daily_cap=_DAILY_CAP, already_promoted_today=19)
    assert len(decision.promoted) == 1
    assert decision.promoted[0].place_id == "high"
    assert {s.place_id for s in decision.deferred} == {"mid", "low"}


if __name__ == "__main__":
    test_parse_promotion_min_score_falls_back_to_default_when_missing_or_invalid()
    test_parse_promotion_min_score_reads_valid_configured_value()
    test_parse_promotion_min_score_accepts_both_range_boundaries()
    test_parse_promotion_daily_cap_falls_back_to_default_when_missing_or_invalid()
    test_parse_promotion_daily_cap_reads_valid_configured_value()
    test_score_below_minimum_is_always_rejected_never_promoted_or_deferred()
    test_score_exactly_at_minimum_is_eligible_inclusive_boundary()
    test_none_score_discarded_by_scoring_layer_is_rejected_never_consumes_quota()
    test_eligible_signals_within_quota_are_all_promoted()
    test_search_never_blocked_by_exhausted_quota_excess_becomes_deferred_not_rejected()
    test_quota_already_fully_consumed_defers_everything_eligible()
    test_already_promoted_today_above_cap_never_produces_negative_quota_crash()
    test_promotion_prioritizes_highest_score_first_when_quota_is_limited()
    print("OK — todos os testes de trava anti-spam geográfica passaram")
