"""
Construção de `Company`/`Opportunity` a partir de um `PlaceSignal`
promovido (Fase E, módulo 6 `icp-wizard-ui`) — última etapa da esteira
discover() → score_place_signal() → select_promotions() → aqui.

Função pura (sem I/O) — quem persiste é a rota (`backend/routes_sync.py`),
mesma separação de responsabilidade do resto do projeto (motor decide,
repositório grava).
"""
from __future__ import annotations

from core.models import Company, Opportunity, SourceRef
from providers.google_maps import PlaceSignal

GEO_DISCOVERY_OPPORTUNITY_TYPE = "geo-discovery"


def build_discovery_records(
    signal: PlaceSignal, score: float, rep_id: str, company_size_hint: str | None,
    reference_product_id: str | None,
) -> tuple[Company, Opportunity]:
    company = Company(
        name=signal.name, is_customer=False, rep_id=rep_id, segment=company_size_hint,
        sources=[SourceRef(type="google_maps")],
    )
    opportunity = Opportunity(
        company_id=company.id, type=GEO_DISCOVERY_OPPORTUNITY_TYPE, product_id=reference_product_id,
        opportunity_score=score,
        evidence=[
            f"Sinal geográfico do Google Maps: categoria={signal.category or 'desconhecida'}, "
            f"status={signal.business_status or 'desconhecido'}, rating={signal.rating}, "
            f"avaliações={signal.review_count}."
        ],
        justification="Descoberta por prospecção geográfica (Google Maps).",
        sources=[SourceRef(type="google_maps")],
    )
    return company, opportunity
