"""Smoke tests das regras determinísticas de pontuação de sinal
geográfico (Fase E, módulo 4 `geo-scoring-rules`)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.geo_scoring import category_matches, score_place_signal
from providers.google_maps import PlaceSignal


def _signal(**kwargs) -> PlaceSignal:
    defaults = dict(
        place_id="p1", name="Lugar", category="car_dealer", business_status="OPERATIONAL",
        rating=None, review_count=0, formatted_address=None,
    )
    defaults.update(kwargs)
    return PlaceSignal(**defaults)


def test_category_matches_case_insensitive():
    assert category_matches("Car_Dealer", "car_dealer") is True
    assert category_matches("car_dealer", "restaurant") is False


def test_category_matches_none_when_either_side_missing():
    assert category_matches(None, "car_dealer") is False
    assert category_matches("car_dealer", None) is False


def test_category_matches_empty_string_never_matches_anything():
    assert category_matches("", "") is False
    assert category_matches("", "car_dealer") is False
    assert category_matches("car_dealer", "") is False


def test_business_status_unspecified_is_never_discarded_same_as_none():
    """Achado da revisão de código: BUSINESS_STATUS_UNSPECIFIED é um
    valor real do enum da Places API — significa "não sabemos", nunca
    "sabemos que fechou". Tratar como fechado descartaria lugares só
    porque o Google não tem certeza do status."""
    signal = _signal(business_status="BUSINESS_STATUS_UNSPECIFIED")
    assert score_place_signal(signal, "car_dealer") is not None


def test_closed_permanently_is_always_discarded_regardless_of_other_signals():
    signal = _signal(business_status="CLOSED_PERMANENTLY", category="car_dealer", rating=5.0, review_count=500)
    assert score_place_signal(signal, "car_dealer") is None


def test_closed_temporarily_is_also_discarded():
    signal = _signal(business_status="CLOSED_TEMPORARILY")
    assert score_place_signal(signal, "car_dealer") is None


def test_operational_and_none_status_are_never_discarded():
    assert score_place_signal(_signal(business_status="OPERATIONAL"), "car_dealer") is not None
    assert score_place_signal(_signal(business_status=None), "car_dealer") is not None


def test_category_match_scores_higher_than_mismatch_regardless_of_reviews():
    """Hierarquia nunca se inverte: o pior caso de "bate" (sem reviews)
    precisa ficar acima do melhor caso de "não bate" (reviews máximos)."""
    matched_no_reviews = score_place_signal(_signal(category="car_dealer", rating=None, review_count=0), "car_dealer")
    mismatched_max_reviews = score_place_signal(_signal(category="restaurant", rating=5.0, review_count=1000), "car_dealer")
    assert matched_no_reviews > mismatched_max_reviews


def test_category_mismatch_is_low_score_never_discard():
    signal = _signal(category="restaurant")
    score = score_place_signal(signal, "car_dealer")
    assert score is not None
    assert score < 0.5


def test_no_icp_category_configured_yet_is_neutral():
    signal = _signal(category="car_dealer", rating=None, review_count=0)
    assert score_place_signal(signal, None) == 0.5


def test_missing_rating_and_reviews_are_neutral_never_penalized():
    with_data = score_place_signal(_signal(category="car_dealer", rating=3.0, review_count=10), "car_dealer")
    without_data = score_place_signal(_signal(category="car_dealer", rating=None, review_count=0), "car_dealer")
    assert without_data < with_data
    # Sem dado nenhum, o score é exatamente a base (0.7) — nem soma nem subtrai.
    assert without_data == 0.7


def test_rating_bonus_scales_from_1_to_5():
    low_rating = score_place_signal(_signal(category="car_dealer", rating=1.0, review_count=0), "car_dealer")
    high_rating = score_place_signal(_signal(category="car_dealer", rating=5.0, review_count=0), "car_dealer")
    assert low_rating == 0.7  # rating mínimo (1.0) não dá bônus nenhum
    assert high_rating == 0.7 + 0.15  # rating máximo (5.0) dá o bônus cheio


def test_review_count_bonus_caps_at_50_reviews():
    at_cap = score_place_signal(_signal(category="car_dealer", rating=None, review_count=50), "car_dealer")
    above_cap = score_place_signal(_signal(category="car_dealer", rating=None, review_count=5000), "car_dealer")
    assert at_cap == above_cap == 0.7 + 0.15


def test_score_never_exceeds_1_0():
    signal = _signal(category="car_dealer", rating=5.0, review_count=1000)
    assert score_place_signal(signal, "car_dealer") == 1.0


def test_out_of_range_rating_is_clamped_never_negative_or_above_max_bonus():
    """rating fora de 1.0-5.0 (dado inesperado de uma futura mudança de
    API) nunca produz bônus negativo nem acima do máximo de 0.15."""
    below_range = score_place_signal(_signal(category="car_dealer", rating=0.0, review_count=0), "car_dealer")
    above_range = score_place_signal(_signal(category="car_dealer", rating=6.0, review_count=0), "car_dealer")
    assert below_range == 0.7  # clamp no piso — nunca vira 0.7 - algo
    assert above_range == 0.7 + 0.15  # clamp no teto — nunca passa do bônus máximo


if __name__ == "__main__":
    test_category_matches_case_insensitive()
    test_category_matches_none_when_either_side_missing()
    test_category_matches_empty_string_never_matches_anything()
    test_business_status_unspecified_is_never_discarded_same_as_none()
    test_closed_permanently_is_always_discarded_regardless_of_other_signals()
    test_closed_temporarily_is_also_discarded()
    test_operational_and_none_status_are_never_discarded()
    test_category_match_scores_higher_than_mismatch_regardless_of_reviews()
    test_category_mismatch_is_low_score_never_discard()
    test_no_icp_category_configured_yet_is_neutral()
    test_missing_rating_and_reviews_are_neutral_never_penalized()
    test_rating_bonus_scales_from_1_to_5()
    test_review_count_bonus_caps_at_50_reviews()
    test_score_never_exceeds_1_0()
    test_out_of_range_rating_is_clamped_never_negative_or_above_max_bonus()
    print("OK — todos os testes de pontuação geográfica passaram")
