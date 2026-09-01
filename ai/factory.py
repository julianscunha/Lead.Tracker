"""
Resolve o provider de IA configurado.

`openrouter` é o padrão (dá acesso a vários modelos por uma única API/key).
`openai`, `gemini` e `claude` ficam disponíveis como alternativa direta,
sem custo de troca de arquitetura — é só mudar AI_PROVIDER no `.env`.
"""
from __future__ import annotations

from ai.base import AIProvider, AIProviderError
from ai.claude_provider import ClaudeProvider
from ai.gemini_provider import GeminiProvider
from ai.openai_provider import OpenAIProvider
from ai.openrouter import OpenRouterProvider

_PROVIDERS: dict[str, type[AIProvider]] = {
    "openrouter": OpenRouterProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "claude": ClaudeProvider,
}

DEFAULT_PROVIDER = "openrouter"


def create_ai_provider(provider_name: str, api_key: str) -> AIProvider:
    name = (provider_name or DEFAULT_PROVIDER).strip().lower()
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise AIProviderError(
            f"Provider de IA '{provider_name}' não suportado. Opções: {', '.join(_PROVIDERS)}."
        )
    return cls(api_key)
