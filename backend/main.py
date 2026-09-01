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
from core.config import sync_env
from core.db import create_engine, init_db, make_session_factory
from backend.routes_exports import router as exports_router

_MODULE_ROOT = Path(__file__).parent.parent
_DB_PATH = _MODULE_ROOT / "data" / "lead_tracker.db"

sdk = create_sdk("lead_tracker")
_engine = create_engine(_DB_PATH)
session_factory = make_session_factory(_engine)

router = APIRouter(prefix="/modules/lead_tracker", tags=["lead_tracker"])
router.include_router(exports_router)


@router.get("/ping")
async def ping():
    sdk.logger.info("ping called")
    return {"module": "lead_tracker", "status": "ok", "version": "0.1.1"}


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
        added = sync_env(_MODULE_ROOT / ".env", _MODULE_ROOT / "env-model")
        if added:
            sdk.logger.info("config: added missing keys from env-model: %s", added)
        await init_db(_engine)
        sdk.settings.set("installed", True)

    async def enable(self) -> None:
        sdk.logger.info("lead_tracker enable() called")
        added = sync_env(_MODULE_ROOT / ".env", _MODULE_ROOT / "env-model")
        if added:
            sdk.logger.info("config: added missing keys from env-model: %s", added)
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
        return HealthResult.ok("lead_tracker is healthy")

    async def uninstall(self) -> None:
        sdk.logger.info("lead_tracker uninstall() called")
        if _DB_PATH.exists():
            _DB_PATH.unlink()
        sdk.settings.reset()


module = LeadTrackerModule()
