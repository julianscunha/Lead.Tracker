"""
Mapeamento único DomainError -> HTTPException, compartilhado por todas as
rotas do módulo (CLAUDE.md 'todo DomainError vira HTTPException pela mesma
tabela categoria->status, não uma regra por rota').
"""
from __future__ import annotations

from fastapi import HTTPException

from core.errors import DomainError, ErrorCategory

STATUS_BY_CATEGORY = {
    ErrorCategory.CONFIGURATION: 503,
    ErrorCategory.AUTHENTICATION: 502,
    ErrorCategory.CONNECTIVITY: 502,
    ErrorCategory.TIMEOUT: 504,
    ErrorCategory.API_LIMIT: 429,
    ErrorCategory.INTEGRATION: 502,
    ErrorCategory.INVALID_DATA: 422,
    ErrorCategory.NOT_FOUND: 404,
    ErrorCategory.AI: 502,
    ErrorCategory.EXPORT: 500,
}


def raise_http(exc: DomainError) -> None:
    raise HTTPException(status_code=STATUS_BY_CATEGORY.get(exc.category, 500), detail=str(exc)) from exc
