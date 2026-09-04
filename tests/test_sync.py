"""Smoke tests da orquestração de sincronização (Fase B.1) — provider fake
in-memory, sem rede real, banco SQLite temporário."""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.settings import SourceDescriptor
from backend.sync import sync_all_enabled_sources, sync_source
from core.db import create_engine, init_db, make_session_factory
from core.models import Company, CompanySignal, Contact, CorrelationRule, Portfolio, SourceRef
from core.repository import (
    list_companies, list_contacts, list_opportunities, save_company, save_company_signal,
    save_portfolio, save_rule,
)
from providers.base import ConnectionTestResult, DataProvider, ProviderContext, ProviderError


class _FakeProvider(DataProvider):
    def __init__(self, companies: list[Company], contacts: dict[str, list[Contact]] | None = None, fail: bool = False):
        self._companies = companies
        self._contacts = contacts or {}
        self._fail = fail

    @property
    def id(self) -> str:
        return "fake"

    async def test_connection(self) -> ConnectionTestResult:
        return ConnectionTestResult.ok()

    async def fetch_companies(self) -> list[Company]:
        if self._fail:
            raise ProviderError("Falha simulada de conexão.")
        return self._companies

    async def fetch_contacts(self, company_id: str) -> list[Contact]:
        return self._contacts.get(company_id, [])

    async def fetch_context(self, company_id: str) -> ProviderContext:
        return ProviderContext(company_id=company_id)


async def _fresh_session_factory(tmp_dir: str):
    engine = create_engine(Path(tmp_dir) / "test.db")
    await init_db(engine)
    return make_session_factory(engine)


def test_sync_source_persists_companies_and_contacts():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            contact = Contact(company_id=company.id, name="Fulano")
            provider = _FakeProvider([company], {company.id: [contact]})
            source = SourceDescriptor(id="fake", label="Fake", enabled_key=None, implemented=True, build=lambda env: provider)

            result = await sync_source(session_factory, source, {})

            assert result.companies_synced == 1
            assert result.contacts_synced == 1
            assert result.errors == []

            async with session_factory() as session:
                companies = await list_companies(session)
                contacts = await list_contacts(session, company.id)
            assert len(companies) == 1
            assert companies[0].name == "Aurora Sistemas"
            assert len(contacts) == 1

    asyncio.run(run())


def test_sync_source_dedups_companies_from_same_provider():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            dup1 = Company(name="Aurora Sistemas", website="aurora.com")
            dup2 = Company(name="Aurora Sistemas", website="aurora.com")
            provider = _FakeProvider([dup1, dup2])
            source = SourceDescriptor(id="fake", label="Fake", enabled_key=None, implemented=True, build=lambda env: provider)

            result = await sync_source(session_factory, source, {})

            assert result.companies_synced == 1

    asyncio.run(run())


def test_sync_source_provider_failure_returns_friendly_error_never_raises():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            provider = _FakeProvider([], fail=True)
            source = SourceDescriptor(id="fake", label="Fake", enabled_key=None, implemented=True, build=lambda env: provider)

            result = await sync_source(session_factory, source, {})

            assert result.companies_synced == 0
            assert result.errors == ["Falha simulada de conexão."]

    asyncio.run(run())


def test_sync_source_not_implemented_source_returns_friendly_error():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            source = SourceDescriptor(id="website", label="Website", enabled_key="WEBSITE_ENABLED", implemented=False)

            result = await sync_source(session_factory, source, {})

            assert result.companies_synced == 0
            assert "não está disponível" in result.errors[0]

    asyncio.run(run())


def test_sync_reconciles_company_across_different_sources_never_duplicates():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)

            # Fonte A já sincronizou "Aurora Sistemas" antes.
            existing = Company(name="Aurora Sistemas", website="aurora.com")
            async with session_factory() as session:
                await save_company(session, existing)

            # Fonte B (provider diferente) traz a MESMA empresa, com outro id nativo.
            same_company_other_source = Company(name="Aurora Sistemas", website="aurora.com")
            provider = _FakeProvider([same_company_other_source])
            source = SourceDescriptor(id="fake", label="Fake", enabled_key=None, implemented=True, build=lambda env: provider)

            await sync_source(session_factory, source, {})

            async with session_factory() as session:
                companies = await list_companies(session)
            assert len(companies) == 1
            assert companies[0].id == existing.id  # id do registro já existente é preservado

    asyncio.run(run())


def test_sync_fetches_contacts_with_provider_native_id_after_reconciliation():
    """company.id reconciliado vira o id JÁ existente no banco (de outra
    fonte) — mas fetch_contacts precisa continuar usando o id NATIVO do
    provider (ex.: Salesforce Account Id), senão a busca falha pro provider."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            existing = Company(name="Aurora Sistemas", website="aurora.com")
            async with session_factory() as session:
                await save_company(session, existing)

            incoming = Company(name="Aurora Sistemas", website="aurora.com")  # id nativo != existing.id
            contact = Contact(company_id=incoming.id, name="Fulano")
            provider = _FakeProvider([incoming], {incoming.id: [contact]})
            source = SourceDescriptor(id="fake", label="Fake", enabled_key=None, implemented=True, build=lambda env: provider)

            result = await sync_source(session_factory, source, {})

            assert result.contacts_synced == 1
            async with session_factory() as session:
                contacts_under_existing_id = await list_contacts(session, existing.id)
            assert len(contacts_under_existing_id) == 1

    asyncio.run(run())


def test_sync_generates_opportunity_when_active_rule_and_portfolio_exist():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            provider = _FakeProvider([company])
            source = SourceDescriptor(id="fake", label="Fake", enabled_key=None, implemented=True, build=lambda env: provider)

            rule = CorrelationRule(
                id="veeam_m365_sem_vdc365", opportunity_type="cross-sell",
                requires=["veeam_vbr", "m365"], absent=["vdc365"],
                justification="Tem Veeam VBR e M365, sem VDC365.",
            )
            async with session_factory() as session:
                await save_rule(session, rule)
                await save_portfolio(session, Portfolio(company_id=company.id, product_ids=["veeam_vbr", "m365"]))

            result = await sync_source(session_factory, source, {})

            assert result.opportunities_generated == 1
            async with session_factory() as session:
                opportunities = await list_opportunities(session, company_id=company.id)
            assert len(opportunities) == 1
            assert opportunities[0].type == "cross-sell"

    asyncio.run(run())


def test_sync_twice_never_duplicates_opportunity():
    """Regressão crítica: sem id determinístico, cada sync re-avaliando a
    mesma regra pro mesmo portfólio inserta uma Opportunity NOVA — duplicata
    infinita a cada sincronização. Rodar sync 2x com portfólio inalterado
    tem que resultar em 1 linha só, sempre a mesma (upsert, não insert)."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            provider = _FakeProvider([company])
            source = SourceDescriptor(id="fake", label="Fake", enabled_key=None, implemented=True, build=lambda env: provider)

            rule = CorrelationRule(
                id="veeam_m365_sem_vdc365", opportunity_type="cross-sell",
                requires=["veeam_vbr", "m365"], absent=["vdc365"],
                justification="Tem Veeam VBR e M365, sem VDC365.",
            )
            async with session_factory() as session:
                await save_rule(session, rule)
                await save_portfolio(session, Portfolio(company_id=company.id, product_ids=["veeam_vbr", "m365"]))

            first = await sync_source(session_factory, source, {})
            second = await sync_source(session_factory, source, {})

            assert first.opportunities_generated == 1
            assert second.opportunities_generated == 1  # reavaliou, mas upsertou a mesma
            async with session_factory() as session:
                opportunities = await list_opportunities(session, company_id=company.id)
            assert len(opportunities) == 1  # nunca duplicou

    asyncio.run(run())


def test_sync_generates_no_opportunity_when_company_has_no_portfolio():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            provider = _FakeProvider([company])
            source = SourceDescriptor(id="fake", label="Fake", enabled_key=None, implemented=True, build=lambda env: provider)

            rule = CorrelationRule(
                id="veeam_m365_sem_vdc365", opportunity_type="cross-sell",
                requires=["veeam_vbr", "m365"], absent=["vdc365"],
                justification="Tem Veeam VBR e M365, sem VDC365.",
            )
            async with session_factory() as session:
                await save_rule(session, rule)
            # sem Portfolio pra "Aurora Sistemas" — não é bug, é honesto

            result = await sync_source(session_factory, source, {})

            assert result.opportunities_generated == 0

    asyncio.run(run())


def test_sync_generates_opportunity_from_open_company_signal():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            provider = _FakeProvider([company])
            source = SourceDescriptor(id="fake", label="Fake", enabled_key=None, implemented=True, build=lambda env: provider)

            rule = CorrelationRule(
                id="renovacao_proxima", opportunity_type="renewal",
                requires=["renewal_upcoming"], justification="Sinal de renovação próxima em aberto.",
            )
            async with session_factory() as session:
                await save_rule(session, rule)
                await save_portfolio(session, Portfolio(company_id=company.id))
                await save_company_signal(session, CompanySignal(
                    company_id=company.id, signal_type="renewal_upcoming",
                    source=SourceRef(type="manual", confidence=1.0),
                ))

            result = await sync_source(session_factory, source, {})

            assert result.opportunities_generated == 1
            async with session_factory() as session:
                opportunities = await list_opportunities(session, company_id=company.id)
            assert len(opportunities) == 1
            assert opportunities[0].type == "renewal"

    asyncio.run(run())


def test_sync_all_enabled_sources_skips_disabled_and_no_toggle_sources():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            # env sem nenhuma fonte real habilitada — deve devolver lista vazia,
            # nunca tentar sincronizar Manual (sem toggle) ou Salesforce (desligado).
            results = await sync_all_enabled_sources(session_factory, {"SALESFORCE_ENABLED": "false"})
            assert results == []

    asyncio.run(run())


if __name__ == "__main__":
    test_sync_source_persists_companies_and_contacts()
    test_sync_source_dedups_companies_from_same_provider()
    test_sync_source_provider_failure_returns_friendly_error_never_raises()
    test_sync_source_not_implemented_source_returns_friendly_error()
    test_sync_reconciles_company_across_different_sources_never_duplicates()
    test_sync_fetches_contacts_with_provider_native_id_after_reconciliation()
    test_sync_generates_opportunity_when_active_rule_and_portfolio_exist()
    test_sync_twice_never_duplicates_opportunity()
    test_sync_generates_no_opportunity_when_company_has_no_portfolio()
    test_sync_generates_opportunity_from_open_company_signal()
    test_sync_all_enabled_sources_skips_disabled_and_no_toggle_sources()
    print("OK — todos os testes de sincronização passaram")
