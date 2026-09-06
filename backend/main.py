"""
lead_tracker — Backend Entry Point
====================================
Esqueleto instalável do módulo. Sem lógica de negócio ainda —
só o contrato Tech.Forge (install/enable/disable/upgrade/health_check/uninstall)
e o router mínimo para o Plugin Loader montar.
"""
import sys
from pathlib import Path

# Permite rodar a partir do diretório do módulo durante o desenvolvimento local
# contra o clone do Tech.Forge Core em .techforge-dev/ (não versionado).
_techforge_sdk_path = Path(__file__).parent.parent / ".techforge-dev" / "sdk" / "python"
if _techforge_sdk_path.exists():
    sys.path.insert(0, str(_techforge_sdk_path))

from fastapi import APIRouter
from sqlalchemy import select
from techforge_sdk import create_sdk
from techforge_sdk.contracts import ModuleContract, ModuleMetadata, HealthResult

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.settings import get_source
from core.config import load_env, sync_env
from core.db import init_db
from core.field_mapping import detect_broken_mappings
from core.repository import list_field_mappings
from backend.db_session import DB_PATH as _DB_PATH, engine as _engine, session_factory
from backend.routes_exports import router as exports_router
from backend.routes_settings import router as settings_router
from backend.routes_sync import router as sync_router
from providers.base import ProviderError

_MODULE_ROOT = Path(__file__).parent.parent

sdk = create_sdk("lead_tracker")

router = APIRouter(prefix="/modules/lead_tracker", tags=["lead_tracker"])
router.include_router(exports_router)
router.include_router(settings_router)
router.include_router(sync_router)


@router.get("/ping")
async def ping():
    sdk.logger.info("ping called")
    return {"module": "lead_tracker", "status": "ok", "version": "0.1.1"}


async def _check_field_mappings_health() -> list:
    """Fase F, módulo 6 (`mapping-health-check`) — só paga o custo de
    `describe_custom_account_fields()` quando existe pelo menos 1
    mapeamento salvo pra Salesforce, mesmo princípio de custo zero do
    módulo 4. Salesforce mal configurado/indisponível nunca derruba o
    health_check do módulo inteiro — isso já é responsabilidade do botão
    "Testar conexão" em Configurações; aqui, silenciosamente não reporta
    mapeamento quebrado nesse ciclo (tenta de novo no próximo).

    `force_refresh=True` é obrigatório aqui (achado da revisão de código):
    decisão já registrada na spec do módulo 1 — sem isso, "funciona por
    acidente" hoje só porque cada chamada cria uma instância nova do
    provider (cache em memória nunca sobrevive entre chamadas); se um dia
    o `build` virar singleton/cacheado por outro motivo, este health check
    passaria a confiar silenciosamente num catálogo de até 1h desatualizado
    — exatamente o cenário que ele existe pra detectar."""
    async with session_factory() as session:
        mappings = await list_field_mappings(session, "salesforce")
    if not mappings:
        return []

    source = get_source("salesforce")
    if source is None or source.build is None:
        return []
    try:
        env = load_env(_MODULE_ROOT / ".env")
        provider = source.build(env)
        catalog = await provider.describe_custom_account_fields(force_refresh=True)
    except ProviderError:
        return []

    return detect_broken_mappings(mappings, {f.name for f in catalog})


class LeadTrackerModule(ModuleContract):

    @property
    def metadata(self) -> ModuleMetadata:
        return ModuleMetadata(
            id="lead_tracker",
            name="Lead.Tracker",
            version="0.1.1",
            category="Sales",
            vendor="TechForge",
            author="TechForge Team",
            description="Opportunity Intelligence — esqueleto do módulo.",
            platform_min_version="1.0.0",
            platform_max_version="2.0.0",
        )

    async def install(self) -> None:
        sdk.logger.info("lead_tracker install() called")
        added = sync_env(_MODULE_ROOT / ".env", _MODULE_ROOT / ".env-model")
        if added:
            sdk.logger.info("config: added missing keys from .env-model: %s", added)
        await init_db(_engine)
        sdk.settings.set("installed", True)

    async def enable(self) -> None:
        sdk.logger.info("lead_tracker enable() called")
        added = sync_env(_MODULE_ROOT / ".env", _MODULE_ROOT / ".env-model")
        if added:
            sdk.logger.info("config: added missing keys from .env-model: %s", added)
        await init_db(_engine)

    async def disable(self) -> None:
        sdk.logger.info("lead_tracker disable() called")

    async def upgrade(self, from_version: str) -> None:
        sdk.logger.info("lead_tracker upgrade() from %s", from_version)

    async def health_check(self) -> HealthResult:
        try:
            async with session_factory() as session:
                await session.execute(select(1))
        except Exception:
            return HealthResult.fail("lead_tracker: banco de dados inacessível")

        broken = await _check_field_mappings_health()
        if broken:
            return HealthResult.ok(
                f"lead_tracker is healthy — {len(broken)} mapeamento(s) de campo do Salesforce precisam de atenção",
                broken_field_mappings=[b.business_message() for b in broken],
            )
        return HealthResult.ok("lead_tracker is healthy")

    async def uninstall(self) -> None:
        sdk.logger.info("lead_tracker uninstall() called")
        if _DB_PATH.exists():
            _DB_PATH.unlink()
        sdk.settings.reset()


module = LeadTrackerModule()
