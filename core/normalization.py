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
        # last_activity_at é um sinal de recência (Fase C, Fatia 4a) — ao
        # contrário dos campos acima, precisa refletir o fetch mais recente,
        # nunca congelar no primeiro sync (senão o sinal de "momentum" nunca
        # se move).
        "last_activity_at": other.last_activity_at or base.last_activity_at,
        # Fase A — atributos de perfil (Salesforce Architect consultado):
        # ao contrário de last_activity_at (sinal de momentum, sempre pega
        # o mais recente), estes não mudam com frequência — primeiro valor
        # não-nulo vence, mesmo padrão de legal_name/website.
        "industry": base.industry or other.industry,
        # achado da revisão de código: `or` é errado pra numérico — 0 é
        # falsy em Python, então annual_revenue=0.0 (empresa pré-receita)
        # ou employee_count=0 em base seria sobrescrito por other mesmo
        # sendo um valor real e intencional, não "ausência de dado".
        "annual_revenue": base.annual_revenue if base.annual_revenue is not None else other.annual_revenue,
        "employee_count": base.employee_count if base.employee_count is not None else other.employee_count,
        "address": base.address or other.address,
        # Fase F, módulo 4 — mesmo tratamento de annual_revenue/employee_count
        # (numérico, "or" trataria 0.0 real como ausência). fetch_companies()
        # nunca popula este campo (só o split de mapeamento, módulo 4, escreve
        # nele depois do merge) — sem isso, resincronizar zeraria o valor já
        # promovido de um campo mapeado a cada rodada.
        "deal_size_hint": base.deal_size_hint if base.deal_size_hint is not None else other.deal_size_hint,
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
