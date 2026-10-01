"""
Guard-rails determinísticos das seções de IA do business case (T3a). Funções
puras: sem I/O, sem rede, sem relógio. Mesmo estilo de `ai/email_guardrails.py`.

`validate_section` devolve só um CÓDIGO curto de rejeição, nunca o texto
rejeitado (pode conter dado de CRM e não deve ir parar em log). Tamanho é
rejeição: nunca se trunca saída da IA.
"""
from __future__ import annotations

import re
import unicodedata

from ai.email_guardrails import _DATE_RE, _normalize_number

# Códigos que indicam possível injeção (T3b descarta todas as seções).
INJECTION_CODES = frozenset({"numero_fora_da_entrada", "moeda_ou_valor", "entidade_desconhecida"})

# Padrões já sem acento/minúsculos não são exigidos: são dobrados em `_fold`.
# Sem `\b` final nos radicais (garant, imediat...) de propósito.
TERMOS_PROIBIDOS: dict[str, tuple[str, ...]] = {
    "urgencia": (
        "últimas vagas", "últimas unidades", "por tempo limitado", r"janela (?:se )?fecha",
        r"prazo (?:se )?(?:encerra|esgota)", "aproveite", "não perca", r"garanta (?:já|agora)",
        "urgente", "urgência", "imediat", r"corra\b", r"enquanto (?:dá|há) tempo", "só até", "expira",
    ),
    "prova_social": (
        r"empresas (?:como|do (?:seu|mesmo))", "clientes como", "outros clientes",
        r"(?:nossos|muitos|diversos|várias) (?:clientes|empresas)", r"cases? de sucesso",
        "resultados comprovados", r"mercado já\b",
    ),
    "concorrente": (
        "concorrent", r"em relação (?:a|ao)\b", "melhor que", r"superior a\b", r"líder\b",
        r"vs\b", r"versus\b", "mais barato", r"diferente d[eo]s? outros",
    ),
    "garantia": ("garant", "comprovad", r"100%", "insuperável", "imbatível", "o melhor", "a melhor",
                 r"únic[oa]\b"),
    "adjetivo_vazio": ("inovador", "revolucionári", "de ponta", "robust", r"world.class", "incrível",
                       "excepcional", "transformador"),
    "fonte_externa": (r"segundo\b", "estudo", "pesquisa", r"relatório (?:de|da)\b", "dados do mercado",
                      "gartner", "forrester"),
}

_MARKDOWN = ("```", "<", "**", "[", "](")
# URL/domínio: compara o token inteiro (www.zeta.com != www.alfa.com.br da entrada).
_URL_RE = re.compile(r"[\w./:-]*(?:http|www\.|://|[a-z]\.(?:com|br|io|net|org|gov|edu)\b)[\w./:-]*")

_NUM_RE = re.compile(r"\d+(?:[.,]\d+)*%?")
_PLAIN_OR_MILHAR_RE = re.compile(r"^\d+$|^\d{1,3}(?:[.,]\d{3})+$")
_MESES = "janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro"
_DATA_EXTENSO_RE = re.compile(rf"\b\d{{1,2}} de (?:{_MESES})\b")
_MOEDA_RE = re.compile(r"\$|\breais\b|\bmil\b|\b(?:milh|bilh)(?:ao|oes)\b|\b(?:euros?|dolar(?:es)?|usd|eur|brl)\b|\bpor cento\b")
_EXTENSO = {"dois": "2", "duas": "2", "tres": "3", "quatro": "4", "cinco": "5", "seis": "6",
            "sete": "7", "oito": "8", "nove": "9", "dez": "10", "cem": "100"}
_UNID = {"um": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9}
_EXTENSO.update({"onze": "11", "doze": "12", "treze": "13", "catorze": "14", "quatorze": "14", "quinze": "15",
                 "dezesseis": "16", "dezessete": "17", "dezoito": "18", "dezenove": "19",
                 "duzentos": "200", "trezentos": "300", "quatrocentos": "400", "quinhentos": "500",
                 "seiscentos": "600", "setecentos": "700", "oitocentos": "800", "novecentos": "900"})
for _n, _d in {"vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60,
               "setenta": 70, "oitenta": 80, "noventa": 90}.items():
    _EXTENSO[_n] = str(_d)
    for _u, _v in _UNID.items():
        _EXTENSO[f"{_n} e {_u}"] = str(_d + _v)
_EXTENSO_RE = re.compile(r"\b(" + "|".join(sorted(_EXTENSO, key=len, reverse=True)) + r")\b")
_WORD_RE = re.compile(r"[^\W_]+")
_STOPWORDS = frozenset(
    "os as o a um uma há dado dados fato fatos evidência evidências solidez em de no na se sem com "
    "por para não sim este esta esse essa também ainda isso hoje".split()
)


def _fold(s: str) -> str:
    """casefold + sem acento (NFKD)."""
    d = unicodedata.normalize("NFKD", s)
    return "".join(c for c in d if not unicodedata.combining(c) and unicodedata.category(c) != "Cf").casefold()


def _stem(tok: str) -> str:
    """Singular simples: tira 'es'/'s' final, depois de dobrar acento/caixa."""
    t = _fold(tok)
    if t.endswith("es") and len(t) > 4:
        return t[:-2]
    if t.endswith("s") and len(t) > 3:
        return t[:-1]
    return t


_STOP_STEMS = frozenset(_stem(w) for w in _STOPWORDS)
_TERMOS_RE = re.compile(r"\b(?:" + "|".join(_fold(p) for g in TERMOS_PROIBIDOS.values() for p in g) + ")")


def _number_sets(text: str) -> tuple[set[str], set[str]]:
    """(números normalizados, formas só-dígitos de números simples/milhar)."""
    norms, digits = set(), set()
    for raw in _NUM_RE.findall(text):
        body = raw.rstrip("%")
        norms.add(_normalize_number(raw))
        if _PLAIN_OR_MILHAR_RE.match(body):
            digits.add(re.sub(r"\D", "", body))
    return norms, digits


def _number_ok(raw: str, norms: set[str], digits: set[str]) -> bool:
    body = raw.rstrip("%")
    if _normalize_number(raw) in norms:
        return True
    return bool(_PLAIN_OR_MILHAR_RE.match(body)) and re.sub(r"\D", "", body) in digits


def _entity_tokens(text: str, *, skip_sentence_start: bool) -> set[str]:
    """Tokens Capitalizados/ALLCAPS/com dígito (normalizados). Tokens só de
    dígitos ficam de fora (números têm checagem própria). Tokens com dígito
    (VDC365) são checados mesmo no início de frase."""
    out: set[str] = set()
    for m in _WORD_RE.finditer(text):
        tok = m.group(0)
        has_digit = any(c.isdigit() for c in tok)
        if tok.isdigit() or not (tok[0].isupper() or has_digit):
            continue
        if skip_sentence_start and not has_digit:
            prefix = text[: m.start()]
            stripped = prefix.rstrip()
            if not stripped or stripped[-1] in ".!?" or "\n" in prefix[len(stripped):]:
                continue
        st = _stem(tok)
        if st not in _STOP_STEMS:
            out.add(st)
    return out


def _words_stems(text: str) -> set[str]:
    return {_stem(m.group(0)) for m in _WORD_RE.finditer(text)}


def validate_section(text: str, allowed_text: str, *, min_ratio: float = 0.4, max_words: int, original: str) -> str | None:
    """`None` se `text` passa, ou um código curto de rejeição. Nunca devolve
    nem registra o texto rejeitado. Códigos: vazio, moeda_ou_valor,
    numero_fora_da_entrada, entidade_desconhecida, markdown_ou_url,
    termo_proibido, muito_longo, muito_curto."""
    if not text or not text.strip():
        return "vazio"
    text = "".join(c for c in text if unicodedata.category(c) != "Cf")  # zero-width etc.
    folded, allowed = _fold(text), _fold(allowed_text)

    # Moeda/valor: proibido sempre, mesmo que a entrada tenha.
    if _MOEDA_RE.search(folded):
        return "moeda_ou_valor"

    norms, digits = _number_sets(allowed_text)
    allowed_compact = allowed.replace(" ", "")
    for raw in _NUM_RE.findall(text):
        if not _number_ok(raw, norms, digits):
            return "numero_fora_da_entrada"
        if raw.endswith("%") and raw not in allowed_compact:
            return "numero_fora_da_entrada"
    for m in _EXTENSO_RE.finditer(folded):
        if _EXTENSO[m.group(1)] not in digits:
            return "numero_fora_da_entrada"
    for m in _DATE_RE.finditer(text):
        if m.group(0) not in allowed_text:
            return "numero_fora_da_entrada"
    for m in _DATA_EXTENSO_RE.finditer(folded):
        if m.group(0) not in allowed:
            return "numero_fora_da_entrada"

    known = _words_stems(allowed_text)
    if any(t not in known for t in _entity_tokens(text, skip_sentence_start=True)):
        return "entidade_desconhecida"

    # Homóglifos (cirílico minúsculo) ficam como risco residual: não tratados.
    achados = [s for s in _MARKDOWN if s in folded] + [m.group(0).rstrip(".") for m in _URL_RE.finditer(folded)]
    if any(a not in allowed for a in achados):
        return "markdown_ou_url"

    # Termo que já existe literalmente na entrada não conta (só o que a IA acrescentou).
    if any(m.group(0) not in allowed for m in _TERMOS_RE.finditer(folded)):
        return "termo_proibido"

    n = len(text.split())
    if n > max_words:
        return "muito_longo"
    if n < min_ratio * len(original.split()):
        return "muito_curto"
    return None


def has_injection_signal(codes: list[str]) -> bool:
    """True se algum código indica injeção (número/valor/entidade fora da entrada)."""
    return any(c in INJECTION_CODES for c in codes)


def missing_facts(text: str, evidences: list[str]) -> list[int]:
    """Índices das evidências cujos números ou tokens-entidade não aparecem
    em `text` (cobertura quase literal). Evidência sem número/entidade nunca falta."""
    norms, digits = _number_sets(text)
    stems = _words_stems(text)
    missing = []
    for i, ev in enumerate(evidences):
        nums_ok = all(_number_ok(r, norms, digits) for r in _NUM_RE.findall(ev))
        ents_ok = _entity_tokens(ev, skip_sentence_start=False) <= stems
        if not (nums_ok and ents_ok):
            missing.append(i)
    return missing


_MASK = "[removido]"
_MARKER_RE = re.compile(r"<</?F", re.IGNORECASE)
_MAX_SCRUB = 20_000
_LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9+/=]{32,}\b")


def _mask_token(m: re.Match) -> str:
    t = m.group(0)
    digs = sum(c.isdigit() for c in t)
    # Só mascara com letra E >30% de dígitos (preserva nomes de produto longos).
    return _MASK if 0 < digs < len(t) and digs / len(t) > 0.3 else t


_SECRET_RES = tuple(re.compile(p) for p in (
    r"\bsk-[A-Za-z0-9_-]{8,200}",
    r"\bBearer\s{1,8}\S{1,500}",
    r"\b[A-Fa-f0-9]{24,}\b",
    r"\b[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63})+",
    r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b",   # CNPJ
    r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b",           # CPF
    r"(?:\+\d{1,3}\s?)?\(\d{2}\)\s?\d{4,5}-?\d{4}",
    r"\+\d{1,3}\s?\d{2}\s?\d{4,5}[-\s]?\d{4}\b",
    r"\b(?:\d{2}\s?)?\d{4,5}-\d{4}\b",
))


def scrub_for_prompt(text: str) -> str:
    """Mascara e-mail/telefone/CPF/CNPJ/segredos e remove marcadores de
    delimitador (`<<F`, `<</F`) — repete até estabilizar, pois a remoção
    pode recompor um marcador (`<<<<FF`)."""
    text = text[:_MAX_SCRUB]  # limita o custo das regex (ReDoS)
    prev = None
    while prev != text:
        prev, text = text, _MARKER_RE.sub("", text)
    for rx in _SECRET_RES:
        text = rx.sub(_MASK, text)
    text = _LONG_TOKEN_RE.sub(_mask_token, text)
    return text
