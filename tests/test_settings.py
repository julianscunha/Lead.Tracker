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
from backend import routes_settings

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


if __name__ == "__main__":
    test_list_settings_returns_all_sources_with_defaults()
    test_secret_field_never_returns_value_in_claro()
    test_update_settings_persists_fields_without_erasing_others()
    test_update_unknown_source_returns_friendly_error()
    test_test_connection_manual_always_connected()
    test_test_connection_salesforce_without_credentials_fails_friendly()
    test_test_connection_not_implemented_source_never_500()
    print("OK — todos os testes de configurações de fontes passaram")
