"""
Coleta e normalização.

Recebe Company vindas de providers (modelo comum) e as consolida em
uma única empresa por domínio/nome — nunca duplica por ter aparecido em fontes
diferentes.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from core.models import Company, SourceRef


def normalize_name(name: str) -> str:
    """Chave de comparação de nome — não é o nome exibido, só usado para casar registros."""
    return re.sub(r"\s+", " ", name.strip().lower())


def normalize_domain(website: str | None) -> str | None:
    """Extrai o domínio nu de uma URL (sem protocolo, www ou path) para comparação."""
    if not website:
        return None
    candidate = website.strip().lower()
    if not re.match(r"^[a-z]+://", candidate):
        candidate = f"//{candidate}"
    host = urlparse(candidate).netloc or urlparse(candidate).path
    host = host.split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host or None


def dedup_key(company: Company) -> str:
    """Chave de deduplicação: domínio quando disponível, senão nome normalizado.
    Pública — backend/sync.py usa pra reconciliar empresa vinda de uma fonte
    contra empresa já persistida de outra fonte, sem duplicar."""
    domain = normalize_domain(company.website)
    return f"domain:{domain}" if domain else f"name:{normalize_name(company.name)}"


def _merge_sources(existing: list[SourceRef], incoming: list[SourceRef]) -> list[SourceRef]:
    by_type: dict[str, SourceRef] = {s.type: s for s in existing}
    for src in incoming:
        current = by_type.get(src.type)
        if current is None or src.confidence > current.confidence:
            by_type[src.type] = src
    return list(by_type.values())


def merge_pair(base: Company, other: Company) -> Company:
    """Mescla `other` em `base`, preservando o `id`/identidade de `base` —
    usado quando `base` já está persistido (backend/sync.py) e não pode
    trocar de id sem quebrar Contact/Opportunity que o referenciam."""
    return base.model_copy(update={
        "legal_name": base.legal_name or other.legal_name,
        "website": base.website or other.website,
        "is_customer": base.is_customer or other.is_customer,
        "customer_status": base.customer_status or other.customer_status,
        "sources": _merge_sources(base.sources, other.sources),
    })


def merge_companies(companies: list[Company]) -> list[Company]:
    """
    Consolida uma lista de Company (potencialmente vindas de providers
    diferentes) em uma empresa única por domínio/nome. Preserva proveniência
    (sources) de todas as origens mescladas.
    """
    merged: dict[str, Company] = {}
    for company in companies:
        key = dedup_key(company)
        if key in merged:
            merged[key] = merge_pair(merged[key], company)
        else:
            merged[key] = company
    return list(merged.values())
