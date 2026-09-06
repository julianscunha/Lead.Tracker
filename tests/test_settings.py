"""Smoke tests HTTP das rotas de Configurações de Fontes, via FastAPI
TestClient (sem subir uvicorn, sem rede real, sem tocar o .env real do
projeto — cada teste aponta routes_settings._ENV_PATH pra um arquivo
temporário)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / ".techforge-dev" / "sdk" / "python"))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

import main as backend_main
import backend.settings as settings_module
from backend import routes_settings
from core.db import create_engine, init_db, make_session_factory
from providers.salesforce import SalesforceFieldInfo

app = FastAPI()
app.include_router(backend_main.router)
client = TestClient(app)


class _TempEnv:
    """Redireciona routes_settings._ENV_PATH pra um arquivo temporário
    durante o teste, restaurando o original ao sair — nunca toca o .env
    real do checkout."""

    def __enter__(self):
        self._original = routes_settings._ENV_PATH
        self._tmpdir = tempfile.TemporaryDirectory()
        path = Path(self._tmpdir.name) / ".env"
        path.write_text("APP_ENV=local\n", encoding="utf-8")
        routes_settings._ENV_PATH = path
        return path

    def __exit__(self, *exc):
        routes_settings._ENV_PATH = self._original
        self._tmpdir.cleanup()


class _TempEnvAndDb:
    """Mesmo padrão de _TempEnv, mas também redireciona
    routes_settings.session_factory pra um banco SQLite temporário — as
    rotas de field-mapping (Fase F, módulo 5) precisam dos dois."""

    def __enter__(self):
        self._original_env = routes_settings._ENV_PATH
        self._original_sf = routes_settings.session_factory
        self._tmpdir = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmpdir.name)

        env_path = tmp_path / ".env"
        env_path.write_text("APP_ENV=local\n", encoding="utf-8")
        routes_settings._ENV_PATH = env_path

        import asyncio
        engine = create_engine(tmp_path / "test.db")
        asyncio.run(init_db(engine))
        self.session_factory = make_session_factory(engine)
        routes_settings.session_factory = self.session_factory
        return self

    def __exit__(self, *exc):
        routes_settings._ENV_PATH = self._original_env
        routes_settings.session_factory = self._original_sf
        self._tmpdir.cleanup()


class _StubSalesforceProvider:
    """Substitui SalesforceProvider real na rota de catálogo — nunca bate
    na rede de verdade em teste (CLAUDE.md: providers sempre mockados)."""
    fields: list = []

    def __init__(self, *args, **kwargs):
        pass

    async def describe_custom_account_fields(self, force_refresh: bool = False):
        return _StubSalesforceProvider.fields


class _FieldCatalogStub:
    def __enter__(self):
        self._original = settings_module.SalesforceProvider
        settings_module.SalesforceProvider = _StubSalesforceProvider
        _StubSalesforceProvider.fields = []
        return self

    def __exit__(self, *exc):
        settings_module.SalesforceProvider = self._original


def test_list_settings_returns_all_sources_with_defaults():
    with _TempEnv():
        resp = client.get("/modules/lead_tracker/settings")
        assert resp.status_code == 200
        body = resp.json()
        ids = {s["id"] for s in body}
        assert ids == {"manual", "salesforce", "website", "google_maps"}

        manual = next(s for s in body if s["id"] == "manual")
        assert manual["enabled"] is None  # sempre disponível, sem toggle
        assert manual["fields"] == []

        salesforce = next(s for s in body if s["id"] == "salesforce")
        assert salesforce["enabled"] is False
        assert all(f["has_value"] is False for f in salesforce["fields"])
        assert all("SALESFORCE" not in f["label"] for f in salesforce["fields"])  # rótulo em português, não API name


def test_secret_field_never_returns_value_in_claro():
    with _TempEnv() as env_path:
        env_path.write_text(env_path.read_text() + "SALESFORCE_CLIENT_SECRET=super-segredo\n", encoding="utf-8")

        resp = client.get("/modules/lead_tracker/settings")
        body = resp.json()
        salesforce = next(s for s in body if s["id"] == "salesforce")
        secret_field = next(f for f in salesforce["fields"] if f["key"] == "SALESFORCE_CLIENT_SECRET")

        assert secret_field["has_value"] is True
        assert "super-segredo" not in resp.text


def test_update_settings_persists_fields_without_erasing_others():
    with _TempEnv():
        resp = client.put("/modules/lead_tracker/settings/salesforce", json={
            "enabled": True,
            "fields": {"SALESFORCE_CLIENT_ID": "cid-123", "SALESFORCE_LOGIN_URL": "https://x.my.salesforce.com"},
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is True
        by_key = {f["key"]: f["has_value"] for f in body["fields"]}
        assert by_key["SALESFORCE_CLIENT_ID"] is True
        assert by_key["SALESFORCE_LOGIN_URL"] is True
        assert by_key["SALESFORCE_CLIENT_SECRET"] is False  # não enviado, continua vazio


def test_update_unknown_source_returns_friendly_error():
    with _TempEnv():
        resp = client.put("/modules/lead_tracker/settings/nao_existe", json={"fields": {}})
        assert resp.status_code == 422
        assert "não existe" in resp.json()["detail"]


def test_test_connection_manual_always_connected():
    with _TempEnv():
        resp = client.post("/modules/lead_tracker/settings/manual/test")
        assert resp.status_code == 200
        assert resp.json()["status"] == "connected"


def test_test_connection_salesforce_without_credentials_fails_friendly():
    with _TempEnv():
        resp = client.post("/modules/lead_tracker/settings/salesforce/test")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert "incompleta" in body["message"]


def test_test_connection_not_implemented_source_never_500():
    with _TempEnv():
        resp = client.post("/modules/lead_tracker/settings/website/test")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert "não está disponível" in body["message"]


def test_get_aging_sla_days_defaults_to_7_when_not_configured():
    with _TempEnv():
        resp = client.get("/modules/lead_tracker/settings/config/aging-sla-days")
        assert resp.status_code == 200
        assert resp.json() == {"days": 7}


def test_put_aging_sla_days_persists_and_round_trips():
    with _TempEnv():
        resp = client.put("/modules/lead_tracker/settings/config/aging-sla-days", json={"days": 14})
        assert resp.status_code == 200
        assert resp.json() == {"days": 14}

        resp = client.get("/modules/lead_tracker/settings/config/aging-sla-days")
        assert resp.json() == {"days": 14}


def test_put_aging_sla_days_rejects_non_positive_value():
    with _TempEnv():
        resp = client.put("/modules/lead_tracker/settings/config/aging-sla-days", json={"days": 0})
        assert resp.status_code == 422
        assert "dia" in resp.json()["detail"]


def test_get_geo_promotion_config_defaults_when_not_configured():
    with _TempEnv():
        resp = client.get("/modules/lead_tracker/settings/config/geo-promotion")
        assert resp.status_code == 200
        assert resp.json() == {"min_score": 0.75, "daily_cap": 20}


def test_put_geo_promotion_config_persists_and_round_trips():
    with _TempEnv():
        resp = client.put("/modules/lead_tracker/settings/config/geo-promotion", json={"min_score": 0.8, "daily_cap": 30})
        assert resp.status_code == 200
        assert resp.json() == {"min_score": 0.8, "daily_cap": 30}

        resp = client.get("/modules/lead_tracker/settings/config/geo-promotion")
        assert resp.json() == {"min_score": 0.8, "daily_cap": 30}


def test_put_geo_promotion_config_accepts_range_boundaries():
    with _TempEnv():
        resp_low = client.put("/modules/lead_tracker/settings/config/geo-promotion", json={"min_score": 0.0, "daily_cap": 1})
        assert resp_low.status_code == 200
        resp_high = client.put("/modules/lead_tracker/settings/config/geo-promotion", json={"min_score": 1.0, "daily_cap": 20})
        assert resp_high.status_code == 200


def test_put_geo_promotion_config_rejects_score_out_of_range():
    with _TempEnv():
        resp = client.put("/modules/lead_tracker/settings/config/geo-promotion", json={"min_score": 1.5, "daily_cap": 20})
        assert resp.status_code == 422
        assert "score" in resp.json()["detail"]


def test_put_geo_promotion_config_rejects_non_positive_cap():
    with _TempEnv():
        resp = client.put("/modules/lead_tracker/settings/config/geo-promotion", json={"min_score": 0.75, "daily_cap": 0})
        assert resp.status_code == 422
        assert "limite" in resp.json()["detail"]


def test_get_field_catalog_returns_fields_with_no_mapping_by_default():
    with _TempEnvAndDb(), _FieldCatalogStub():
        _StubSalesforceProvider.fields = [
            SalesforceFieldInfo(name="Segmento__c", label="Segmento", type="picklist"),
        ]
        resp = client.get("/modules/lead_tracker/settings/salesforce/field-catalog")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["source_field_api_name"] == "Segmento__c"
        assert body[0]["role"] is None


def test_get_field_catalog_reflects_existing_mapping():
    with _TempEnvAndDb() as env, _FieldCatalogStub():
        _StubSalesforceProvider.fields = [
            SalesforceFieldInfo(name="Segmento__c", label="Segmento", type="picklist"),
        ]
        put_resp = client.put("/modules/lead_tracker/settings/salesforce/field-mapping", json={
            "source_field_api_name": "Segmento__c", "source_field_label": "Segmento", "role": "industry_hint",
        })
        assert put_resp.status_code == 200
        assert put_resp.json()["reassigned_from_label"] is None

        resp = client.get("/modules/lead_tracker/settings/salesforce/field-catalog")
        body = resp.json()
        assert body[0]["role"] == "industry_hint"


def test_put_field_mapping_reassigns_role_from_previous_field():
    """Sales Engineer consultado: um papel só pode ter uma fonte por vez —
    mapear um 2º campo pro mesmo papel reatribui, nunca deixa os dois
    mapeados simultaneamente."""
    with _TempEnvAndDb():
        client.put("/modules/lead_tracker/settings/salesforce/field-mapping", json={
            "source_field_api_name": "Segmento__c", "source_field_label": "Segmento", "role": "industry_hint",
        })
        resp = client.put("/modules/lead_tracker/settings/salesforce/field-mapping", json={
            "source_field_api_name": "Vertical__c", "source_field_label": "Vertical", "role": "industry_hint",
        })
        assert resp.status_code == 200
        assert resp.json()["reassigned_from_label"] == "Segmento"

        with _FieldCatalogStub():
            _StubSalesforceProvider.fields = [
                SalesforceFieldInfo(name="Segmento__c", label="Segmento", type="picklist"),
                SalesforceFieldInfo(name="Vertical__c", label="Vertical", type="picklist"),
            ]
            catalog = client.get("/modules/lead_tracker/settings/salesforce/field-catalog").json()
        by_name = {f["source_field_api_name"]: f["role"] for f in catalog}
        assert by_name["Vertical__c"] == "industry_hint"
        assert by_name["Segmento__c"] is None


def test_put_field_mapping_same_field_updates_role_never_duplicates():
    with _TempEnvAndDb() as env:
        client.put("/modules/lead_tracker/settings/salesforce/field-mapping", json={
            "source_field_api_name": "Valor__c", "source_field_label": "Valor", "role": "industry_hint",
        })
        resp = client.put("/modules/lead_tracker/settings/salesforce/field-mapping", json={
            "source_field_api_name": "Valor__c", "source_field_label": "Valor", "role": "deal_size_hint",
        })
        assert resp.status_code == 200
        assert resp.json()["reassigned_from_label"] is None  # mesmo campo, não é reatribuição de outro


def test_delete_field_mapping_unmaps_it():
    with _TempEnvAndDb(), _FieldCatalogStub():
        _StubSalesforceProvider.fields = [SalesforceFieldInfo(name="Segmento__c", label="Segmento", type="picklist")]
        client.put("/modules/lead_tracker/settings/salesforce/field-mapping", json={
            "source_field_api_name": "Segmento__c", "source_field_label": "Segmento", "role": "industry_hint",
        })
        resp = client.delete("/modules/lead_tracker/settings/salesforce/field-mapping/Segmento__c")
        assert resp.status_code == 200

        catalog = client.get("/modules/lead_tracker/settings/salesforce/field-catalog").json()
        assert catalog[0]["role"] is None


def test_delete_field_mapping_unknown_field_never_errors():
    with _TempEnvAndDb():
        resp = client.delete("/modules/lead_tracker/settings/salesforce/field-mapping/Nao_Existe__c")
        assert resp.status_code == 200


def test_get_field_catalog_flags_mapping_whose_field_disappeared():
    """Fase F, módulo 6 (mapping-health-check) — campo mapeado que sumiu do
    catálogo atual aparece como linha própria, marcada broken=True, com a
    mensagem de negócio (nunca o nome técnico do campo)."""
    with _TempEnvAndDb():
        client.put("/modules/lead_tracker/settings/salesforce/field-mapping", json={
            "source_field_api_name": "Segmento__c", "source_field_label": "Segmento", "role": "industry_hint",
        })
        with _FieldCatalogStub():
            _StubSalesforceProvider.fields = []  # campo sumiu
            resp = client.get("/modules/lead_tracker/settings/salesforce/field-catalog")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["broken"] is True
        assert body[0]["source_field_api_name"] == "Segmento__c"
        assert "removido ou renomeado" in body[0]["broken_message"]


def test_get_field_catalog_without_credentials_returns_friendly_error():
    with _TempEnvAndDb():
        resp = client.get("/modules/lead_tracker/settings/salesforce/field-catalog")
        assert resp.status_code == 503  # ErrorCategory.CONFIGURATION
        assert "incompleta" in resp.json()["detail"]


if __name__ == "__main__":
    test_list_settings_returns_all_sources_with_defaults()
    test_secret_field_never_returns_value_in_claro()
    test_update_settings_persists_fields_without_erasing_others()
    test_update_unknown_source_returns_friendly_error()
    test_test_connection_manual_always_connected()
    test_test_connection_salesforce_without_credentials_fails_friendly()
    test_test_connection_not_implemented_source_never_500()
    test_get_aging_sla_days_defaults_to_7_when_not_configured()
    test_put_aging_sla_days_persists_and_round_trips()
    test_put_aging_sla_days_rejects_non_positive_value()
    test_get_geo_promotion_config_defaults_when_not_configured()
    test_put_geo_promotion_config_persists_and_round_trips()
    test_put_geo_promotion_config_accepts_range_boundaries()
    test_put_geo_promotion_config_rejects_score_out_of_range()
    test_put_geo_promotion_config_rejects_non_positive_cap()
    test_get_field_catalog_returns_fields_with_no_mapping_by_default()
    test_get_field_catalog_reflects_existing_mapping()
    test_put_field_mapping_reassigns_role_from_previous_field()
    test_put_field_mapping_same_field_updates_role_never_duplicates()
    test_delete_field_mapping_unmaps_it()
    test_delete_field_mapping_unknown_field_never_errors()
    test_get_field_catalog_flags_mapping_whose_field_disappeared()
    test_get_field_catalog_without_credentials_returns_friendly_error()
    print("OK — todos os testes de configurações de fontes passaram")
