"""
Taxonomia de erro de domínio.

Toda exceção técnica vira um destes — nunca vaza stack trace/exceção bruta
pro usuário leigo (CLAUDE.md 'Error handling & resilience').
"""
from __future__ import annotations

from enum import Enum


class ErrorCategory(str, Enum):
    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    CONNECTIVITY = "connectivity"
    TIMEOUT = "timeout"
    API_LIMIT = "api_limit"
    INTEGRATION = "integration"
    INVALID_DATA = "invalid_data"
    AI = "ai"
    EXPORT = "export"


class DomainError(Exception):
    """Erro amigável e acionável. `message` é o que o usuário lê; nunca a exceção técnica original."""

    def __init__(self, category: ErrorCategory, message: str, recommended_action: str | None = None) -> None:
        self.category = category
        self.message = message
        self.recommended_action = recommended_action
        super().__init__(message)

    def __str__(self) -> str:
        if self.recommended_action:
            return f"{self.message} {self.recommended_action}"
        return self.message
