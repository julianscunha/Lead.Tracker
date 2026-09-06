"""Smoke tests de geração de rascunho de e-mail. Provider de IA
mockado com httpx.MockTransport, zero chamada de rede real."""
import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.base import AIProviderError, AIRequest
from ai.email_draft import build_email_request, generate_email_draft, parse_email_draft
from ai.openai_provider import OpenAIProvider

VALID_DRAFT = {
    "content": "ok",
    "evidence": ["veeam_vbr", "m365"],
    "confidence": 0.9,
    "subject": "Oportunidade de modernização de backup",
    "greeting": "Olá, equipe Aurora,",
    "body": "Notamos que vocês usam Veeam VBR e M365, sem VDC365 ainda.",
    "cta": "Podemos agendar 15 minutos essa semana?",
}


def _client_returning_content(json_content: dict) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(json_content)}}]})
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_build_email_request_never_lets_ai_send_never_invents_outside_evidence():
    req = build_email_request("Aurora", "cross-sell", ["veeam_vbr"], "justificativa", {"product_ids": ["veeam_vbr"]})
    assert isinstance(req, AIRequest)
    assert "nunca agressivo" in req.instruction.lower()
    assert "invente" in req.instruction.lower()


def test_parse_email_draft_extracts_all_four_fields():
    draft = parse_email_draft(VALID_DRAFT)
    assert draft.subject == VALID_DRAFT["subject"]
    assert draft.cta == VALID_DRAFT["cta"]


def test_parse_email_draft_never_invents_missing_field():
    incomplete = {"subject": "x", "greeting": "y"}  # sem body/cta
    try:
        parse_email_draft(incomplete)
        assert False, "deveria falhar em vez de inventar body/cta"
    except AIProviderError as exc:
        assert "body" in str(exc) and "cta" in str(exc)


def test_generate_email_draft_end_to_end_with_mocked_provider():
    async def run():
        client = _client_returning_content(VALID_DRAFT)
        provider = OpenAIProvider(api_key="k", client=client)
        draft = await generate_email_draft(provider, "Aurora", "cross-sell", ["veeam_vbr"], "just.", {})
        assert draft.subject == VALID_DRAFT["subject"]

    asyncio.run(run())


def test_generate_email_draft_fails_friendly_when_provider_returns_incomplete_json():
    async def run():
        client = _client_returning_content({"subject": "só isso"})
        provider = OpenAIProvider(api_key="k", client=client)
        try:
            await generate_email_draft(provider, "Aurora", "cross-sell", [], None, {})
            assert False, "deveria levantar AIProviderError"
        except AIProviderError:
            pass

    asyncio.run(run())


def test_build_email_request_includes_primary_reason_in_provider_data():
    req = build_email_request("Aurora", "cross-sell", ["veeam_vbr"], "justificativa", {}, primary_reason="motivo forte")
    assert req.provider_data["motivo_principal"] == "motivo forte"


def test_build_email_request_defaults_primary_reason_to_justification():
    req = build_email_request("Aurora", "cross-sell", ["veeam_vbr"], "justificativa", {})
    assert req.provider_data["motivo_principal"] == "justificativa"


def test_parse_email_draft_echoes_primary_reason_never_from_ai_response():
    """primary_reason nunca vem do `structured` (resposta da IA) — mesmo que
    a IA devolva algo em 'motivo_principal' na resposta (não deveria, mas
    nunca deve ser confiado), o valor no EmailDraft é sempre o passado como
    argumento (dado de entrada, decidido pelo motor de regras)."""
    poisoned = {**VALID_DRAFT, "motivo_principal": "coisa que a IA inventou"}
    draft = parse_email_draft(poisoned, primary_reason="motivo real do motor de regras")
    assert draft.primary_reason == "motivo real do motor de regras"


def test_parse_email_draft_primary_reason_defaults_to_none():
    draft = parse_email_draft(VALID_DRAFT)
    assert draft.primary_reason is None


def test_parse_email_draft_never_falls_back_to_structured_when_no_primary_reason_given():
    """Achado da revisão de código: trava especificamente contra a regressão
    mais provável nesta blindagem — um "fallback de conveniência" tipo
    `primary_reason or structured.get("motivo_principal")` pareceria
    inofensivo, mas reabriria a porta pra IA decidir o motivo quando o
    chamador não informar um. Sem `primary_reason` explícito, o campo tem
    que ficar None mesmo que `structured` tenha um `motivo_principal`."""
    poisoned = {**VALID_DRAFT, "motivo_principal": "a IA decidiu isso sozinha"}
    draft = parse_email_draft(poisoned)
    assert draft.primary_reason is None


def test_generate_email_draft_echoes_primary_reason_end_to_end():
    async def run():
        client = _client_returning_content(VALID_DRAFT)
        provider = OpenAIProvider(api_key="k", client=client)
        draft = await generate_email_draft(
            provider, "Aurora", "cross-sell", ["veeam_vbr"], "just.", {}, primary_reason="motivo determinístico",
        )
        assert draft.primary_reason == "motivo determinístico"

    asyncio.run(run())


def test_generate_email_draft_falls_back_to_justification_when_no_primary_reason_given():
    async def run():
        client = _client_returning_content(VALID_DRAFT)
        provider = OpenAIProvider(api_key="k", client=client)
        draft = await generate_email_draft(provider, "Aurora", "cross-sell", [], "justificativa da regra", {})
        assert draft.primary_reason == "justificativa da regra"

    asyncio.run(run())


def test_parse_email_draft_keeps_differentiator_that_passes_guardrails():
    draft = parse_email_draft(
        {**VALID_DRAFT, "differentiator": "Vocês já usam Veeam VBR sem VDC365 configurado."},
        evidence=["Veeam VBR presente", "VDC365 ausente"], portfolio={},
    )
    assert draft.differentiator == "Vocês já usam Veeam VBR sem VDC365 configurado."


def test_parse_email_draft_discards_differentiator_that_fails_guardrails_keeps_rest_of_draft():
    """Achado do Sales Engineer: campo reprovado é descartado, nunca derruba
    o resto do rascunho (subject/body/cta continuam intactos)."""
    draft = parse_email_draft(
        {**VALID_DRAFT, "differentiator": "Somos líder de mercado comprovado."},
        evidence=[], portfolio={},
    )
    assert draft.differentiator is None
    assert draft.subject == VALID_DRAFT["subject"]
    assert draft.body == VALID_DRAFT["body"]


def test_parse_email_draft_discards_ps_with_invented_number():
    draft = parse_email_draft(
        {**VALID_DRAFT, "ps": "Isso reduz custos em 90%."}, evidence=["nenhum dado de redução"], portfolio={},
    )
    assert draft.ps is None


def test_parse_email_draft_guardrail_exception_discards_only_that_field():
    """Achado da revisão de código: qualquer exceção dentro do guard-rail
    (ex.: RecursionError num portfolio anormal) nunca pode derrubar a
    geração inteira — só descarta o campo persuasivo."""
    import ai.email_draft as email_draft_module

    def _boom(*args, **kwargs):
        raise RuntimeError("guard-rail explodiu")

    original = email_draft_module.validate_persuasive_field
    email_draft_module.validate_persuasive_field = _boom
    try:
        draft = parse_email_draft({**VALID_DRAFT, "differentiator": "qualquer coisa"}, evidence=[], portfolio={})
    finally:
        email_draft_module.validate_persuasive_field = original
    assert draft.differentiator is None
    assert draft.subject == VALID_DRAFT["subject"]


def test_parse_email_draft_without_differentiator_or_ps_leaves_them_none():
    draft = parse_email_draft(VALID_DRAFT)
    assert draft.differentiator is None
    assert draft.ps is None


def test_generate_email_draft_validates_differentiator_against_real_evidence_end_to_end():
    async def run():
        client = _client_returning_content({**VALID_DRAFT, "differentiator": "Isso reduz custos em 40%."})
        provider = OpenAIProvider(api_key="k", client=client)
        draft = await generate_email_draft(
            provider, "Aurora", "cross-sell", ["redução de 40% documentada"], "just.", {},
        )
        assert draft.differentiator == "Isso reduz custos em 40%."

    asyncio.run(run())


def test_generate_email_draft_discards_differentiator_not_backed_by_real_evidence_end_to_end():
    async def run():
        client = _client_returning_content({**VALID_DRAFT, "differentiator": "Isso reduz custos em 40%."})
        provider = OpenAIProvider(api_key="k", client=client)
        draft = await generate_email_draft(provider, "Aurora", "cross-sell", ["evidência sem número"], "just.", {})
        assert draft.differentiator is None

    asyncio.run(run())


if __name__ == "__main__":
    test_build_email_request_never_lets_ai_send_never_invents_outside_evidence()
    test_parse_email_draft_extracts_all_four_fields()
    test_parse_email_draft_never_invents_missing_field()
    test_generate_email_draft_end_to_end_with_mocked_provider()
    test_generate_email_draft_fails_friendly_when_provider_returns_incomplete_json()
    test_build_email_request_includes_primary_reason_in_provider_data()
    test_build_email_request_defaults_primary_reason_to_justification()
    test_parse_email_draft_echoes_primary_reason_never_from_ai_response()
    test_parse_email_draft_primary_reason_defaults_to_none()
    test_parse_email_draft_never_falls_back_to_structured_when_no_primary_reason_given()
    test_generate_email_draft_echoes_primary_reason_end_to_end()
    test_generate_email_draft_falls_back_to_justification_when_no_primary_reason_given()
    test_parse_email_draft_keeps_differentiator_that_passes_guardrails()
    test_parse_email_draft_discards_differentiator_that_fails_guardrails_keeps_rest_of_draft()
    test_parse_email_draft_discards_ps_with_invented_number()
    test_parse_email_draft_guardrail_exception_discards_only_that_field()
    test_parse_email_draft_without_differentiator_or_ps_leaves_them_none()
    test_generate_email_draft_validates_differentiator_against_real_evidence_end_to_end()
    test_generate_email_draft_discards_differentiator_not_backed_by_real_evidence_end_to_end()
    print("OK — todos os testes de rascunho de e-mail passaram")
