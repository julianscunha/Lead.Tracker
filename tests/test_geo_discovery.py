"""Smoke tests da construção de Company/Opportunity a partir de sinal
promovido (Fase E, módulo 6 `icp-wizard-ui`)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.geo_discovery import GEO_DISCOVERY_OPPORTUNITY_TYPE, build_discovery_records
from providers.google_maps import PlaceSignal


def _signal() -> PlaceSignal:
    return PlaceSignal(
        place_id="p1", name="Concessionária Exemplo", category="car_dealer", business_status="OPERATIONAL",
        rating=4.5, review_count=30, formatted_address="Rua Exemplo, 123",
    )


def test_company_is_never_marked_as_customer():
    company, _ = build_discovery_records(_signal(), 0.9, "rep-1", "media", "prod-1")
    assert company.is_customer is False


def test_company_gets_rep_and_segment_from_wizard_input():
    company, _ = build_discovery_records(_signal(), 0.9, "rep-1", "media", "prod-1")
    assert company.rep_id == "rep-1"
    assert company.segment == "media"


def test_company_and_opportunity_are_tagged_with_google_maps_source():
    company, opportunity = build_discovery_records(_signal(), 0.9, "rep-1", "media", "prod-1")
    assert company.sources[0].type == "google_maps"
    assert opportunity.sources[0].type == "google_maps"


def test_opportunity_links_to_the_company_just_built():
    company, opportunity = build_discovery_records(_signal(), 0.9, "rep-1", "media", "prod-1")
    assert opportunity.company_id == company.id


def test_opportunity_carries_the_score_and_reference_product():
    _, opportunity = build_discovery_records(_signal(), 0.87, "rep-1", "media", "prod-1")
    assert opportunity.opportunity_score == 0.87
    assert opportunity.product_id == "prod-1"
    assert opportunity.type == GEO_DISCOVERY_OPPORTUNITY_TYPE


def test_opportunity_starts_in_detected_status_like_any_other():
    from core.models import OpportunityStatus
    _, opportunity = build_discovery_records(_signal(), 0.9, "rep-1", "media", "prod-1")
    assert opportunity.status == OpportunityStatus.DETECTED


def test_evidence_never_empty_carries_the_raw_signal():
    _, opportunity = build_discovery_records(_signal(), 0.9, "rep-1", "media", "prod-1")
    assert opportunity.evidence
    assert "car_dealer" in opportunity.evidence[0]


def test_reference_product_id_can_be_none():
    _, opportunity = build_discovery_records(_signal(), 0.9, "rep-1", None, None)
    assert opportunity.product_id is None


if __name__ == "__main__":
    test_company_is_never_marked_as_customer()
    test_company_gets_rep_and_segment_from_wizard_input()
    test_company_and_opportunity_are_tagged_with_google_maps_source()
    test_opportunity_links_to_the_company_just_built()
    test_opportunity_carries_the_score_and_reference_product()
    test_opportunity_starts_in_detected_status_like_any_other()
    test_evidence_never_empty_carries_the_raw_signal()
    test_reference_product_id_can_be_none()
    print("OK — todos os testes de construção de descoberta geográfica passaram")
