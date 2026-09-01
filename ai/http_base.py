"""
Base HTTP para providers de IA reais (Fase 09).

Timeout explícito e retry só em erro transitório (5xx/timeout) — nunca em
credencial/requisição inválida (CLAUDE.md 'Error handling & resilience').
`client` é injetável para permitir teste com `httpx.MockTransport`, sem
chamada de rede real (CLAUDE.md 'Testing': providers de IA sempre mockados).
"""
from __future__ import annotations

import asyncio

import httpx

from ai.base import AIProviderError

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_TRANSIENT_STATUS = {429, 500, 502, 503, 504}


class HTTPChatProvider:

    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        if not api_key:
            raise AIProviderError(f"{self.__class__.__name__}: API key ausente — configure AI_API_KEY.")
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(timeout=_TIMEOUT)

    async def _post_json(self, url: str, headers: dict, payload: dict, max_retries: int = 1) -> dict:
        attempt = 0
        while True:
            try:
                response = await self._client.post(url, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                raise AIProviderError("Tempo esgotado ao contatar o provider de IA. Tente novamente.") from exc
            except httpx.RequestError as exc:
                raise AIProviderError("Falha de conexão com o provider de IA.") from exc

            if response.status_code == 200:
                return response.json()

            if response.status_code in _TRANSIENT_STATUS and attempt < max_retries:
                attempt += 1
                await asyncio.sleep(0.5 * attempt)
                continue

            if response.status_code in (401, 403):
                raise AIProviderError("Credencial de IA inválida ou sem permissão.")
            if response.status_code == 422 or response.status_code == 400:
                raise AIProviderError("Requisição inválida ao provider de IA.")
            raise AIProviderError(f"Provider de IA retornou erro ({response.status_code}).")
