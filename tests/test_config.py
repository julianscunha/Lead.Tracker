"""Smoke tests da sincronização .env / .env-model."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import load_env, set_env_values, sync_env


def test_fresh_install_copies_all_keys_from_model():
    with tempfile.TemporaryDirectory() as tmp:
        model = Path(tmp) / ".env-model"
        model.write_text("APP_ENV=local\nAI_API_KEY=\n", encoding="utf-8")
        env = Path(tmp) / ".env"

        added = sync_env(env, model)

        assert set(added) == {"APP_ENV", "AI_API_KEY"}
        assert "APP_ENV=local" in env.read_text(encoding="utf-8")


def test_never_overwrites_existing_value():
    with tempfile.TemporaryDirectory() as tmp:
        model = Path(tmp) / ".env-model"
        model.write_text("APP_ENV=local\n", encoding="utf-8")
        env = Path(tmp) / ".env"
        env.write_text("APP_ENV=production\n", encoding="utf-8")

        added = sync_env(env, model)

        assert added == []
        assert "APP_ENV=production" in env.read_text(encoding="utf-8")
        assert "APP_ENV=local" not in env.read_text(encoding="utf-8")


def test_only_adds_missing_keys():
    with tempfile.TemporaryDirectory() as tmp:
        model = Path(tmp) / ".env-model"
        model.write_text("APP_ENV=local\nNEW_KEY=\n", encoding="utf-8")
        env = Path(tmp) / ".env"
        env.write_text("APP_ENV=production\nCUSTOM=1\n", encoding="utf-8")

        added = sync_env(env, model)

        content = env.read_text(encoding="utf-8")
        assert added == ["NEW_KEY"]
        assert "APP_ENV=production" in content
        assert "CUSTOM=1" in content
        assert "NEW_KEY=" in content


def test_load_env_parses_key_value_pairs():
    with tempfile.TemporaryDirectory() as tmp:
        env = Path(tmp) / ".env"
        env.write_text("AI_PROVIDER=openrouter\nAI_API_KEY=sk-123\n# comentário\n\n", encoding="utf-8")

        result = load_env(env)

        assert result == {"AI_PROVIDER": "openrouter", "AI_API_KEY": "sk-123"}


def test_load_env_missing_file_returns_empty_dict():
    result = load_env(Path("/nao/existe/.env"))
    assert result == {}


def test_set_env_values_updates_existing_key_in_place():
    with tempfile.TemporaryDirectory() as tmp:
        env = Path(tmp) / ".env"
        env.write_text("APP_ENV=local\nSALESFORCE_CLIENT_ID=\nCUSTOM=1\n", encoding="utf-8")

        set_env_values(env, {"SALESFORCE_CLIENT_ID": "abc123"})

        content = env.read_text(encoding="utf-8")
        assert "SALESFORCE_CLIENT_ID=abc123" in content
        assert "APP_ENV=local" in content
        assert "CUSTOM=1" in content
        assert content.count("SALESFORCE_CLIENT_ID") == 1


def test_set_env_values_never_erases_with_empty_string():
    with tempfile.TemporaryDirectory() as tmp:
        env = Path(tmp) / ".env"
        env.write_text("SALESFORCE_CLIENT_ID=abc123\n", encoding="utf-8")

        set_env_values(env, {"SALESFORCE_CLIENT_ID": ""})

        assert "SALESFORCE_CLIENT_ID=abc123" in env.read_text(encoding="utf-8")


def test_set_env_values_appends_key_missing_from_file():
    with tempfile.TemporaryDirectory() as tmp:
        env = Path(tmp) / ".env"
        env.write_text("APP_ENV=local\n", encoding="utf-8")

        set_env_values(env, {"SALESFORCE_ENABLED": "true"})

        content = env.read_text(encoding="utf-8")
        assert "APP_ENV=local" in content
        assert "SALESFORCE_ENABLED=true" in content


def test_set_env_values_fixes_duplicate_key_keeping_new_value():
    with tempfile.TemporaryDirectory() as tmp:
        env = Path(tmp) / ".env"
        # chave duplicada no arquivo (cenário real: edição manual antiga) —
        # sem a correção, só a primeira ocorrência era atualizada e
        # load_env() (que lê top-to-bottom num dict) devolvia a segunda,
        # nunca-atualizada, como se fosse o valor salvo.
        env.write_text("SALESFORCE_CLIENT_ID=antigo\nAPP_ENV=local\nSALESFORCE_CLIENT_ID=antigo\n", encoding="utf-8")

        set_env_values(env, {"SALESFORCE_CLIENT_ID": "novo"})

        content = env.read_text(encoding="utf-8")
        assert content.count("SALESFORCE_CLIENT_ID") == 1
        assert load_env(env)["SALESFORCE_CLIENT_ID"] == "novo"


def test_set_env_values_rejects_value_with_newline():
    with tempfile.TemporaryDirectory() as tmp:
        env = Path(tmp) / ".env"
        env.write_text("APP_ENV=local\n", encoding="utf-8")

        try:
            set_env_values(env, {"SALESFORCE_CLIENT_ID": "abc\nGOOGLE_MAPS_API_KEY=injetado"})
            assert False, "deveria ter levantado ValueError"
        except ValueError:
            pass

        assert "injetado" not in env.read_text(encoding="utf-8")


def test_set_env_values_preserves_comments_and_blank_lines():
    with tempfile.TemporaryDirectory() as tmp:
        env = Path(tmp) / ".env"
        env.write_text("# comentário\nAPP_ENV=local\n\nSALESFORCE_ENABLED=false\n", encoding="utf-8")

        set_env_values(env, {"SALESFORCE_ENABLED": "true"})

        content = env.read_text(encoding="utf-8")
        assert "# comentário" in content
        assert "SALESFORCE_ENABLED=true" in content
        assert "SALESFORCE_ENABLED=false" not in content


if __name__ == "__main__":
    test_fresh_install_copies_all_keys_from_model()
    test_never_overwrites_existing_value()
    test_only_adds_missing_keys()
    test_load_env_parses_key_value_pairs()
    test_load_env_missing_file_returns_empty_dict()
    test_set_env_values_updates_existing_key_in_place()
    test_set_env_values_never_erases_with_empty_string()
    test_set_env_values_appends_key_missing_from_file()
    test_set_env_values_fixes_duplicate_key_keeping_new_value()
    test_set_env_values_rejects_value_with_newline()
    test_set_env_values_preserves_comments_and_blank_lines()
    print("OK — todos os testes de configuração passaram")
