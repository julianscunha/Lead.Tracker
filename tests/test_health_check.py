"""Testes do health_check() do módulo (Fase F, módulo 6
`mapping-health-check`) — banco SQLite temporário, SalesforceProvider
mockado (CLAUDE.md: providers sempre mockados em teste)."""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / ".techforge-dev" / "sdk" / "python"))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import backend.settings as settings_module
import main as backend_main
from core.db import create_engine, init_db, make_session_factory
from core.models import FieldMapping, SemanticFieldRole
from core.opportunity_engine import field_mapping_id
from core.repository import save_field_mapping
from providers.salesforce import SalesforceFieldInfo


class _StubSalesforceProvider:
    fields: list = []

    def __init__(self, *args, **kwargs):
        pass

    async def describe_custom_account_fields(self, force_refresh: bool = False):
        return _StubSalesforceProvider.fields


class _TempDbAndCatalog:
    """Redireciona main.session_factory pra um banco temporário e
    backend.settings.SalesforceProvider pro stub — mesmo padrão de
    tests/test_settings.py."""

    def __enter__(self):
        self._original_sf = backend_main.session_factory
        self._original_provider = settings_module.SalesforceProvider
        settings_module.SalesforceProvider = _StubSalesforceProvider
        _StubSalesforceProvider.fields = []

        self._tmpdir = tempfile.TemporaryDirectory()
        engine = create_engine(Path(self._tmpdir.name) / "test.db")
        asyncio.run(init_db(engine))
        self.session_factory = make_session_factory(engine)
        backend_main.session_factory = self.session_factory
        return self

    def __exit__(self, *exc):
        backend_main.session_factory = self._original_sf
        settings_module.SalesforceProvider = self._original_provider
        self._tmpdir.cleanup()


def test_check_field_mappings_health_returns_empty_without_any_mapping():
    with _TempDbAndCatalog():
        broken = asyncio.run(backend_main._check_field_mappings_health())
        assert broken == []


def test_check_field_mappings_health_flags_field_missing_from_catalog():
    with _TempDbAndCatalog() as ctx:
        async def setup():
            async with ctx.session_factory() as session:
                await save_field_mapping(session, FieldMapping(
                    id=field_mapping_id("salesforce", "Segmento__c"), provider_id="salesforce",
                    source_field_api_name="Segmento__c", source_field_label="Segmento",
                    role=SemanticFieldRole.INDUSTRY_HINT,
                ))
        asyncio.run(setup())
        _StubSalesforceProvider.fields = []  # campo sumiu do catálogo atual

        broken = asyncio.run(backend_main._check_field_mappings_health())
        assert len(broken) == 1
        assert broken[0].source_field_api_name == "Segmento__c"


def test_check_field_mappings_health_clean_when_field_still_in_catalog():
    with _TempDbAndCatalog() as ctx:
        async def setup():
            async with ctx.session_factory() as session:
                await save_field_mapping(session, FieldMapping(
                    id=field_mapping_id("salesforce", "Segmento__c"), provider_id="salesforce",
                    source_field_api_name="Segmento__c", source_field_label="Segmento",
                    role=SemanticFieldRole.INDUSTRY_HINT,
                ))
        asyncio.run(setup())
        _StubSalesforceProvider.fields = [SalesforceFieldInfo(name="Segmento__c", label="Segmento", type="picklist")]

        broken = asyncio.run(backend_main._check_field_mappings_health())
        assert broken == []


def test_health_check_stays_healthy_even_with_broken_mapping():
    """Achado do Sales Engineer: mapeamento quebrado é aviso, nunca falha
    do módulo — o sync continua funcionando pros demais campos."""
    with _TempDbAndCatalog() as ctx:
        async def setup():
            async with ctx.session_factory() as session:
                await save_field_mapping(session, FieldMapping(
                    id=field_mapping_id("salesforce", "Segmento__c"), provider_id="salesforce",
                    source_field_api_name="Segmento__c", source_field_label="Segmento",
                    role=SemanticFieldRole.INDUSTRY_HINT,
                ))
        asyncio.run(setup())
        _StubSalesforceProvider.fields = []

        result = asyncio.run(backend_main.module.health_check())
        assert result.is_healthy is True
        assert len(result.details["broken_field_mappings"]) == 1
        assert "removido ou renomeado" in result.details["broken_field_mappings"][0]


def test_health_check_never_touches_salesforce_without_any_mapping_saved():
    """Custo zero pra instalação sem Fase F configurada, mesmo princípio
    já aplicado no módulo 4 do split de contexto."""
    calls = {"describe": 0}

    class _CountingProvider(_StubSalesforceProvider):
        async def describe_custom_account_fields(self, force_refresh: bool = False):
            calls["describe"] += 1
            return []

    with _TempDbAndCatalog():
        settings_module.SalesforceProvider = _CountingProvider
        result = asyncio.run(backend_main.module.health_check())
        assert result.is_healthy is True
        assert calls["describe"] == 0


if __name__ == "__main__":
    test_check_field_mappings_health_returns_empty_without_any_mapping()
    test_check_field_mappings_health_flags_field_missing_from_catalog()
    test_check_field_mappings_health_clean_when_field_still_in_catalog()
    test_health_check_stays_healthy_even_with_broken_mapping()
    test_health_check_never_touches_salesforce_without_any_mapping_saved()
    print("OK — todos os testes de health check passaram")
