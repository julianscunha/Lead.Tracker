"""ClaudeProvider (Anthropic) — opção alternativa de IA."""
from __future__ import annotations

from ai.base import AIProvider, AIRequest, AIResponse, build_structured_prompt, parse_structured_response
from ai.http_base import HTTPChatProvider
from providers.base import ConnectionTestResult

_URL = "https://api.anthropic.com/v1/messages"
_DEFAULT_MODEL = "claude-sonnet-5"
_ANTHROPIC_VERSION = "2023-06-01"


class ClaudeProvider(HTTPChatProvider, AIProvider):

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL, **kwargs) -> None:
        super().__init__(api_key, **kwargs)
        self._model = model

    @property
    def id(self) -> str:
        return "claude"

    async def test_connection(self) -> ConnectionTestResult:
        try:
            await self.generate(AIRequest(instruction="ping"))
            return ConnectionTestResult.ok("claude acessível")
        except Exception as exc:  # noqa: BLE001
            return ConnectionTestResult.fail(str(exc))

    async def generate(self, request: AIRequest) -> AIResponse:
        prompt = build_structured_prompt(request)
        payload = {
            "model": self._model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        }
        data = await self._post_json(_URL, headers, payload)
        raw_text = data["content"][0]["text"]
        return parse_structured_response(raw_text)
