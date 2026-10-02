"""Fase Q — completar porte e setor das empresas pela API de enriquecimento configurada.

`POST /enrichment/run` roda sob demanda (nunca no /sync), segura o SYNC_LOCK (grava a linha inteira da
empresa) e reaproveita a reconciliação da Fase N: campo vazio é preenchido com origem `enrichment`;
valor de outra fonte (CRM/manual/CSV) abre conflito e o atual é mantido; `mapping` nunca é contestado."""
from __future__ import annotations

import time

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend import routes_settings
from backend.db_session import session_factory
from backend.http_errors import raise_http
from backend.sync import SYNC_LOCK
from core.config import load_env
from core.errors import DomainError, ErrorCategory
from core.normalization import reconcile
from core.repository import list_companies, record_reconciliation, rejected_conflict_keys, save_company
from providers.base import ProviderError
from providers.enrichment_http import SOURCE_ID, EnrichmentHttpProvider, eligible_domain

router = APIRouter(tags=["lead_tracker-enrichment"])

FIELDS = ("industry", "employee_count")
BATCH_DEADLINE = 120.0  # prazo total do lote; cada chamada tem o seu (10 s)


class EnrichmentRunOut(BaseModel):
    enriquecidas: int
    sem_dado: int
    conflitos: int
    erros: list[str]


def _needs(company) -> bool:
    return not (company.industry or "").strip() or company.employee_count is None


@router.post("/enrichment/run")
async def run_enrichment(limit: int = Query(default=50, ge=1, le=200)) -> EnrichmentRunOut:
    env = load_env(routes_settings._ENV_PATH)
    if env.get("ENRICHMENT_ENABLED", "").strip().lower() != "true":
        raise_http(DomainError(
            ErrorCategory.CONFIGURATION, "O enriquecimento de empresas está desligado.",
            "Ligue e configure a fonte em Entrada de dados > Enriquecimento de empresas.",
        ))
    try:
        provider = EnrichmentHttpProvider.from_env(env)
    except ProviderError as exc:
        raise_http(exc)

    if SYNC_LOCK.locked():  # lote longo e sync disputam a mesma trava: não enfileira cliques repetidos
        raise_http(DomainError(
            ErrorCategory.INTEGRATION,
            "Já há uma atualização de dados em andamento.", "Aguarde terminar e tente de novo.",
        ))
    out = EnrichmentRunOut(enriquecidas=0, sem_dado=0, conflitos=0, erros=[])
    started = time.monotonic()
    async with SYNC_LOCK, session_factory() as session:
        candidates = sorted(
            (c for c in await list_companies(session) if _needs(c) and eligible_domain(c.website)),
            key=lambda c: c.name.lower(),
        )[:limit]
        rejected_by_company = await rejected_conflict_keys(session)
        for index, company in enumerate(candidates):
            if time.monotonic() - started > BATCH_DEADLINE:
                out.erros.append(f"O tempo do lote acabou; {len(candidates) - index} empresa(s) ficaram para a próxima vez.")
                break
            try:
                partial = await provider.enrich(company.website)
            except ProviderError as exc:
                if exc.category == ErrorCategory.AUTHENTICATION:
                    out.erros.append(str(exc))
                    break  # chave recusada: insistir em todas as outras só gera bloqueio
                out.erros.append(f"{company.name}: {exc}")
                continue
            if partial is None or (partial.industry is None and partial.employee_count is None):
                out.sem_dado += 1
                continue
            partial = partial.model_copy(update={"name": company.name})
            result = reconcile(
                company, partial, SOURCE_ID, rejected_by_company.get(company.id, frozenset()), fields=FIELDS,
            )
            filled = any(getattr(result.company, f) != getattr(company, f) for f in FIELDS)
            if not (filled or result.changes or result.conflicts):
                out.sem_dado += 1
                continue
            await save_company(session, result.company)
            if result.changes or result.conflicts:
                await record_reconciliation(session, company.id, result.changes, result.conflicts, SOURCE_ID)
            out.conflitos += len(result.conflicts)
            if filled:
                out.enriquecidas += 1
    return out
