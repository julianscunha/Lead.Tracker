"""
Rotas de Configurações de Fontes (docs/specs/fase0-configuracoes-fontes.md).

Contrato: nenhum segredo (`SourceField.secret=True`) volta em claro no
GET — só `has_value`. Todo DomainError vira HTTPException pela mesma tabela
compartilhada (backend/http_errors.py). Fonte não implementada nunca gera
500 — devolve ConnectionTestResult amigável.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.http_errors import raise_http
from backend.settings import SOURCES, get_source
from core.config import load_env, set_env_values
from core.errors import DomainError, ErrorCategory
from providers.base import ConnectionTestResult, ProviderError

_MODULE_ROOT = Path(__file__).parent.parent
_ENV_PATH = _MODULE_ROOT / ".env"

router = APIRouter(prefix="/settings", tags=["lead_tracker-settings"])


class FieldStatus(BaseModel):
    key: str
    label: str
    help_text: str
    secret: bool
    has_value: bool


class LastCheck(BaseModel):
    status: str  # "connected" | "failed" | "unknown"
    message: str = ""


class SourceStatus(BaseModel):
    id: str
    label: str
    implemented: bool
    enabled: bool | None  # None = sempre disponível, sem toggle (ex.: Manual)
    fields: list[FieldStatus]
    last_check: LastCheck


class UpdateSourceRequest(BaseModel):
    enabled: bool | None = None
    fields: dict[str, str] = {}


def _source_status(source, env: dict[str, str]) -> SourceStatus:
    enabled = env.get(source.enabled_key, "false") == "true" if source.enabled_key else None
    fields = [
        FieldStatus(
            key=f.key, label=f.label, help_text=f.help_text, secret=f.secret,
            has_value=bool(env.get(f.key)),
        )
        for f in source.fields
    ]
    return SourceStatus(
        id=source.id, label=source.label, implemented=source.implemented,
        enabled=enabled, fields=fields, last_check=LastCheck(status="unknown"),
    )


def _require_source(source_id: str):
    source = get_source(source_id)
    if source is None:
        raise_http(DomainError(ErrorCategory.INVALID_DATA, f"Fonte '{source_id}' não existe."))
    return source


@router.get("")
async def list_settings() -> list[SourceStatus]:
    env = load_env(_ENV_PATH)
    return [_source_status(s, env) for s in SOURCES]


@router.put("/{source_id}")
async def update_settings(source_id: str, body: UpdateSourceRequest) -> SourceStatus:
    source = _require_source(source_id)

    values = dict(body.fields)
    if source.enabled_key is not None and body.enabled is not None:
        values[source.enabled_key] = "true" if body.enabled else "false"
    try:
        set_env_values(_ENV_PATH, values)
    except ValueError:
        raise_http(DomainError(
            ErrorCategory.INVALID_DATA, "Valor informado é inválido.",
            "Remova quebras de linha do campo e tente novamente.",
        ))

    env = load_env(_ENV_PATH)
    return _source_status(source, env)


@router.post("/{source_id}/test")
async def test_settings(source_id: str) -> LastCheck:
    source = _require_source(source_id)

    if not source.implemented:
        return LastCheck(status="failed", message="Esta fonte ainda não está disponível nesta versão.")

    env = load_env(_ENV_PATH)
    try:
        provider = source.build(env)
        result: ConnectionTestResult = await provider.test_connection()
    except ProviderError as exc:
        return LastCheck(status="failed", message=str(exc))
    except Exception:  # noqa: BLE001 — última linha de defesa: nunca 500 nesta rota, nunca exceção crua ao usuário
        return LastCheck(status="failed", message="Não consegui verificar a conexão com esta fonte. Tente novamente.")

    return LastCheck(status="connected" if result.is_connected else "failed", message=result.message)
