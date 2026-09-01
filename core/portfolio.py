"""
Portfólio da empresa usuária.

Regras determinísticas de CRUD e sincronização de portfólio — a extração via
website/IA é feita em outra camada (coleta/normalização e IA); aqui só o
resultado validado é aplicado. Nunca altera o portfólio existente sem uma
escolha explícita de modo (Adicionar/Sobrescrever).
"""
from __future__ import annotations

from typing import Literal

from core.models import Portfolio

MergeMode = Literal["add", "overwrite"]


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def add_product(portfolio: Portfolio, product_id: str) -> Portfolio:
    return portfolio.model_copy(update={"product_ids": _dedup([*portfolio.product_ids, product_id])})


def remove_product(portfolio: Portfolio, product_id: str) -> Portfolio:
    return portfolio.model_copy(update={"product_ids": [p for p in portfolio.product_ids if p != product_id]})


def add_service(portfolio: Portfolio, service_id: str) -> Portfolio:
    return portfolio.model_copy(update={"service_ids": _dedup([*portfolio.service_ids, service_id])})


def remove_service(portfolio: Portfolio, service_id: str) -> Portfolio:
    return portfolio.model_copy(update={"service_ids": [s for s in portfolio.service_ids if s != service_id]})


def merge_portfolio(existing: Portfolio | None, candidate: Portfolio, mode: MergeMode) -> Portfolio:
    """
    Aplica um portfólio candidato (validado, vindo de coleta/IA) ao existente.

    - "add": mantém o conteúdo atual e acrescenta itens novos do candidato (dedup).
    - "overwrite": substitui o conteúdo do existente pelo do candidato.

    Sem `existing` (primeira sincronização), o resultado é sempre o candidato.
    """
    if existing is None:
        return candidate

    if mode == "overwrite":
        return existing.model_copy(update={
            "vendor_ids": candidate.vendor_ids,
            "product_ids": candidate.product_ids,
            "service_ids": candidate.service_ids,
            "relations": candidate.relations,
            "notes": candidate.notes,
        })

    return existing.model_copy(update={
        "vendor_ids": _dedup([*existing.vendor_ids, *candidate.vendor_ids]),
        "product_ids": _dedup([*existing.product_ids, *candidate.product_ids]),
        "service_ids": _dedup([*existing.service_ids, *candidate.service_ids]),
        "relations": existing.relations + [r for r in candidate.relations if r not in existing.relations],
        "notes": candidate.notes or existing.notes,
    })
