"""OpenAIProvider — opção alternativa de IA."""
from __future__ import annotations

from ai.base import AIProvider, AIRequest, AIResponse, build_structured_prompt, parse_structured_response
from ai.http_base import HTTPChatProvider
from providers.base import ConnectionTestResult

_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(HTTPChatProvider, AIProvider):

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL, **kwargs) -> None:
        super().__init__(api_key, **kwargs)
        self._model = model

    @property
    def id(self) -> str:
        return "openai"

    async def test_connection(self) -> ConnectionTestResult:
        try:
            await self.generate(AIRequest(instruction="ping"))
            return ConnectionTestResult.ok("openai acessível")
        except Exception as exc:  # noqa: BLE001
            return ConnectionTestResult.fail(str(exc))

    async def generate(self, request: AIRequest) -> AIResponse:
        prompt = build_structured_prompt(request)
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        data = await self._post_json(_URL, headers, payload)
        raw_text = data["choices"][0]["message"]["content"]
        return parse_structured_response(raw_text)
