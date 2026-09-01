"""
Contrato de Providers.

Provider coleta e normaliza dados de uma fonte externa (ou manual) — nunca
calcula score, gera e-mail, executa prompts de IA ou controla a interface.
Erros técnicos nunca vazam brutos para quem chama: toda falha vira
ProviderError com mensagem acionável.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from core.errors import DomainError, ErrorCategory
from core.models import Company, Contact


class ProviderError(DomainError):
    """Erro amigável de provider — nunca expor stack trace/exceção técnica bruta ao usuário.
    Categoria padrão INTEGRATION; passar `category=` explícito para AUTHENTICATION/CONNECTIVITY/etc."""

    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.INTEGRATION, recommended_action: str | None = None) -> None:
        super().__init__(category, message, recommended_action)


@dataclass
class ConnectionTestResult:
    is_connected: bool
    message: str = "OK"

    @classmethod
    def ok(cls, message: str = "OK") -> "ConnectionTestResult":
        return cls(is_connected=True, message=message)

    @classmethod
    def fail(cls, message: str) -> "ConnectionTestResult":
        return cls(is_connected=False, message=message)


@dataclass
class ProviderContext:
    """Contexto bruto coletado por um provider (ex.: texto de website), consumido
    depois pela camada de normalização/portfólio — não pela IA direto."""
    company_id: str
    raw_text: str = ""
    pages: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


class DataProvider(ABC):
    """
    Contrato mínimo que todo provider deve implementar.

    Nenhum método aqui decide oportunidade, calcula score ou toca a UI —
    só coleta e devolve dados normalizados nos modelos de domínio (core/models.py).
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """Identificador estável do provider (ex.: 'salesforce', 'website', 'manual')."""

    @abstractmethod
    async def test_connection(self) -> ConnectionTestResult:
        """Verifica se o provider está acessível/configurado corretamente."""

    @abstractmethod
    async def fetch_companies(self) -> list[Company]:
        """Retorna empresas conhecidas por este provider."""

    @abstractmethod
    async def fetch_contacts(self, company_id: str) -> list[Contact]:
        """Retorna contatos de uma empresa específica."""

    @abstractmethod
    async def fetch_context(self, company_id: str) -> ProviderContext:
        """Retorna contexto bruto adicional de uma empresa (texto, páginas, etc.)."""
