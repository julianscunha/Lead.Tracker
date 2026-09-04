"""
Configuração e segredos.

Sincroniza `.env` com `.env-model`: adiciona apenas chaves ausentes, nunca
sobrescreve ou remove valores existentes. O builder de pacotes do Tech.Forge
exclui todo arquivo começando com ponto, exceto `.env-model` — que está na
allowlist (`ALLOWED_DOTFILES`) desde o Tech.Forge v1.1.0 justamente para
sobreviver ao empacotamento sem exigir um nome fora do padrão.
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
        content = env_lines + (["", "# Adicionado automaticamente a partir de .env-model"] if env_lines else []) + new_lines
        env_path.write_text("\n".join(content) + "\n", encoding="utf-8")

    return added


def set_env_values(env_path: Path, values: dict[str, str]) -> None:
    """
    Atualiza (ou adiciona, se ainda não existir) cada chave de `values` no
    `.env`, preservando comentários, linhas em branco e qualquer chave não
    mencionada. Complementa `sync_env` — usada pela tela de Configurações
    de Fontes, que grava valor que o usuário digitou (nunca à mão).

    Uma chave com valor vazio em `values` nunca apaga um valor já salvo —
    mesma filosofia não-destrutiva do `sync_env`.

    Levanta `ValueError` se algum valor contiver quebra de linha — sem essa
    checagem, um campo de credencial poderia injetar uma chave nova
    arbitrária no `.env` (`sync_env`/`load_env` leem linha a linha).

    # ponytail: leitura-modificação-escrita sem lock de arquivo — assume um
    # único processo escrevendo por vez (módulo local-first, desktop). Se
    # escritas concorrentes via API virarem cenário real, adicionar lock.
    """
    values = {k: v for k, v in values.items() if v != ""}
    if not values:
        return
    for key, value in values.items():
        if "\n" in value or "\r" in value:
            raise ValueError(f"Valor de '{key}' contém quebra de linha — não permitido em .env.")

    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    written: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in values:
                if key in written:
                    continue  # chave duplicada no arquivo — descarta a repetição, mantém só a primeira
                new_lines.append(f"{key}={values[key]}")
                written.add(key)
                continue
        new_lines.append(line)

    for key, value in values.items():
        if key not in written:
            new_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


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
