"""Fase P — guardrail DETERMINÍSTICO sobre a sugestão de portfólio da IA. Função pura, sem I/O.

O texto do site é dado NÃO confiável (pode conter instruções para a IA). Por isso a saída da IA
nunca é aceita pelo que diz: um item só passa se for comprovável NO TEXTO COLETADO:
  1. a `pagina` citada é uma das páginas realmente coletadas;
  2. a `evidencia` é trecho literal do texto dessa página (mínimo 10 caracteres, máximo 300);
  3. o `nome` aparece literalmente (sem caixa/acento, com fronteira de palavra) DENTRO da evidência;
  4. o `fabricante`, quando vem, também aparece literalmente (fronteira de palavra) nessa página;
  5. o `tipo` é fabricante/produto/servico, e o nome não tem markup, URL nem caractere de controle.
Qualquer outro campo, URL, comando ou ação vinda da IA é ignorado. O que é descartado é só contado."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

MAX_SUGGESTIONS = 50
MAX_NAME = 100
MIN_EVIDENCE = 10
MAX_EVIDENCE = 300
_KINDS = {"fabricante": "vendor", "produto": "product", "servico": "service", "serviço": "service"}
_NAME_FORBIDDEN = re.compile(r"[<>]|://|[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class Suggestion:
    kind: str  # vendor | product | service
    name: str
    vendor_name: str | None
    evidence: str
    page_url: str


def _norm(text: str) -> str:
    """casefold, sem acento e com espaços colapsados — só para comparar texto."""
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(c for c in folded if not unicodedata.combining(c) and unicodedata.category(c) != "Cf")
    return " ".join(folded.casefold().split())


def has_forbidden_chars(name: str) -> bool:
    """Markup, URL, controle e caracteres invisíveis/bidi (Cf, que permitem spoofing de exibição)."""
    return bool(_NAME_FORBIDDEN.search(name)) or any(unicodedata.category(c) == "Cf" for c in name)


def _contains_word(text: str, term: str) -> bool:
    """`term` aparece em `text` com fronteira de palavra (ambos já normalizados): "go" não casa em "google"."""
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None


def _clean_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    name = " ".join(value.split())
    if not 2 <= len(name) <= MAX_NAME or has_forbidden_chars(name):
        return None
    return name


def validate_suggestions(raw_items: Any, pages: list[tuple[str, str]]) -> tuple[list[Suggestion], int]:
    """(sugestões válidas, quantas foram descartadas). `pages` = [(url, texto)] exatamente como foi
    enviado à IA (já higienizado), para a comparação ser sobre o mesmo texto."""
    if not isinstance(raw_items, list):
        return [], 0
    texts = {url: _norm(text) for url, text in pages}
    accepted: list[Suggestion] = []
    seen: set[tuple[str, str]] = set()
    discarded = 0
    for raw in raw_items:
        suggestion = _validate_one(raw, texts)
        if suggestion is None:
            discarded += 1
            continue
        key = (suggestion.kind, _norm(suggestion.name))
        if key in seen:
            continue  # duplicata exata não conta como descarte relevante
        if len(accepted) >= MAX_SUGGESTIONS:
            discarded += 1
            continue
        seen.add(key)
        accepted.append(suggestion)
    return accepted, discarded


def _validate_one(raw: Any, texts: dict[str, str]) -> Suggestion | None:
    if not isinstance(raw, dict):
        return None
    kind = _KINDS.get(_norm(raw.get("tipo", "")) if isinstance(raw.get("tipo"), str) else "")
    page_url = raw.get("pagina")
    name = _clean_name(raw.get("nome"))
    evidence = raw.get("evidencia")
    if kind is None or name is None or not isinstance(page_url, str) or page_url not in texts:
        return None
    if not isinstance(evidence, str):
        return None
    evidence = " ".join(evidence.split())[:MAX_EVIDENCE]
    page_text = texts[page_url]
    evidence_norm = _norm(evidence)
    # A evidência tem de ser trecho REAL da página E mostrar o item: sem isso a IA poderia citar uma frase
    # qualquer ("Fale conosco") para um nome solto em outro lugar da página.
    if len(evidence) < MIN_EVIDENCE or evidence_norm not in page_text or not _contains_word(evidence_norm, _norm(name)):
        return None
    vendor_name = None
    if raw.get("fabricante") not in (None, ""):
        vendor_name = _clean_name(raw.get("fabricante"))
        if vendor_name is None or not _contains_word(page_text, _norm(vendor_name)):
            return None
    if kind == "vendor":
        vendor_name = None
    elif kind == "product" and vendor_name is None:
        kind = "service"  # produto exige fabricante: sem fabricante citado vira serviço (o operador pode trocar)
    return Suggestion(kind=kind, name=name, vendor_name=vendor_name, evidence=evidence, page_url=page_url)
