"""
Contrato da camada de IA (Fase 09).

IA é complementar — nunca decide sozinha, nunca inventa produto/serviço fora
do portfólio, nunca edita dado de origem, nunca envia e-mail automaticamente
(docs/fases/09-CAMADA-IA.md 'A IA não pode'; CLAUDE.md 'AI is complementary').
Toda resposta é estruturada, com evidência e confiança — nunca texto livre
sem rastreabilidade.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from providers.base import ConnectionTestResult


class AIProviderError(Exception):
    """Erro amigável de IA — falha de provider de IA nunca derruba o motor determinístico."""


@dataclass
class AIRequest:
    """
    Contexto enviado à IA (docs/fases/09 'Contexto enviado à IA'):
    empresa + portfólio + produtos + serviços + regras de correlação + dados dos providers.
    """
    instruction: str
    company_context: dict[str, Any] = field(default_factory=dict)
    portfolio: dict[str, Any] = field(default_factory=dict)
    correlation_rules: list[dict[str, Any]] = field(default_factory=list)
    provider_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class AIResponse:
    """Saída estruturada e obrigatória (docs/fases/09 'Saída estruturada')."""
    content: str
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    structured: dict[str, Any] = field(default_factory=dict)


class AIProvider(ABC):
    """Contrato mínimo que todo provider de IA deve implementar."""

    @property
    @abstractmethod
    def id(self) -> str:
        """Identificador estável do provider (ex.: 'openrouter', 'openai', 'gemini', 'claude')."""

    @abstractmethod
    async def test_connection(self) -> ConnectionTestResult:
        """Verifica se a API key/endpoint está acessível e configurado corretamente."""

    @abstractmethod
    async def generate(self, request: AIRequest) -> AIResponse:
        """Executa a requisição contra o provider e retorna uma resposta estruturada."""


_JSON_INSTRUCTION = (
    "Responda SOMENTE com um JSON válido no formato "
    '{"content": string, "evidence": [string], "confidence": number entre 0 e 1}. '
    "Nunca invente produto, serviço ou fabricante fora do portfólio fornecido. "
    "Baseie 'evidence' apenas nos dados do contexto abaixo."
)


def build_structured_prompt(request: AIRequest) -> str:
    """Monta o prompt textual a partir do AIRequest, exigindo saída JSON estruturada
    (docs/fases/09 'Saída estruturada')."""
    context = {
        "empresa": request.company_context,
        "portfolio": request.portfolio,
        "regras_de_correlacao": request.correlation_rules,
        "dados_providers": request.provider_data,
    }
    return (
        f"{_JSON_INSTRUCTION}\n\n"
        f"Instrução: {request.instruction}\n\n"
        f"Contexto: {json.dumps(context, ensure_ascii=False)}"
    )


def parse_structured_response(raw_text: str) -> AIResponse:
    """Converte a saída bruta do modelo em AIResponse. Degrada com segurança se o
    modelo não devolver JSON válido — nunca propaga erro de parsing pro chamador."""
    try:
        data = json.loads(raw_text)
        return AIResponse(
            content=str(data.get("content", raw_text)),
            evidence=list(data.get("evidence", [])),
            confidence=float(data.get("confidence", 0.0)),
            structured=data,
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        return AIResponse(content=raw_text, evidence=[], confidence=0.0)
