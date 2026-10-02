"""POST /exports/business-case — banco temporário, IA mockada, empresas fictícias, zero rede."""
import asyncio
import re
import sys
import tempfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / ".techforge-dev" / "sdk" / "python"))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import main as backend_main
from ai.base import AIProvider, AIResponse
from backend import routes_exports, routes_settings, routes_sync
from core.db import create_engine, init_db, make_session_factory
from core.errors import DomainError, ErrorCategory
from exports.errors import wrap_export_errors
from core.models import Company, Opportunity, Product, Service, SourceRef
from core.repository import save_company, save_opportunity, save_product, save_service

app = FastAPI()
app.include_router(backend_main.router)
client = TestClient(app)
URL = "/modules/lead_tracker/exports/business-case"
SECRET = "PERGUNTA-SECRETA-DA-TELA"


class FakeProvider(AIProvider):
    def __init__(self, behavior="echo"):
        self.calls, self.behavior = 0, behavior

    @property
    def id(self):
        return "fake"

    async def generate(self, request):
        self.calls += 1
        if self.behavior == "domain":
            raise DomainError(ErrorCategory.AI, "indisponível")
        if self.behavior == "timeout":
            raise TimeoutError()
        return AIResponse(content="", structured={"secoes": dict(request.provider_data["secoes"])})

    async def test_connection(self): ...
    async def health_check(self): ...


@pytest.fixture
def env(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        engine = create_engine(Path(d) / "t.db")
        asyncio.run(init_db(engine))
        sf = make_session_factory(engine)
        monkeypatch.setattr(routes_exports, "session_factory", sf, raising=False)
        monkeypatch.setattr(routes_sync, "session_factory", sf)
        monkeypatch.setattr(routes_settings, "_ENV_PATH", Path(d) / ".env")
        (Path(d) / ".env").write_text("APP_ENV=local\n", encoding="utf-8")
        state = {"env": {}, "built": 0, "provider": FakeProvider()}

        def _create(*a, **k):
            state["built"] += 1
            return state["provider"]

        monkeypatch.setattr(routes_exports, "load_env", lambda *_: state["env"])
        monkeypatch.setattr(routes_exports, "create_ai_provider", _create)
        state["sf"] = sf
        yield state


def seed(sf, name="Empresa Alfa Ltda", evidence=("Backup local instalado", "Microsoft 365 em uso"),
         with_company=True, with_item=True, service=False):
    async def go():
        async with sf() as s:
            c = Company(name=name)
            if with_company:
                await save_company(s, c)
            p = Product(vendor_id="v1", name="Nuvem Segura", description="Backup gerenciado em nuvem.")
            sv = Service(name="Consultoria Segura", description="Revisão de proteção.")
            await save_product(s, p)
            await save_service(s, sv)
            o = Opportunity(
                company_id=c.id, type="cross-sell", opportunity_score=0.9, financial_potential=0.5,
                strategic_score=0.2, confidence_score=0.8, evidence=list(evidence),
                justification="Há uma lacuna de proteção em nuvem.", sources=[SourceRef(type="csv")],
                discovery_prompt=SECRET,
                product_id=None if service or not with_item else p.id,
                service_id=sv.id if service and with_item else None,
            )
            await save_opportunity(s, o)
            return o.id
    return asyncio.run(go())


def _content(pdf: bytes) -> str:
    out = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        try:
            data = zlib.decompressobj().decompress(m.group(1))
        except zlib.error:
            continue
        out += re.findall(rb"\(((?:[^()\\]|\\.)*)\)\s*Tj", data)
    return b"\n".join(out).decode("latin-1")


def test_200_pdf_headers_sem_discovery_prompt(env):
    oid = seed(env["sf"])
    r = client.post(URL, json={"opportunity_id": oid})
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-prosa-fonte"] == "deterministica"
    assert "Empresa Alfa" in _content(r.content) and SECRET not in _content(r.content)
    assert 'filename="business-case-Empresa-Alfa-Ltda.pdf"' in r.headers["content-disposition"]


def test_200_com_servico(env):
    oid = seed(env["sf"], service=True)
    assert client.post(URL, json={"opportunity_id": oid}).status_code == 200


def test_404_oportunidade_inexistente(env):
    r = client.post(URL, json={"opportunity_id": "nao-existe"})
    assert r.status_code == 404 and "Traceback" not in r.text


def test_404_empresa_removida(env):
    assert client.post(URL, json={"opportunity_id": seed(env["sf"], with_company=False)}).status_code == 404


def test_422_oportunidade_sem_produto_nem_servico(env):
    r = client.post(URL, json={"opportunity_id": seed(env["sf"], with_item=False)})
    assert r.status_code == 422
    assert "Esta oportunidade ainda não está ligada a um produto ou serviço do portfólio, então não dá para montar o business case." in r.json()["detail"]


def test_404_item_do_portfolio_removido(env):
    async def go():
        async with env["sf"]() as s:
            c = Company(name="Beta Ltda")
            await save_company(s, c)
            o = Opportunity(company_id=c.id, type="cross-sell", evidence=["x"], product_id="removido",
                            sources=[SourceRef(type="csv")])
            await save_opportunity(s, o)
            return o.id
    r = client.post(URL, json={"opportunity_id": asyncio.run(go())})
    assert r.status_code == 404 and "Traceback" not in r.text


def test_422_sem_evidencia(env):
    r = client.post(URL, json={"opportunity_id": seed(env["sf"], evidence=())})
    assert r.status_code == 422
    assert "faltam evidências" in r.json()["detail"]
    assert "Traceback" not in r.text and "SELECT" not in r.text


def test_sem_ia_nao_constroi_nem_chama_provider(env):
    oid = seed(env["sf"])
    env["env"] = {"AI_API_KEY": "k"}
    client.post(URL, json={"opportunity_id": oid})
    client.post(URL, json={"opportunity_id": oid, "usar_ia": False})
    assert env["built"] == 0 and env["provider"].calls == 0


def test_ia_sem_chave_degrada(env):
    r = client.post(URL, json={"opportunity_id": seed(env["sf"]), "usar_ia": True})
    assert r.status_code == 200 and r.headers["x-prosa-fonte"] == "deterministica"
    assert env["built"] == 0


@pytest.mark.parametrize("behavior", ["domain", "timeout"])
def test_ia_com_falha_degrada(env, behavior):
    env["env"] = {"AI_API_KEY": "k"}
    env["provider"] = FakeProvider(behavior)
    r = client.post(URL, json={"opportunity_id": seed(env["sf"]), "usar_ia": True})
    assert r.status_code == 200 and r.headers["x-prosa-fonte"] == "deterministica"
    assert env["provider"].calls == 1


class RewriteProvider(FakeProvider):
    """Reescreve só a situação (mesmos fatos); as demais seções voltam como vieram."""
    async def generate(self, request):
        self.calls += 1
        secoes = dict(request.provider_data["secoes"])
        secoes["situacao"] = "A Empresa Alfa Ltda tem Backup local instalado e Microsoft 365 em uso."
        return AIResponse(content="", structured={"secoes": secoes})


def test_ia_resposta_boa(env):
    env["env"] = {"AI_API_KEY": "k"}
    env["provider"] = RewriteProvider()
    r = client.post(URL, json={"opportunity_id": seed(env["sf"]), "usar_ia": True})
    assert r.status_code == 200 and r.headers["x-prosa-fonte"] in ("ia", "mista")
    txt = _content(r.content)
    assert "tem Backup local instalado e Microsoft 365 em uso" in txt
    assert "Evidências: Backup local instalado; Microsoft 365 em uso." not in txt
    assert env["provider"].calls == 1


def test_500_erro_interno_de_pdf_sem_vazar(env, monkeypatch):
    @wrap_export_errors
    def business_case_pdf(*a, **k):
        raise RuntimeError("Empresa Alfa Ltda detalhe de CRM")

    monkeypatch.setattr(routes_exports, "business_case_pdf", business_case_pdf)
    r = client.post(URL, json={"opportunity_id": seed(env["sf"])})
    assert r.status_code == 500
    assert "Não foi possível gerar o arquivo. Tente novamente ou contate o suporte." in r.text
    assert "business_case_pdf" not in r.text and "Empresa Alfa" not in r.text and "CRM" not in r.text
    assert "Traceback" not in r.text


def test_nome_so_simbolos_usa_fallback(env):
    r = client.post(URL, json={"opportunity_id": seed(env["sf"], name="😀!!! ###")})
    assert r.status_code == 200
    assert 'filename="business-case-empresa.pdf"' in r.headers["content-disposition"]


def test_create_provider_com_erro_degrada(env, monkeypatch):
    env["env"] = {"AI_API_KEY": "k"}

    def boom(*a, **k):
        raise DomainError(ErrorCategory.CONFIGURATION, "x")

    monkeypatch.setattr(routes_exports, "create_ai_provider", boom)
    r = client.post(URL, json={"opportunity_id": seed(env["sf"]), "usar_ia": True})
    assert r.status_code == 200 and r.headers["x-prosa-fonte"] == "deterministica"


def test_nome_malicioso_no_content_disposition(env):
    oid = seed(env["sf"], name="Acme\r\nX-Evil: 1 ../../é")
    r = client.post(URL, json={"opportunity_id": oid})
    assert r.status_code == 200 and "x-evil" not in r.headers
    cd = r.headers["content-disposition"]
    assert not re.search(r"[\r\n/]|\.\.", cd) and "X-Evil: " not in cd


def test_422_campo_extra(env):
    r = client.post(URL, json={"opportunity_id": "abc", "financial_potential": 1})
    assert r.status_code == 422


@pytest.mark.parametrize("bad", ["../x", "", "a" * 200, "abc\n"])
def test_422_id_invalido(env, bad):
    assert client.post(URL, json={"opportunity_id": bad}).status_code == 422


def test_opportunity_out_traz_discovery_prompt(env):
    seed(env["sf"])
    r = client.get("/modules/lead_tracker/opportunities")
    assert r.status_code == 200 and r.json()[0]["discovery_prompt"] == SECRET
