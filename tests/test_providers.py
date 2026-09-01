"""Smoke tests do contrato DataProvider via ManualProvider."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import Company, Contact, SourceRef
from providers.base import DataProvider
from providers.manual import ManualProvider


def test_manual_provider_implements_contract():
    assert issubclass(ManualProvider, DataProvider)


def test_manual_provider_lifecycle():
    async def run():
        provider = ManualProvider()
        assert provider.id == "manual"

        conn = await provider.test_connection()
        assert conn.is_connected is True

        company = Company(name="Empresa Fictícia", sources=[SourceRef(type="manual")])
        provider.add_company(company)
        provider.add_contact(Contact(company_id=company.id, name="Fulano"))

        companies = await provider.fetch_companies()
        assert companies == [company]

        contacts = await provider.fetch_contacts(company.id)
        assert len(contacts) == 1
        assert contacts[0].name == "Fulano"

        ctx = await provider.fetch_context(company.id)
        assert ctx.company_id == company.id

    asyncio.run(run())


if __name__ == "__main__":
    test_manual_provider_implements_contract()
    test_manual_provider_lifecycle()
    print("OK — todos os testes de providers passaram")
