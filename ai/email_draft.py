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
    "contexto. O campo 'motivo_principal' do contexto é o motivo determinístico já decidido "
    "pelo motor de regras — reforce esse MESMO motivo em subject/body/cta (nunca troque, "
    "nunca invente um motivo diferente ou adicional). Retorne o JSON pedido com 'structured' "
    'contendo exatamente as chaves "subject", "greeting", "body" e "cta" (call-to-action), '
    "todas string."
)


@dataclass
class EmailDraft:
    subject: str
    greeting: str
    body: str
    cta: str
    # Fase G, módulo 1 (`primary-reason-field`) — eco do motivo determinístico
    # de ENTRADA (justification/regra já decidida pelo motor), nunca extraído
    # da resposta da IA: a IA só é instruída a reforçá-lo em subject/body/cta,
    # nunca a decidir ou reescrever qual é o motivo principal (mesma blindagem
    # que `_build_opportunity` já tem contra a IA inventar `justification`,
    # CLAUDE.md "Deterministic rules come before AI").
    primary_reason: str | None = None


def build_email_request(
    company_name: str,
    opportunity_type: str,
    evidence: list[str],
    justification: str | None,
    portfolio: dict[str, Any],
    primary_reason: str | None = None,
) -> AIRequest:
    reason = primary_reason or justification or ""
    return AIRequest(
        instruction=_INSTRUCTION,
        company_context={"nome": company_name, "tipo_oportunidade": opportunity_type},
        portfolio=portfolio,
        provider_data={"evidencias": evidence, "justificativa": justification or "", "motivo_principal": reason},
    )


def parse_email_draft(structured: dict[str, Any], primary_reason: str | None = None) -> EmailDraft:
    """Extrai o rascunho da resposta estruturada. Nunca preenche campo ausente
    com texto inventado — falha de forma amigável se a IA não devolveu o formato pedido.
    `primary_reason` nunca vem de `structured` (resposta da IA) — é sempre o valor de
    ENTRADA já decidido pelo motor de regras, só repassado adiante."""
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
        primary_reason=primary_reason,
    )


async def generate_email_draft(
    provider: AIProvider,
    company_name: str,
    opportunity_type: str,
    evidence: list[str],
    justification: str | None,
    portfolio: dict[str, Any],
    primary_reason: str | None = None,
) -> EmailDraft:
    reason = primary_reason or justification
    request = build_email_request(company_name, opportunity_type, evidence, justification, portfolio, primary_reason=reason)
    response = await provider.generate(request)
    return parse_email_draft(response.structured, primary_reason=reason)
