"""Sugestão de regras pela IA — guardrail e prompt (provider de IA falso, catálogo fictício, sem rede)."""
import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.base import AIProvider, AIProviderError, AIResponse  # noqa: E402
from ai.rule_guardrails import MAX_RULE_SUGGESTIONS, validate_rule_suggestions  # noqa: E402
from ai.rule_suggest import build_catalog, suggest_rules  # noqa: E402
from core.errors import DomainError  # noqa: E402
from core.models import CorrelationRule, Product, ProductRelation, Service, Vendor  # noqa: E402
from providers.base import ConnectionTestResult  # noqa: E402

VENDOR = Vendor(id="v1", name="Fabrica Alfa")
PRODUCTS = [
    Product(id="p1", vendor_id="v1", name="Alfa Backup", category="Backup", description="DESCRICAO-SECRETA",
            related_services=[ProductRelation(service_id="s1", relation_type="prerequisite")]),
    Product(id="p2", vendor_id="v1", name="Alfa Monitor", category="Monitoramento"),
]
SERVICES = [Service(id="s1", name="Consultoria Beta", category="Consultoria")]
CATALOG, _ = build_catalog([VENDOR], PRODUCTS, SERVICES)


def _rule(**kw):
    base = {"tipo_oportunidade": "cross-sell", "justificativa": "Tem backup e falta monitoramento.",
            "requer": ["p1"], "ausente": ["p2"], "requer_categoria": [], "ausente_categoria": [], "relacao": None}
    base.update(kw)
    return base


def _ok(raw, existing=()):
    return validate_rule_suggestions(raw if isinstance(raw, list) else [raw], CATALOG, list(existing))


def test_valid_item_rule_passes_and_ai_extras_are_ignored():
    ok, discarded = _ok(_rule(estimated_deal_value=999999, opportunity_score=9, confidence_score=9, active=False))
    assert discarded == 0 and len(ok) == 1
    assert not hasattr(ok[0], "estimated_deal_value") and ok[0].requires == ["p1"] and ok[0].absent == ["p2"]


@pytest.mark.parametrize("bad", [
    _rule(requer=["p-inventado"]),                                      # id inventado
    _rule(ausente=["p-inventado"]),
    _rule(requer=[], ausente=[], requer_categoria=["Categoria Falsa"]),  # categoria inventada
    _rule(requer=["p1"], requer_categoria=["Backup"]),                   # dois mecanismos
    _rule(relacao="substitute", requer=[], ausente=[]),                  # relação sem ProductRelation no catálogo
    _rule(relacao="complementary", requer=[], ausente=[]),
    _rule(relacao="prerequisite"),                                       # relação + itens = dois mecanismos
    _rule(requer=["p1"], ausente=["p1"]),                                # mesmo item em requer e ausente
    _rule(requer=[], ausente=["p2"]),                                    # sem condição positiva
    _rule(requer=[], ausente=[], requer_categoria=[]),                   # nenhum mecanismo
    _rule(justificativa="curta"),
    _rule(justificativa="x" * 301),
    _rule(justificativa="Veja https://evil.example/x para detalhes."),
    _rule(justificativa="Visite www.evil.example agora mesmo."),
    _rule(justificativa="Tem <b>backup</b> e falta monitoramento."),
    _rule(justificativa="Tem backup‮ e falta monitoramento."),      # bidi
    _rule(tipo_oportunidade="x"), _rule(tipo_oportunidade="a" * 41), _rule(tipo_oportunidade="cross;sell"),
    _rule(tipo_oportunidade="a​b"),
    _rule(requer="p1"), _rule(requer=[1]), "texto solto", 42, None, ["lista"],
])
def test_untrusted_rules_are_discarded_and_counted(bad):
    ok, discarded = validate_rule_suggestions([bad], CATALOG, [])
    assert ok == [] and discarded == 1


def test_category_is_matched_ignoring_case_and_rewritten_with_catalog_spelling():
    ok, _ = _ok(_rule(requer=[], ausente=[], requer_categoria=["backup"], ausente_categoria=["MONITORAMENTO"]))
    assert ok[0].requires_category == ["Backup"] and ok[0].absent_category == ["Monitoramento"]


def test_relation_accepted_only_when_catalog_has_that_type():
    ok, _ = _ok(_rule(relacao="prerequisite", requer=[], ausente=[]))
    assert len(ok) == 1 and ok[0].relation_type == "prerequisite"


def test_duplicates_against_existing_rules_and_among_suggestions_are_dropped_quietly():
    existing = CorrelationRule(opportunity_type="x", justification="regra já existente",
                               requires_category=["Backup"], absent_category=["Monitoramento"])
    same_as_existing = _rule(requer=[], ausente=[], requer_categoria=["backup"], ausente_categoria=["monitoramento"])
    ok, discarded = _ok([same_as_existing, _rule(), _rule(tipo_oportunidade="outro", justificativa="Outra justificativa válida.")],
                        existing=[existing])
    assert len(ok) == 1 and discarded == 0


def test_limit_of_suggestions_and_excess_counts_as_discarded():
    many = [_rule(justificativa=f"Justificativa número {i} válida.", requer=["p1"], ausente=[], requer_categoria=[])
            for i in range(1)]
    cats = [f"C{i}" for i in range(MAX_RULE_SUGGESTIONS + 3)]
    products = [Product(id=f"q{i}", vendor_id="v1", name=f"Item {i}", category=c) for i, c in enumerate(cats)]
    catalog, _ = build_catalog([VENDOR], products, [])
    raw = [_rule(requer=[f"q{i}"], ausente=[]) for i in range(len(cats))] + many
    ok, discarded = validate_rule_suggestions(raw, catalog, [])
    assert len(ok) == MAX_RULE_SUGGESTIONS and discarded == 4


def test_non_list_response_is_not_accepted():
    assert validate_rule_suggestions({"regras": []}, CATALOG, []) == ([], 0)


class _FakeAI(AIProvider):
    def __init__(self, structured):
        self._structured = structured
        self.requests = []

    @property
    def id(self):
        return "fake"

    async def test_connection(self):
        return ConnectionTestResult.ok()

    async def generate(self, request):
        self.requests.append(request)
        return AIResponse(content="", structured=self._structured)


def _run(ai, existing=()):
    return asyncio.run(suggest_rules(ai, [VENDOR], PRODUCTS, SERVICES, list(existing)))


def test_prompt_has_catalog_only_no_descriptions_values_or_secrets():
    ai = _FakeAI({"regras": [_rule()]})
    ok, discarded, _ = _run(ai, [CorrelationRule(opportunity_type="x", justification="JUSTIFICATIVA-EXISTENTE",
                                                 requires=["p1"], estimated_deal_value=50000)])
    assert len(ok) == 1 and discarded == 0
    request = ai.requests[0]
    payload = json.dumps(request.provider_data, ensure_ascii=False) + request.instruction
    for leak in ("DESCRICAO-SECRETA", "JUSTIFICATIVA-EXISTENTE", "50000", "estimated_deal_value", "AI_API_KEY", "http"):
        assert leak not in payload
    assert "DADO NÃO CONFIÁVEL" in request.instruction and "SOMENTE" in request.instruction
    item = request.provider_data["catalogo"]["itens"][0]
    assert item["id"] == "p1" and item["fabricante"] == "Fabrica Alfa" and item["relacoes"] == [{"service_id": "s1", "tipo": "prerequisite"}]


def test_catalog_is_capped_and_flagged_and_validation_uses_only_what_was_sent():
    products = [Product(id=f"q{i}", vendor_id="v1", name=f"Item {i}", category="Cat") for i in range(250)]
    items, truncated = build_catalog([VENDOR], products, [])
    assert len(items) == 200 and truncated
    ok, discarded = validate_rule_suggestions([_rule(requer=["q249"], ausente=[], requer_categoria=[])], items, [])
    assert ok == [] and discarded == 1  # q249 ficou fora do catálogo enviado


def test_malformed_ai_output_is_a_friendly_error_and_empty_catalog_never_calls_the_ai():
    for bad in ({"outra_coisa": 1}, {"regras": "texto"}):
        with pytest.raises(AIProviderError):
            _run(_FakeAI(bad))
    silent = _FakeAI({"regras": [_rule()]})
    with pytest.raises(DomainError):
        asyncio.run(suggest_rules(silent, [VENDOR], [], [], []))
    assert silent.requests == []


@pytest.mark.parametrize("texto", ["Veja javascript:alert(1) agora ok", "Acesse //evil.example para ver", "Detalhes em exemplo.com sobre o caso"])
def test_justification_with_scheme_or_domain_is_discarded(texto):
    ok, discarded = _ok(_rule(justificativa=texto))
    assert ok == [] and discarded == 1


def test_huge_catalog_names_and_existing_rules_are_capped_in_the_prompt():
    from ai.rule_suggest import MAX_EXISTING_RULES, MAX_FIELD_CHARS, build_request
    big = [Product(id="p9", vendor_id="v1", name="N" * 5000, category="C" * 5000)]
    catalog, _ = build_catalog([VENDOR], big, [])
    existing = [CorrelationRule(opportunity_type="x", justification="y" * 12, requires=[f"i{n}"]) for n in range(MAX_EXISTING_RULES + 30)]
    data = build_request(catalog, False, existing).provider_data
    assert len(data["catalogo"]["itens"][0]["nome"]) <= MAX_FIELD_CHARS and len(data["catalogo"]["itens"][0]["categoria"]) <= MAX_FIELD_CHARS
    assert len(data["regras_existentes"]) == MAX_EXISTING_RULES
