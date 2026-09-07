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
from ai.email_guardrails import validate_email_body, validate_persuasive_field

_BASE_INSTRUCTION = (
    "Gere um rascunho de e-mail comercial para a oportunidade descrita no contexto. "
    "Tom: empresarial, consultivo, contextual, nunca agressivo. Baseie-se somente nas "
    "evidências fornecidas — nunca invente fato, dado ou benefício não sustentado pelo "
    "contexto. O campo 'motivo_principal' do contexto é o motivo determinístico já decidido "
    "pelo motor de regras — reforce esse MESMO motivo em subject/body/cta (nunca troque, "
    "nunca invente um motivo diferente ou adicional). Retorne o JSON pedido com 'structured' "
    'contendo as chaves "subject", "greeting", "body" e "cta" (call-to-action), todas string, '
    'e opcionalmente "differentiator" (uma frase só, releitura persuasiva de um fato JÁ presente '
    "em evidências/portfólio — nunca número, produto ou alegação que não esteja lá) e \"ps\" "
    "(um P.S. opcional reforçando o ponto mais forte já citado no corpo, mesma regra: nunca fato novo). "
    "Proibições explícitas (subject/greeting/body/cta): nunca mencione prazo, urgência ou escassez "
    "artificial ('por tempo limitado', 'últimas vagas', 'aproveite antes que acabe' e afins) a menos "
    "que exista uma data real nas evidências — se não houver data real, não mencione prazo nenhum. "
    "Nunca generalize com 'clientes como você'/'empresas do seu porte'/'nossos clientes satisfeitos' "
    "sem um caso concreto (nome, número, resultado real) nas evidências — sem caso concreto, "
    "omita a generalização em vez de inventar uma."
)

# Fase G, módulo 3 (`tone-by-customer-status`) — Outbound Strategist
# consultado (docs/specs/fase-g-outreach-assistido.md, módulo 3). Duas
# variações fixas de tom, nunca uma terceira genérica: a linha entre
# "cliente" e "prospecção fria" é binária (Company.is_customer já existe),
# sem meio-termo especulativo.
_TONE_INSTRUCTION_CUSTOMER = (
    "Este destinatário já é cliente ativo e usa o produto/serviço já configurado no portfólio "
    "fornecido. Abra o e-mail citando esse uso já existente como ponto de partida natural da "
    'conversa (ex.: "vocês já usam [produto] há [tempo/contexto]") — nunca como elogio genérico, '
    "sempre ancorado num fato concreto do portfólio. Nunca mencione produto/serviço que o cliente "
    "NÃO usa na abertura — isso só pode entrar no CTA. O CTA deve ser de continuidade ou expansão "
    "de baixo atrito (evoluir o uso atual, revisar configuração, antecipar renovação, avaliar módulo "
    "complementar ao que já existe) — nunca oferta de produto novo desconectado do que ele já usa. "
    "Tom de parceiro que acompanha a conta, nunca de vendedor prospectando quem já é cliente."
)

_TONE_INSTRUCTION_PROSPECT = (
    "Este destinatário não é cliente. Abra o e-mail pelo achado externo (motivo principal) "
    "apresentado como observação factual e específica, nunca como vigilância — proibido usar "
    '"percebemos que..." ou qualquer variação que descreva o ato de observar; descreva o fato '
    "direto. O CTA deve ser exploratório e de baixíssimo compromisso: uma conversa curta (10–15 "
    "min) pra entender se o achado é relevante — proibido pedir reunião de demonstração, orçamento "
    "ou apresentação da empresa; formule como pergunta aberta de baixo risco. Tom de quem oferece "
    "troca de informação, nunca de quem tem pressa de fechar."
)


def _build_instruction(is_customer: bool) -> str:
    tone = _TONE_INSTRUCTION_CUSTOMER if is_customer else _TONE_INSTRUCTION_PROSPECT
    return f"{_BASE_INSTRUCTION}\n\n{tone}"


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
    # Fase G, módulo 2 (`differentiator-and-ps-fields`) — opcionais; passam
    # por `validate_persuasive_field` (guard-rail determinístico, Sales
    # Engineer consultado) antes de chegar aqui. Campo que reprova é
    # descartado (fica `None`), nunca derruba o resto do rascunho.
    differentiator: str | None = None
    ps: str | None = None


def build_email_request(
    company_name: str,
    opportunity_type: str,
    evidence: list[str],
    justification: str | None,
    portfolio: dict[str, Any],
    primary_reason: str | None = None,
    is_customer: bool = False,
) -> AIRequest:
    reason = primary_reason or justification or ""
    return AIRequest(
        instruction=_build_instruction(is_customer),
        company_context={"nome": company_name, "tipo_oportunidade": opportunity_type, "is_customer": is_customer},
        portfolio=portfolio,
        provider_data={"evidencias": evidence, "justificativa": justification or "", "motivo_principal": reason},
    )


def parse_email_draft(
    structured: dict[str, Any],
    primary_reason: str | None = None,
    evidence: list[str] | None = None,
    portfolio: dict[str, Any] | None = None,
) -> EmailDraft:
    """Extrai o rascunho da resposta estruturada. Nunca preenche campo ausente
    com texto inventado — falha de forma amigável se a IA não devolveu o formato pedido.
    `primary_reason` nunca vem de `structured` (resposta da IA) — é sempre o valor de
    ENTRADA já decidido pelo motor de regras, só repassado adiante.

    `differentiator`/`ps` passam por `validate_persuasive_field` — campo que reprova o
    guard-rail determinístico é descartado (fica `None`), nunca derruba o resto do
    rascunho (Sales Engineer consultado: são opcionais, o e-mail já é funcional sem eles).

    subject/greeting/body/cta (obrigatórios) passam por `validate_email_body` (módulo 4,
    Sales Coach consultado) — reprova aqui vira `AIProviderError` (mesmo tratamento de campo
    obrigatório ausente), porque não dá pra "descartar" um corpo de e-mail obrigatório."""
    missing = [k for k in ("subject", "greeting", "body", "cta") if not structured.get(k)]
    if missing:
        raise AIProviderError(
            f"O provider de IA não devolveu o rascunho no formato esperado (faltando: {', '.join(missing)}). Tente novamente."
        )

    evidence = evidence or []
    portfolio = portfolio or {}

    # "\n" (não " ") entre os campos — achado da revisão de código: um
    # gatilho proibido nunca contém quebra de linha, então juntar com espaço
    # deixaria uma frase se "formar" na fronteira entre dois campos (ex.:
    # subject terminando em "por tempo" + body começando com "limitado")
    # mesmo sem aparecer de fato em nenhum campo isolado.
    full_body_text = "\n".join(str(structured[k]) for k in ("subject", "greeting", "body", "cta"))
    body_violation = validate_email_body(full_body_text, evidence, portfolio)
    if body_violation is not None:
        raise AIProviderError(
            "O rascunho gerado usou linguagem de pressão de vendas não sustentada pelos dados "
            f"({body_violation}). Tente novamente."
        )

    def _validated(key: str) -> str | None:
        value = structured.get(key)
        if not value:
            return None
        text = str(value)
        try:
            passed = validate_persuasive_field(text, evidence, portfolio) is None
        except Exception:  # noqa: BLE001 — achado da revisão de código: qualquer
            # falha no guard-rail (ex.: RecursionError num portfolio anormalmente
            # aninhado) descarta só este campo opcional, nunca derruba o resto
            # do rascunho (subject/body/cta/primary_reason já validados acima).
            return None
        return text if passed else None

    return EmailDraft(
        subject=str(structured["subject"]),
        greeting=str(structured["greeting"]),
        body=str(structured["body"]),
        cta=str(structured["cta"]),
        primary_reason=primary_reason,
        differentiator=_validated("differentiator"),
        ps=_validated("ps"),
    )


async def generate_email_draft(
    provider: AIProvider,
    company_name: str,
    opportunity_type: str,
    evidence: list[str],
    justification: str | None,
    portfolio: dict[str, Any],
    primary_reason: str | None = None,
    is_customer: bool = False,
) -> EmailDraft:
    reason = primary_reason or justification
    request = build_email_request(
        company_name, opportunity_type, evidence, justification, portfolio,
        primary_reason=reason, is_customer=is_customer,
    )
    response = await provider.generate(request)
    return parse_email_draft(response.structured, primary_reason=reason, evidence=evidence, portfolio=portfolio)
