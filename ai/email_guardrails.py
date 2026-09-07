"""
Guard-rails determinísticos do rascunho de e-mail (Fase G). Nunca chama IA
nem depende de heurística estatística/n-grama — só regex e comparação de
string, pra ser testável com `assert` simples, sem mock de provider.

- `validate_persuasive_field` (módulo 2, Sales Engineer consultado): campos
  OPCIONAIS `differentiator`/`ps`. Reprova → o CAMPO é descartado, nunca a
  geração inteira — são opcionais, o e-mail já é funcional sem eles.
- `validate_email_body` (módulo 4, Sales Coach consultado): campos
  OBRIGATÓRIOS subject/greeting/body/cta. Reprova → `ai/email_draft.py`
  levanta `AIProviderError` (mesmo padrão já usado pra campo obrigatório
  ausente) — não dá pra "descartar" um subject/body, só pedir nova geração.
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


# ── Módulo 4 (`prompt-prohibition-guards`) — Sales Coach consultado ─────────
# Nunca bloqueia a palavra isolada ("prazo", "cliente") — só a combinação
# gatilho + ausência do dado real que a legitimaria. Escopo consciente
# (Sales Coach: "manter o mesmo nível" de regex/string, sem NLP/paráfrase):
# "caso concreto" é aproximado por presença de número real em evidence/
# portfolio (mesma infra de `_numbers_in` já usada acima) — detecção de nome
# de empresa citado ficaria de fora, exigiria NLP pra não ter falso positivo.
_URGENCY_TRIGGERS = (
    "expira em breve", "expira brevemente", "por tempo limitado",
    "últimas vagas", "últimas unidades", "últimas chances",
    "aproveite antes que acabe", "aproveite antes que termine", "aproveite antes que encerre",
    "só até", "não perca essa chance", "não perca essa oportunidade",
    "urgente", "urgência", "hoje é o último dia", "garanta já", "garanta agora",
    "agende hoje mesmo", "agende agora mesmo", "enquanto dá tempo", "enquanto há tempo",
    "de última hora", "não fique de fora", "não deixe pra depois",
)

_GENERALIZATION_TRIGGERS = (
    "clientes como você", "clientes como a sua empresa", "clientes como vocês",
    "empresas do seu porte", "empresas do seu segmento", "empresas do seu setor",
    "nossos clientes satisfeitos", "nossos clientes relatam", "nossos clientes dizem",
    "outras empresas já perceberam", "outras empresas já conquistaram", "outras empresas já alcançaram",
    "muitos clientes nos contam", "muitos parceiros nos contam", "diversos clientes",
    "várias empresas como a sua", "é isso que nossos clientes buscam", "resultados comprovados",
    "cases de sucesso",
)

_DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b")


def _has_real_temporal_data(evidence: list[str], portfolio: dict[str, Any]) -> bool:
    """Existe uma data de verdade (não um prazo inventado) em evidence/
    portfolio — único jeito de legitimar uma menção a prazo/urgência."""
    haystack = " ".join(evidence + _flatten_strings(portfolio))
    return bool(_DATE_RE.search(haystack))


def _has_concrete_reference(evidence: list[str], portfolio: dict[str, Any]) -> bool:
    """Existe um número real (proxy de caso concreto/resultado mensurável)
    em evidence/portfolio — único jeito de legitimar uma generalização tipo
    "clientes como você". Não detecta nome de empresa citado (exigiria NLP,
    fora do escopo desta fatia — decisão consciente, Sales Coach consultado).

    Achado da revisão de código: uma data (ex. "15/03/2026") também "parece"
    número pra `_numbers_in` — sem remover a data antes, qualquer evidência
    com data de renovação (comum) legitimaria generalização vazia sem
    nenhum resultado real associado. Remove trechos de data antes de contar."""
    haystack = _DATE_RE.sub(" ", " ".join(evidence + _flatten_strings(portfolio)))
    return bool(_numbers_in(haystack))


def validate_email_body(text: str, evidence: list[str], portfolio: dict[str, Any]) -> str | None:
    """Devolve `None` se `text` (subject+greeting+body+cta concatenados)
    passa nos dois guard-rails do módulo 4, ou uma razão curta se deve ser
    rejeitado. Nunca levanta exceção — quem chama decide (`ai/email_draft.py`
    trata reprovação como campo obrigatório ausente, pede pra tentar de novo)."""
    if not text or not text.strip():
        return None

    lowered = text.lower()

    for trigger in _URGENCY_TRIGGERS:
        if trigger in lowered and not _has_real_temporal_data(evidence, portfolio):
            return f"urgência/prazo sem dado temporal real: '{trigger}'"

    for trigger in _GENERALIZATION_TRIGGERS:
        if trigger in lowered and not _has_concrete_reference(evidence, portfolio):
            return f"generalização sem caso concreto: '{trigger}'"

    return None
