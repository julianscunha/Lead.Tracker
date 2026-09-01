"""
Rascunho de e-mail.

Fluxo: Oportunidade -> contexto -> portfólio -> evidências -> IA -> rascunho ->
revisão do usuário. Nunca envia — não existe função de envio
aqui, só geração de texto pra revisão humana.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai.base import AIProvider, AIProviderError, AIRequest

_INSTRUCTION = (
    "Gere um rascunho de e-mail comercial para a oportunidade descrita no contexto. "
    "Tom: empresarial, consultivo, contextual, nunca agressivo. Baseie-se somente nas "
    "evidências fornecidas — nunca invente fato, dado ou benefício não sustentado pelo "
    "contexto. Retorne o JSON pedido com 'structured' contendo exatamente as chaves "
    '"subject", "greeting", "body" e "cta" (call-to-action), todas string.'
)


@dataclass
class EmailDraft:
    subject: str
    greeting: str
    body: str
    cta: str


def build_email_request(
    company_name: str,
    opportunity_type: str,
    evidence: list[str],
    justification: str | None,
    portfolio: dict[str, Any],
) -> AIRequest:
    return AIRequest(
        instruction=_INSTRUCTION,
        company_context={"nome": company_name, "tipo_oportunidade": opportunity_type},
        portfolio=portfolio,
        provider_data={"evidencias": evidence, "justificativa": justification or ""},
    )


def parse_email_draft(structured: dict[str, Any]) -> EmailDraft:
    """Extrai o rascunho da resposta estruturada. Nunca preenche campo ausente
    com texto inventado — falha de forma amigável se a IA não devolveu o formato pedido."""
    missing = [k for k in ("subject", "greeting", "body", "cta") if not structured.get(k)]
    if missing:
        raise AIProviderError(
            f"O provider de IA não devolveu o rascunho no formato esperado (faltando: {', '.join(missing)}). Tente novamente."
        )
    return EmailDraft(
        subject=str(structured["subject"]),
        greeting=str(structured["greeting"]),
        body=str(structured["body"]),
        cta=str(structured["cta"]),
    )


async def generate_email_draft(
    provider: AIProvider,
    company_name: str,
    opportunity_type: str,
    evidence: list[str],
    justification: str | None,
    portfolio: dict[str, Any],
) -> EmailDraft:
    request = build_email_request(company_name, opportunity_type, evidence, justification, portfolio)
    response = await provider.generate(request)
    return parse_email_draft(response.structured)
