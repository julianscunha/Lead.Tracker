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
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.db_session import session_factory
from backend.http_errors import raise_http
from backend.settings import SOURCES, get_source
from core.config import load_env, set_env_values
from core.errors import DomainError, ErrorCategory
from core.geo_promotion import (
    GEO_PROMOTION_DAILY_CAP_ENV_KEY, GEO_PROMOTION_MIN_SCORE_ENV_KEY, parse_promotion_daily_cap,
    parse_promotion_min_score,
)
from core.field_mapping import detect_broken_mappings
from core.models import FieldMapping, SemanticFieldRole
from core.opportunity_engine import AGING_SLA_ENV_KEY, field_mapping_id, parse_aging_sla_days
from core.repository import delete_field_mapping, list_field_mappings, save_field_mapping
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


class AgingSlaConfig(BaseModel):
    days: int


@router.get("/config/aging-sla-days")
async def get_aging_sla_days() -> AgingSlaConfig:
    return AgingSlaConfig(days=parse_aging_sla_days(load_env(_ENV_PATH)))


@router.put("/config/aging-sla-days")
async def update_aging_sla_days(body: AgingSlaConfig) -> AgingSlaConfig:
    if body.days < 1:
        raise_http(DomainError(ErrorCategory.INVALID_DATA, "O prazo precisa ser de pelo menos 1 dia."))
    set_env_values(_ENV_PATH, {AGING_SLA_ENV_KEY: str(body.days)})
    return AgingSlaConfig(days=body.days)


class GeoPromotionConfig(BaseModel):
    min_score: float
    daily_cap: int


@router.get("/config/geo-promotion")
async def get_geo_promotion_config() -> GeoPromotionConfig:
    env = load_env(_ENV_PATH)
    return GeoPromotionConfig(min_score=parse_promotion_min_score(env), daily_cap=parse_promotion_daily_cap(env))


@router.put("/config/geo-promotion")
async def update_geo_promotion_config(body: GeoPromotionConfig) -> GeoPromotionConfig:
    if not (0.0 <= body.min_score <= 1.0):
        raise_http(DomainError(ErrorCategory.INVALID_DATA, "O score mínimo precisa estar entre 0.0 e 1.0."))
    if body.daily_cap < 1:
        raise_http(DomainError(ErrorCategory.INVALID_DATA, "O limite diário precisa ser de pelo menos 1."))
    set_env_values(_ENV_PATH, {
        GEO_PROMOTION_MIN_SCORE_ENV_KEY: str(body.min_score), GEO_PROMOTION_DAILY_CAP_ENV_KEY: str(body.daily_cap),
    })
    return GeoPromotionConfig(min_score=body.min_score, daily_cap=body.daily_cap)


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


# ── Fase F, módulo 5 (`mapping-config-ui`) ────────────────────────────────────
# Só Salesforce tem catálogo/mapeamento nesta fase — provider_id fica fixo
# aqui na rota (camada de aplicação), não no core (core/field_mapping.py,
# core/repository.py continuam genéricos, sem saber que só um provider
# popula isso hoje).
_FIELD_MAPPING_PROVIDER_ID = "salesforce"


class FieldCatalogItem(BaseModel):
    source_field_api_name: str
    source_field_label: str
    field_type: str | None = None
    role: SemanticFieldRole | None = None
    broken: bool = False
    broken_message: str | None = None


@router.get("/salesforce/field-catalog")
async def get_salesforce_field_catalog(force_refresh: bool = False) -> list[FieldCatalogItem]:
    """Sales Engineer consultado (docs/specs/fase-f-mapeamento-campo-personalizado.md,
    módulo 5): a tela nunca mostra o campo cru sem contexto — cada linha já
    chega com o papel atualmente mapeado (ou nenhum), pra tabela renderizar
    direto sem uma segunda chamada.

    Módulo 6 (`mapping-health-check`): mapeamento cujo campo sumiu do
    catálogo atual (removido/renomeado no Salesforce) ainda aparece como
    linha própria, marcada `broken=True` — Sales Engineer consultado: o
    aviso precisa aparecer aqui, não só no health_check técnico do Core,
    porque é o único lugar que o vendedor/admin de vendas realmente abre."""
    env = load_env(_ENV_PATH)
    source = _require_source(_FIELD_MAPPING_PROVIDER_ID)
    try:
        provider = source.build(env)
        fields = await provider.describe_custom_account_fields(force_refresh=force_refresh)
    except ProviderError as exc:
        raise_http(exc)

    async with session_factory() as session:
        mappings = await list_field_mappings(session, _FIELD_MAPPING_PROVIDER_ID)
    role_by_field = {m.source_field_api_name: m.role for m in mappings}
    catalog_field_names = {f.name for f in fields}

    items = [
        FieldCatalogItem(
            source_field_api_name=f.name, source_field_label=f.label, field_type=f.type,
            role=role_by_field.get(f.name),
        )
        for f in fields
    ]
    items.extend(
        FieldCatalogItem(
            source_field_api_name=b.source_field_api_name, source_field_label=b.source_field_label,
            role=b.role, broken=True, broken_message=b.business_message(),
        )
        for b in detect_broken_mappings(mappings, catalog_field_names)
    )
    return items


class FieldMappingRequest(BaseModel):
    source_field_api_name: str
    source_field_label: str
    role: SemanticFieldRole


class FieldMappingResponse(BaseModel):
    source_field_api_name: str
    role: SemanticFieldRole
    reassigned_from_api_name: str | None = None
    reassigned_from_label: str | None = None


@router.put("/salesforce/field-mapping")
async def upsert_salesforce_field_mapping(body: FieldMappingRequest) -> FieldMappingResponse:
    """Sales Engineer consultado: um papel só pode ter uma fonte por vez —
    mapear um 2º campo pro mesmo papel reatribui automaticamente (nunca os
    dois mapeados silenciosamente ao mesmo papel), e o front mostra um
    toast curto avisando a troca. `reassigned_from_api_name` (achado da
    revisão de código) é o identificador estável pro front reconciliar
    estado local — `reassigned_from_label` é só pra compor a frase do
    toast; dois campos com o mesmo rótulo (org mal configurada) não podem
    depender do rótulo pra decidir qual linha perdeu o papel."""
    async with session_factory() as session:
        existing = await list_field_mappings(session, _FIELD_MAPPING_PROVIDER_ID)
        reassigned_from_api_name = None
        reassigned_from_label = None
        for mapping in existing:
            if mapping.role == body.role and mapping.source_field_api_name != body.source_field_api_name:
                await delete_field_mapping(session, mapping.id)
                reassigned_from_api_name = mapping.source_field_api_name
                reassigned_from_label = mapping.source_field_label

        try:
            await save_field_mapping(session, FieldMapping(
                id=field_mapping_id(_FIELD_MAPPING_PROVIDER_ID, body.source_field_api_name),
                provider_id=_FIELD_MAPPING_PROVIDER_ID, source_field_api_name=body.source_field_api_name,
                source_field_label=body.source_field_label, role=body.role,
            ))
        except IntegrityError:
            # UniqueConstraint(provider_id, role) barrou uma corrida real
            # (duas requisições reatribuindo o mesmo papel ao mesmo tempo) —
            # nunca vaza IntegrityError crua, pede pro usuário tentar de novo
            # vendo o estado já atualizado.
            await session.rollback()
            raise_http(DomainError(
                ErrorCategory.INVALID_DATA,
                "Esse papel acabou de ser atribuído a outro campo por outra pessoa.",
                "Atualize a tela e tente novamente.",
            ))

    return FieldMappingResponse(
        source_field_api_name=body.source_field_api_name, role=body.role,
        reassigned_from_api_name=reassigned_from_api_name, reassigned_from_label=reassigned_from_label,
    )


@router.delete("/salesforce/field-mapping/{source_field_api_name}")
async def unmap_salesforce_field(source_field_api_name: str) -> dict:
    """Desfazer é sempre permitido e sem confirmação — campo volta a ser
    contexto bruto pra IA, nunca um estado de erro (Sales Engineer:
    mapeamento é 100% opcional e reversível a qualquer momento)."""
    mapping_id = field_mapping_id(_FIELD_MAPPING_PROVIDER_ID, source_field_api_name)
    async with session_factory() as session:
        await delete_field_mapping(session, mapping_id)
    return {"unmapped": True}
