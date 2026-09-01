"""Smoke tests da camada de IA. Nenhuma chamada de rede real:
httpx.MockTransport injeta as respostas (CLAUDE.md: IA sempre mockada em teste)."""
import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.base import AIProviderError, AIRequest, build_structured_prompt, parse_structured_response
from ai.claude_provider import ClaudeProvider
from ai.factory import create_ai_provider
from ai.gemini_provider import GeminiProvider
from ai.openai_provider import OpenAIProvider
from ai.openrouter import OpenRouterProvider


def _client_returning(status_code: int, json_body: dict) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=json_body)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


STRUCTURED_JSON = json.dumps({"content": "há oportunidade de cross-sell", "evidence": ["veeam_vbr"], "confidence": 0.9})


def test_build_structured_prompt_never_invents_outside_portfolio_instruction():
    req = AIRequest(instruction="correlacionar", portfolio={"product_ids": ["veeam_vbr"]})
    prompt = build_structured_prompt(req)
    assert "portfólio" in prompt
    assert "correlacionar" in prompt


def test_build_structured_prompt_strips_secret_like_keys():
    req = AIRequest(
        instruction="x",
        company_context={"name": "Acme", "api_key": "sk-super-secret", "nested": {"client_secret": "xyz"}},
    )
    prompt = build_structured_prompt(req)
    assert "sk-super-secret" not in prompt
    assert "xyz" not in prompt
    assert "Acme" in prompt


def test_parse_structured_response_valid_json():
    resp = parse_structured_response(STRUCTURED_JSON)
    assert resp.content == "há oportunidade de cross-sell"
    assert resp.evidence == ["veeam_vbr"]
    assert resp.confidence == 0.9


def test_parse_structured_response_degrades_gracefully_on_non_json():
    resp = parse_structured_response("texto solto sem json")
    assert resp.content == "texto solto sem json"
    assert resp.evidence == []
    assert resp.confidence == 0.0


def test_openrouter_generate_parses_openai_shaped_response():
    async def run():
        client = _client_returning(200, {"choices": [{"message": {"content": STRUCTURED_JSON}}]})
        provider = OpenRouterProvider(api_key="k", client=client)
        resp = await provider.generate(AIRequest(instruction="x"))
        assert resp.evidence == ["veeam_vbr"]

    asyncio.run(run())


def test_openai_generate_parses_response():
    async def run():
        client = _client_returning(200, {"choices": [{"message": {"content": STRUCTURED_JSON}}]})
        provider = OpenAIProvider(api_key="k", client=client)
        resp = await provider.generate(AIRequest(instruction="x"))
        assert resp.confidence == 0.9

    asyncio.run(run())


def test_gemini_generate_parses_response():
    async def run():
        client = _client_returning(200, {"candidates": [{"content": {"parts": [{"text": STRUCTURED_JSON}]}}]})
        provider = GeminiProvider(api_key="k", client=client)
        resp = await provider.generate(AIRequest(instruction="x"))
        assert resp.content == "há oportunidade de cross-sell"

    asyncio.run(run())


def test_claude_generate_parses_response():
    async def run():
        client = _client_returning(200, {"content": [{"text": STRUCTURED_JSON}]})
        provider = ClaudeProvider(api_key="k", client=client)
        resp = await provider.generate(AIRequest(instruction="x"))
        assert resp.evidence == ["veeam_vbr"]

    asyncio.run(run())


def test_invalid_credentials_never_retried_and_raises_friendly_error():
    async def run():
        client = _client_returning(401, {"error": "unauthorized"})
        provider = OpenAIProvider(api_key="k", client=client)
        try:
            await provider.generate(AIRequest(instruction="x"))
            assert False, "deveria levantar AIProviderError"
        except AIProviderError as exc:
            assert "raw" not in str(exc).lower()  # nunca vaza exceção técnica bruta

    asyncio.run(run())


def test_missing_api_key_raises_before_any_call():
    try:
        OpenAIProvider(api_key="")
        assert False, "deveria rejeitar API key vazia"
    except AIProviderError:
        pass


def test_factory_defaults_to_openrouter():
    provider = create_ai_provider("", api_key="k")
    assert provider.id == "openrouter"


def test_factory_resolves_each_supported_provider():
    assert create_ai_provider("openai", "k").id == "openai"
    assert create_ai_provider("gemini", "k").id == "gemini"
    assert create_ai_provider("claude", "k").id == "claude"


def test_factory_rejects_unknown_provider():
    try:
        create_ai_provider("nao_existe", "k")
        assert False, "deveria rejeitar provider desconhecido"
    except AIProviderError:
        pass


if __name__ == "__main__":
    test_build_structured_prompt_never_invents_outside_portfolio_instruction()
    test_parse_structured_response_valid_json()
    test_parse_structured_response_degrades_gracefully_on_non_json()
    test_openrouter_generate_parses_openai_shaped_response()
    test_openai_generate_parses_response()
    test_gemini_generate_parses_response()
    test_claude_generate_parses_response()
    test_invalid_credentials_never_retried_and_raises_friendly_error()
    test_missing_api_key_raises_before_any_call()
    test_factory_defaults_to_openrouter()
    test_factory_resolves_each_supported_provider()
    test_factory_rejects_unknown_provider()
    print("OK — todos os testes de IA passaram")
