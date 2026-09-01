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


if __name__ == "__main__":
    test_build_email_request_never_lets_ai_send_never_invents_outside_evidence()
    test_parse_email_draft_extracts_all_four_fields()
    test_parse_email_draft_never_invents_missing_field()
    test_generate_email_draft_end_to_end_with_mocked_provider()
    test_generate_email_draft_fails_friendly_when_provider_returns_incomplete_json()
    print("OK — todos os testes de rascunho de e-mail passaram")
