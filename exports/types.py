"""Tipos de exportação — linha já resolvida (nomes, não IDs), pronta
para PDF/Excel. Desacoplado de core.models pra exports não depender de como o
domínio guarda vendor_id/product_id (resolução é responsabilidade de quem chama)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OpportunityExportRow:
    company_name: str
    is_customer: bool
    opportunity_score: float | None
    financial_potential: float | None
    product: str | None
    service: str | None
    priority: str
    sources: list[str] = field(default_factory=list)
