"""Smoke tests da sincronização .env / env-model."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import load_env, sync_env


def test_fresh_install_copies_all_keys_from_model():
    with tempfile.TemporaryDirectory() as tmp:
        model = Path(tmp) / "env-model"
        model.write_text("APP_ENV=local\nAI_API_KEY=\n", encoding="utf-8")
        env = Path(tmp) / ".env"

        added = sync_env(env, model)

        assert set(added) == {"APP_ENV", "AI_API_KEY"}
        assert "APP_ENV=local" in env.read_text(encoding="utf-8")


def test_never_overwrites_existing_value():
    with tempfile.TemporaryDirectory() as tmp:
        model = Path(tmp) / "env-model"
        model.write_text("APP_ENV=local\n", encoding="utf-8")
        env = Path(tmp) / ".env"
        env.write_text("APP_ENV=production\n", encoding="utf-8")

        added = sync_env(env, model)

        assert added == []
        assert "APP_ENV=production" in env.read_text(encoding="utf-8")
        assert "APP_ENV=local" not in env.read_text(encoding="utf-8")


def test_only_adds_missing_keys():
    with tempfile.TemporaryDirectory() as tmp:
        model = Path(tmp) / "env-model"
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


if __name__ == "__main__":
    test_fresh_install_copies_all_keys_from_model()
    test_never_overwrites_existing_value()
    test_only_adds_missing_keys()
    test_load_env_parses_key_value_pairs()
    test_load_env_missing_file_returns_empty_dict()
    print("OK — todos os testes de configuração passaram")
