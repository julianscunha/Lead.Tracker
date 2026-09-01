"""GeminiProvider — opção alternativa de IA."""
from __future__ import annotations

from ai.base import AIProvider, AIRequest, AIResponse, build_structured_prompt, parse_structured_response
from ai.http_base import HTTPChatProvider
from providers.base import ConnectionTestResult

_DEFAULT_MODEL = "gemini-1.5-flash"


class GeminiProvider(HTTPChatProvider, AIProvider):

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL, **kwargs) -> None:
        super().__init__(api_key, **kwargs)
        self._model = model

    @property
    def id(self) -> str:
        return "gemini"

    async def test_connection(self) -> ConnectionTestResult:
        try:
            await self.generate(AIRequest(instruction="ping"))
            return ConnectionTestResult.ok("gemini acessível")
        except Exception as exc:  # noqa: BLE001
            return ConnectionTestResult.fail(str(exc))

    async def generate(self, request: AIRequest) -> AIResponse:
        prompt = build_structured_prompt(request)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent?key={self._api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        data = await self._post_json(url, headers={}, payload=payload)
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        return parse_structured_response(raw_text)
