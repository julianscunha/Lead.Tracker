"""
Guard-rails determinísticos pra campos persuasivos opcionais do rascunho de
e-mail (`differentiator`/`ps`, Fase G módulo 2). Decisões em consulta ao
agente Sales Engineer (docs/specs/fase-g-outreach-assistido.md, módulo 2).

Nunca chama IA nem depende de heurística estatística/n-grama — só regex e
comparação de string, pra ser testável com `assert` simples, sem mock de
provider. Reprova → o CAMPO é descartado (nunca a geração inteira; ver
`ai/email_draft.py`), porque `differentiator`/`ps` são opcionais e o e-mail
já é funcional sem eles.
"""
from __future__ import annotations

import re
from typing import Any

_BLOCKED_PHRASES = (
    "líder de mercado", "comprovad", "garantid", "o melhor", "a melhor",
    "único", "única", "sempre", "nunca", "100%", "sem concorrente",
    "mais barato que todos", "insuperável", "imbatível",
)

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?%?")
_COMPARATIVE_RE = re.compile(r"\b(mais|menos|melhor|maior|menor)\b", re.IGNORECASE)
_UNCITED_SOURCE_RE = re.compile(r"\b(segundo|estudo|pesquisa mostra|dados indicam)\b|fonte\s*:", re.IGNORECASE)


def _normalize_number(raw: str) -> str:
    # Só normaliza separador decimal (vírgula -> ponto) — nunca mexe em "."
    # já presente, porque não dá pra distinguir de forma confiável separador
    # de milhar de separador decimal só olhando o número isolado.
    return raw.rstrip("%").replace(",", ".")


def _numbers_in(text: str) -> set[str]:
    return {_normalize_number(m) for m in _NUMBER_RE.findall(text)}


_MAX_FLATTEN_DEPTH = 20


def _flatten_strings(value: Any, _depth: int = 0) -> list[str]:
    if _depth > _MAX_FLATTEN_DEPTH:
        # Nunca deixa um portfolio/evidence anormalmente aninhado estourar
        # RecursionError — isso derrubaria a geração inteira do e-mail, não
        # só descartaria o campo persuasivo (achado da revisão de código).
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, bool):
        return []  # bool é subclasse de int -- nunca vira "True"/"False" no haystack
    if isinstance(value, (int, float)):
        return [str(value)]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _flatten_strings(v, _depth + 1)]
    if isinstance(value, (list, tuple)):
        return [s for item in value for s in _flatten_strings(item, _depth + 1)]
    return []


def validate_persuasive_field(text: str, evidence: list[str], portfolio: dict[str, Any]) -> str | None:
    """Devolve `None` se `text` passa em todos os guard-rails, ou uma razão
    curta (log/telemetria) se deve ser descartado. Nunca levanta exceção —
    quem chama decide o que fazer com a razão (`ai/email_draft.py` descarta
    o campo e segue com o resto do rascunho)."""
    if not text or not text.strip():
        return None

    # (?<!\d)/(?!\d) -- nunca conta o ponto decimal de um número ("4.5")
    # como fim de frase; achado durante a implementação (bug real, não só
    # teste): sem isso, qualquer differentiator/ps legítimo citando um
    # número com ponto decimal seria rejeitado como "mais de uma frase".
    sentences = [s for s in re.split(r"(?<!\d)[.!?]+(?!\d)", text) if s.strip()]
    if len(sentences) > 1:
        return "mais de uma frase"

    lowered = text.lower()
    for phrase in _BLOCKED_PHRASES:
        if phrase in lowered:
            return f"termo absoluto/superlativo proibido: '{phrase}'"

    haystack = " ".join(evidence + _flatten_strings(portfolio))
    allowed_numbers = _numbers_in(haystack)
    for number in _numbers_in(text):
        if number not in allowed_numbers:
            return f"número '{number}' não encontrado em evidence/portfolio"

    if _COMPARATIVE_RE.search(text) and not _numbers_in(text):
        return "comparativo sem número âncora"

    if _UNCITED_SOURCE_RE.search(lowered):
        return "menção a fonte externa não citada"

    return None
