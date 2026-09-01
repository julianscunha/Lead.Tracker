"""
ManualProvider — referência de arquitetura.

Permite dados adicionados manualmente pelo usuário. Sem chamada externa, sem
timeout/retry necessário: valida que o contrato DataProvider funciona ponta a
ponta antes de qualquer integração real (Salesforce/Website ainda não
implementados).
"""
from __future__ import annotations

from core.models import Company, Contact
from providers.base import ConnectionTestResult, DataProvider, ProviderContext


class ManualProvider(DataProvider):

    def __init__(self) -> None:
        self._companies: dict[str, Company] = {}
        self._contacts: dict[str, list[Contact]] = {}

    @property
    def id(self) -> str:
        return "manual"

    def add_company(self, company: Company) -> None:
        self._companies[company.id] = company

    def add_contact(self, contact: Contact) -> None:
        self._contacts.setdefault(contact.company_id, []).append(contact)

    async def test_connection(self) -> ConnectionTestResult:
        return ConnectionTestResult.ok("provider manual sempre disponível")

    async def fetch_companies(self) -> list[Company]:
        return list(self._companies.values())

    async def fetch_contacts(self, company_id: str) -> list[Contact]:
        return list(self._contacts.get(company_id, []))

    async def fetch_context(self, company_id: str) -> ProviderContext:
        return ProviderContext(company_id=company_id)
