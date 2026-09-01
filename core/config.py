"""
Configuração e segredos.

Sincroniza `.env` com `env-model`: adiciona apenas chaves ausentes, nunca
sobrescreve ou remove valores existentes. `env-model` não leva ponto no nome
de propósito — o builder de pacotes do Tech.Forge exclui todo arquivo
começando com ponto, e esse arquivo precisa sobreviver ao empacotamento.
"""
from __future__ import annotations

from pathlib import Path


def _parse_keys(lines: list[str]) -> set[str]:
    keys = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        keys.add(stripped.split("=", 1)[0].strip())
    return keys


def sync_env(env_path: Path, model_path: Path) -> list[str]:
    """
    Compara `env_path` com `model_path` e adiciona ao `.env` somente as
    variáveis presentes no modelo e ausentes no `.env`.

    Nunca sobrescreve ou remove uma variável já existente.
    Retorna a lista de chaves adicionadas (vazia se nada mudou).
    """
    model_lines = model_path.read_text(encoding="utf-8").splitlines()
    env_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []

    existing_keys = _parse_keys(env_lines)
    added: list[str] = []
    new_lines: list[str] = []

    for line in model_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key not in existing_keys:
            new_lines.append(line)
            added.append(key)

    if added:
        content = env_lines + (["", "# Adicionado automaticamente a partir de env-model"] if env_lines else []) + new_lines
        env_path.write_text("\n".join(content) + "\n", encoding="utf-8")

    return added


def load_env(env_path: Path) -> dict[str, str]:
    """Lê `.env` para um dict — usado em runtime pra configurar providers
    (ex.: AI_PROVIDER/AI_API_KEY). Chave sem valor vira string vazia, nunca None."""
    if not env_path.exists():
        return {}
    result: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        result[key.strip()] = value.strip()
    return result
