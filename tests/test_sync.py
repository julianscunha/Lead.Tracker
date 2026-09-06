"""Smoke tests da orquestração de sincronização (Fase B.1) — provider fake
in-memory, sem rede real, banco SQLite temporário."""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.settings import SourceDescriptor
from backend.sync import _apply_field_mappings_for_synced_companies, sync_all_enabled_sources, sync_source
from core.db import create_engine, init_db, make_session_factory
from core.models import (
    Company, CompanySignal, Contact, CorrelationRule, FieldMapping, Portfolio, SemanticFieldRole, SourceRef,
)
from core.opportunity_engine import field_mapping_id
from core.repository import (
    get_company, list_companies, list_contacts, list_latest_snapshot, list_opportunities, save_company,
    save_company_signal, save_field_mapping, save_portfolio, save_rule,
)
from providers.base import ConnectionTestResult, DataProvider, ProviderContext, ProviderError


class _FakeProvider(DataProvider):
    def __init__(
        self, companies: list[Company], contacts: dict[str, list[Contact]] | None = None, fail: bool = False,
        contexts: dict[str, dict] | None = None, context_fail_for: set[str] | None = None,
    ):
        self._companies = companies
        self._contacts = contacts or {}
        self._fail = fail
        self._contexts = contexts or {}
        self._context_fail_for = context_fail_for or set()

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
        if company_id in self._context_fail_for:
            raise ProviderError("Falha simulada ao buscar contexto.")
        custom_fields = self._contexts.get(company_id)
        if not custom_fields:
            return ProviderContext(company_id=company_id)
        return ProviderContext(company_id=company_id, extra={"custom_fields": custom_fields})


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


def test_sync_all_enabled_sources_recomputes_daily_snapshot_reflecting_generated_opportunity():
    """Fase D: o snapshot diário é recalculado no fim de TODO /sync, mesmo
    passando por sync_all_enabled_sources (não só sync_source isolado) — é
    o caminho real que a rota POST /sync usa."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            provider = _FakeProvider([company])
            source = SourceDescriptor(
                id="fake", label="Fake", enabled_key="FAKE_ENABLED", implemented=True, build=lambda env: provider,
            )

            rule = CorrelationRule(
                id="veeam_m365_sem_vdc365", opportunity_type="cross-sell",
                requires=["veeam_vbr", "m365"], absent=["vdc365"],
                justification="Tem Veeam VBR e M365, sem VDC365.",
            )
            async with session_factory() as session:
                await save_rule(session, rule)
                await save_portfolio(session, Portfolio(company_id=company.id, product_ids=["veeam_vbr", "m365"]))

            import backend.sync as sync_module
            original_sources = sync_module.SOURCES
            sync_module.SOURCES = [source]
            try:
                await sync_all_enabled_sources(session_factory, {"FAKE_ENABLED": "true"})
            finally:
                sync_module.SOURCES = original_sources

            async with session_factory() as session:
                snapshot = await list_latest_snapshot(session)
            assert len(snapshot) == 1
            assert snapshot[0].stage.value == "detected"
            assert snapshot[0].is_zombie is False

    asyncio.run(run())


def test_sync_without_field_mapping_never_calls_fetch_context():
    """Instalação sem nenhum FieldMapping configurado (caso comum hoje) não
    paga o custo de fetch_context — mesmo padrão de custo/comportamento de
    antes do módulo mapping-driven-context-split existir."""
    calls = {"context": 0}

    class _CountingProvider(_FakeProvider):
        async def fetch_context(self, company_id: str) -> ProviderContext:
            calls["context"] += 1
            return await super().fetch_context(company_id)

    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            provider = _CountingProvider([company])
            source = SourceDescriptor(id="fake", label="Fake", enabled_key=None, implemented=True, build=lambda env: provider)

            result = await sync_source(session_factory, source, {})
            assert result.errors == []

    asyncio.run(run())
    assert calls["context"] == 0


def test_sync_applies_field_mapping_writes_structural_company_field():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            provider = _FakeProvider([company], contexts={company.id: {"Segmento__c": "Varejo"}})
            source = SourceDescriptor(id="fake", label="Fake", enabled_key=None, implemented=True, build=lambda env: provider)

            async with session_factory() as session:
                await save_field_mapping(session, FieldMapping(
                    id=field_mapping_id("fake", "Segmento__c"), provider_id="fake",
                    source_field_api_name="Segmento__c", source_field_label="Segmento",
                    role=SemanticFieldRole.INDUSTRY_HINT,
                ))

            result = await sync_source(session_factory, source, {})
            assert result.errors == []

            async with session_factory() as session:
                loaded = await get_company(session, company.id)
            assert loaded.industry == "Varejo"

    asyncio.run(run())


def test_sync_field_mapping_always_overwrites_existing_structural_value():
    """Precedência confirmada (Salesforce Architect): campo mapeado sempre
    sobrescreve, mesmo que o campo estrutural já tivesse um valor (padrão
    ou de um sync anterior) — nunca "só se vazio"."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas", industry="Industry Padrão Desatualizada")
            provider = _FakeProvider([company], contexts={company.id: {"Segmento__c": "Varejo"}})
            source = SourceDescriptor(id="fake", label="Fake", enabled_key=None, implemented=True, build=lambda env: provider)

            async with session_factory() as session:
                await save_field_mapping(session, FieldMapping(
                    id=field_mapping_id("fake", "Segmento__c"), provider_id="fake",
                    source_field_api_name="Segmento__c", source_field_label="Segmento",
                    role=SemanticFieldRole.INDUSTRY_HINT,
                ))

            await sync_source(session_factory, source, {})

            async with session_factory() as session:
                loaded = await get_company(session, company.id)
            assert loaded.industry == "Varejo"

    asyncio.run(run())


def test_sync_field_mapping_writes_deal_size_hint_from_numeric_custom_field():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            provider = _FakeProvider([company], contexts={company.id: {"Valor_Estimado__c": 50000.0}})
            source = SourceDescriptor(id="fake", label="Fake", enabled_key=None, implemented=True, build=lambda env: provider)

            async with session_factory() as session:
                await save_field_mapping(session, FieldMapping(
                    id=field_mapping_id("fake", "Valor_Estimado__c"), provider_id="fake",
                    source_field_api_name="Valor_Estimado__c", source_field_label="Valor Estimado",
                    role=SemanticFieldRole.DEAL_SIZE_HINT,
                ))

            await sync_source(session_factory, source, {})

            async with session_factory() as session:
                loaded = await get_company(session, company.id)
            assert loaded.deal_size_hint == 50000.0

    asyncio.run(run())


def test_sync_field_mapping_with_unparseable_value_never_crashes_leaves_field_untouched():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            provider = _FakeProvider([company], contexts={company.id: {"Valor_Estimado__c": "não é número"}})
            source = SourceDescriptor(id="fake", label="Fake", enabled_key=None, implemented=True, build=lambda env: provider)

            async with session_factory() as session:
                await save_field_mapping(session, FieldMapping(
                    id=field_mapping_id("fake", "Valor_Estimado__c"), provider_id="fake",
                    source_field_api_name="Valor_Estimado__c", source_field_label="Valor Estimado",
                    role=SemanticFieldRole.DEAL_SIZE_HINT,
                ))

            result = await sync_source(session_factory, source, {})
            assert result.errors == []

            async with session_factory() as session:
                loaded = await get_company(session, company.id)
            assert loaded.deal_size_hint is None

    asyncio.run(run())


def test_apply_field_mappings_updates_in_memory_company_not_just_the_database():
    """Achado da revisão de código: sem isso, o motor de regras (chamado
    logo depois, na mesma rodada de sync, com os objetos em memória de
    `to_persist`) avaliaria contra o valor antigo até o PRÓXIMO /sync —
    quieto hoje porque nenhuma regra lê industry/deal_size_hint ainda, mas
    é exatamente o bug que aparece no dia em que uma regra passar a usar
    esses campos."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            provider = _FakeProvider([company], contexts={company.id: {"Segmento__c": "Varejo"}})

            async with session_factory() as session:
                await save_company(session, company)
                await save_field_mapping(session, FieldMapping(
                    id=field_mapping_id("fake", "Segmento__c"), provider_id="fake",
                    source_field_api_name="Segmento__c", source_field_label="Segmento",
                    role=SemanticFieldRole.INDUSTRY_HINT,
                ))

            to_persist = {company.id: company}
            errors = await _apply_field_mappings_for_synced_companies(session_factory, provider, "fake", to_persist)

            assert errors == []
            assert to_persist[company.id].industry == "Varejo"  # objeto em memória, não só o banco

    asyncio.run(run())


def test_sync_field_mapping_parses_salesforce_datetime_field_with_offset():
    """RENEWAL_DATE pode vir de um campo Date ("YYYY-MM-DD") ou DateTime
    Salesforce ("...T00:00:00.000+0000") — os dois precisam parsear."""
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            provider = _FakeProvider(
                [company], contexts={company.id: {"Data_Renovacao__c": "2026-12-01T00:00:00.000+0000"}},
            )
            source = SourceDescriptor(id="fake", label="Fake", enabled_key=None, implemented=True, build=lambda env: provider)

            async with session_factory() as session:
                await save_field_mapping(session, FieldMapping(
                    id=field_mapping_id("fake", "Data_Renovacao__c"), provider_id="fake",
                    source_field_api_name="Data_Renovacao__c", source_field_label="Data de Renovação",
                    role=SemanticFieldRole.RENEWAL_DATE,
                ))

            result = await sync_source(session_factory, source, {})
            assert result.errors == []

            async with session_factory() as session:
                loaded = await get_company(session, company.id)
            assert loaded.renewal_date is not None
            assert loaded.renewal_date.year == 2026
            assert loaded.renewal_date.month == 12

    asyncio.run(run())


def test_sync_fetch_context_failure_reported_as_error_never_aborts_sync():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            session_factory = await _fresh_session_factory(tmp)
            company = Company(name="Aurora Sistemas")
            provider = _FakeProvider([company], context_fail_for={company.id})
            source = SourceDescriptor(id="fake", label="Fake", enabled_key=None, implemented=True, build=lambda env: provider)

            async with session_factory() as session:
                await save_field_mapping(session, FieldMapping(
                    id=field_mapping_id("fake", "Segmento__c"), provider_id="fake",
                    source_field_api_name="Segmento__c", source_field_label="Segmento",
                    role=SemanticFieldRole.INDUSTRY_HINT,
                ))

            result = await sync_source(session_factory, source, {})
            assert result.companies_synced == 1  # empresa continua persistida
            assert len(result.errors) == 1

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
    test_sync_all_enabled_sources_recomputes_daily_snapshot_reflecting_generated_opportunity()
    test_sync_without_field_mapping_never_calls_fetch_context()
    test_sync_applies_field_mapping_writes_structural_company_field()
    test_sync_field_mapping_always_overwrites_existing_structural_value()
    test_sync_field_mapping_writes_deal_size_hint_from_numeric_custom_field()
    test_sync_field_mapping_with_unparseable_value_never_crashes_leaves_field_untouched()
    test_apply_field_mappings_updates_in_memory_company_not_just_the_database()
    test_sync_field_mapping_parses_salesforce_datetime_field_with_offset()
    test_sync_fetch_context_failure_reported_as_error_never_aborts_sync()
    print("OK — todos os testes de sincronização passaram")
