"""
Coleta e normalização.

Recebe Company vindas de providers (modelo comum) e as consolida em
uma única empresa por domínio/nome — nunca duplica por ter aparecido em fontes
diferentes.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from core.models import Address, Company, SourceRef

# Sufixos jurídicos comuns no cadastro de empresa que não mudam a identidade
# real ("Acme Ltda" e "Acme S.A." são a mesma empresa) — só usados aqui pra
# não gerar Company duplicada quando a fonte não tem website (fallback de
# nome do dedup_key). Checados em ordem: mais específico primeiro.
_LEGAL_SUFFIXES = ("eireli", "ltda", "epp", "mei", "me", "sa")


def normalize_name(name: str) -> str:
    """Chave de comparação de nome — não é o nome exibido, só usado para
    casar registros. Dobra acento (NFKD), pontuação e sufixo jurídico comum
    (Ltda/LTDA./S.A./ME/EPP/EIRELI) pra que a mesma empresa real não vire
    duas Company diferentes só por variação de cadastro entre fontes."""
    folded = unicodedata.normalize("NFKD", name.strip().lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    folded = re.sub(r"[^\w\s]", "", folded)
    collapsed = re.sub(r"\s+", " ", folded).strip()
    for suffix in _LEGAL_SUFFIXES:
        if collapsed.endswith(" " + suffix):
            collapsed = collapsed[: -(len(suffix) + 1)].strip()
            break
    return collapsed


def normalize_domain(website: str | None) -> str | None:
    """Extrai o domínio nu de uma URL (sem protocolo, www ou path) para comparação."""
    if not website:
        return None
    candidate = website.strip().lower()
    if not re.match(r"^[a-z]+://", candidate):
        candidate = f"//{candidate}"
    host = urlparse(candidate).netloc or urlparse(candidate).path
    host = host.split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host or None


# Domínios que aparecem como "site" no Maps/CRM mas pertencem a uma plataforma,
# não à empresa: duas empresas diferentes colidiriam na chave de dedup. O link
# continua válido para exibição; só não serve de chave.
GENERIC_DOMAINS = {
    "facebook.com", "instagram.com", "wa.me", "linktr.ee", "sites.google.com",
    "linkedin.com", "twitter.com", "x.com", "youtube.com", "tiktok.com", "wixsite.com",
}

_MAX_WEBSITE_LEN = 2048


def normalize_website(raw: str | None) -> str | None:
    """URL segura para guardar/exibir, ou `None`. O dado vem de fonte externa
    (Maps, CRM com texto livre) e nunca é buscado por nós — só guardado e
    mostrado como link. Aceita só http/https com host contendo ponto e sem
    `user:pass@`; sem esquema ("www.x.com") prefixa https://. Esquemas opacos
    (`javascript:`, `data:`, `mailto:`) não têm `//`, por isso o teste é
    por `:` seguido de não-dígito (preserva `host.com:8080`). Qualquer
    rejeição devolve `None`, nunca erro: o campo é opcional."""
    if not raw:
        return None
    candidate = raw.strip()
    if not candidate or len(candidate) > _MAX_WEBSITE_LEN or any(c.isspace() or not c.isprintable() for c in candidate):
        return None
    if "://" not in candidate:
        if re.match(r"^[a-z][a-z0-9+.-]*:(?!\d)", candidate, re.I):
            return None
        candidate = f"https://{candidate}"
    try:
        parsed = urlparse(candidate)
        host = parsed.hostname
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or "@" in parsed.netloc or not host or "." not in host:
        return None
    return parsed._replace(netloc=parsed.netloc.lower()).geturl()


def dedup_key(company: Company) -> str:
    """Chave de deduplicação: domínio quando disponível, senão nome normalizado.
    Pública — backend/sync.py usa pra reconciliar empresa vinda de uma fonte
    contra empresa já persistida de outra fonte, sem duplicar. Domínio de
    plataforma (`GENERIC_DOMAINS`) não conta como domínio da empresa."""
    domain = normalize_domain(company.website)
    if domain and not any(domain == d or domain.endswith(f".{d}") for d in GENERIC_DOMAINS):
        return f"domain:{domain}"
    return f"name:{normalize_name(company.name)}"


def _merge_sources(existing: list[SourceRef], incoming: list[SourceRef]) -> list[SourceRef]:
    by_type: dict[str, SourceRef] = {s.type: s for s in existing}
    for src in incoming:
        current = by_type.get(src.type)
        if current is None or src.confidence > current.confidence:
            by_type[src.type] = src
    return list(by_type.values())


def merge_pair(base: Company, other: Company) -> Company:
    """Mescla `other` em `base`, preservando o `id`/identidade de `base` —
    usado quando `base` já está persistido (backend/sync.py) e não pode
    trocar de id sem quebrar Contact/Opportunity que o referenciam."""
    return base.model_copy(update={
        "legal_name": base.legal_name or other.legal_name,
        "website": base.website or other.website,
        "is_customer": base.is_customer or other.is_customer,
        "customer_status": base.customer_status or other.customer_status,
        "sources": _merge_sources(base.sources, other.sources),
        # last_activity_at é um sinal de recência (Fase C, Fatia 4a) — ao
        # contrário dos campos acima, precisa refletir o fetch mais recente,
        # nunca congelar no primeiro sync (senão o sinal de "momentum" nunca
        # se move).
        "last_activity_at": other.last_activity_at or base.last_activity_at,
        # Fase A — atributos de perfil (Salesforce Architect consultado):
        # ao contrário de last_activity_at (sinal de momentum, sempre pega
        # o mais recente), estes não mudam com frequência — primeiro valor
        # não-nulo vence, mesmo padrão de legal_name/website.
        "industry": base.industry or other.industry,
        # achado da revisão de código: `or` é errado pra numérico — 0 é
        # falsy em Python, então annual_revenue=0.0 (empresa pré-receita)
        # ou employee_count=0 em base seria sobrescrito por other mesmo
        # sendo um valor real e intencional, não "ausência de dado".
        "annual_revenue": base.annual_revenue if base.annual_revenue is not None else other.annual_revenue,
        "employee_count": base.employee_count if base.employee_count is not None else other.employee_count,
        "address": base.address or other.address,
        # Fase F, módulo 4 — mesmo tratamento de annual_revenue/employee_count
        # (numérico, "or" trataria 0.0 real como ausência). fetch_companies()
        # nunca popula este campo (só o split de mapeamento, módulo 4, escreve
        # nele depois do merge) — sem isso, resincronizar zeraria o valor já
        # promovido de um campo mapeado a cada rodada.
        "deal_size_hint": base.deal_size_hint if base.deal_size_hint is not None else other.deal_size_hint,
    })


def merge_companies(companies: list[Company]) -> list[Company]:
    """
    Consolida uma lista de Company (potencialmente vindas de providers
    diferentes) em uma empresa única por domínio/nome. Preserva proveniência
    (sources) de todas as origens mescladas.
    """
    merged: dict[str, Company] = {}
    for company in companies:
        key = dedup_key(company)
        if key in merged:
            merged[key] = merge_pair(merged[key], company)
        else:
            merged[key] = company
    return list(merged.values())


# ── Fase N — reconciliação com a empresa já gravada ──────────────────────────
# `merge_pair` continua como está (também é usado DENTRO da mesma fonte, onde abriria
# falsos conflitos). `reconcile` é chamada só onde já existe empresa persistida.

RECONCILED_FIELDS = (
    "legal_name", "website", "industry", "address", "annual_revenue", "employee_count", "customer_status",
)
LEGACY_SOURCE = "legacy"
# Perfil que o CSV traz (R11). Não entram no sync/Maps: só a importação passa estes campos.
CSV_PROFILE_FIELDS = ("segment", "region", "rep_id")


@dataclass(frozen=True)
class FieldChange:
    field: str
    old: Any
    new: Any


@dataclass(frozen=True)
class ConflictProposal:
    field: str
    current_value: Any
    current_source: str
    incoming_value: Any
    incoming_source: str


@dataclass(frozen=True)
class ReconcileResult:
    company: Company
    changes: list[FieldChange]
    conflicts: list[ConflictProposal]


def _fold(text: str) -> str:
    """Caixa, acento, pontuação e espaços — sem remover sufixo jurídico (diferente de `normalize_name`)."""
    folded = unicodedata.normalize("NFKD", text.strip().lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", folded)).strip()


def comparable(field: str, value: Any) -> str | None:
    """Forma comparável do valor (ignora formatação); `None` = ausência (nunca discorda)."""
    if value is None:
        return None
    if isinstance(value, dict):
        value = Address(**value)
    if isinstance(value, Address):
        parts = [_fold(p) for p in (value.city, value.state, value.postal_code, value.country) if p]
        return "|".join(parts) or None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return str(float(value))  # 0 é valor real
    text = str(value)
    if field == "website":
        return normalize_domain(text) or None
    if field == "rep_id":
        return text.strip().casefold() or None  # identificador: "rep-1" e "rep1" são pessoas diferentes
    return _fold(text) or None


def effective_field_source(company: Company, field: str) -> str:
    recorded = company.field_sources.get(field)
    if recorded:
        return recorded
    return company.sources[0].type if len(company.sources) == 1 else LEGACY_SOURCE


_ADDRESS_SLOTS = ("city", "state", "postal_code", "country")


def _address_slots(value) -> dict[str, str]:
    address = Address(**value) if isinstance(value, dict) else value
    return {s: _fold(getattr(address, s) or "") for s in _ADDRESS_SLOTS if getattr(address, s)}


def _address_differs(current, incoming) -> bool:
    """Endereço diverge só se um MESMO campo (cidade/UF/CEP/país) existe nos dois e é diferente;
    campo ausente de um lado (endereço menos detalhado) não é discordância."""
    cur, inc = _address_slots(current), _address_slots(incoming)
    return any(cur[s] != inc[s] for s in cur.keys() & inc.keys())


def _merged_address(current, incoming) -> Address:
    """Refresh da mesma fonte: o que ela trouxe vale; o que ela não trouxe fica como estava."""
    cur = Address(**current) if isinstance(current, dict) else current
    inc = Address(**incoming) if isinstance(incoming, dict) else incoming
    return Address(**{s: getattr(inc, s) or getattr(cur, s) for s in _ADDRESS_SLOTS})


def with_field_sources(company: Company, source_type: str, fields: tuple[str, ...] = RECONCILED_FIELDS) -> Company:
    """Empresa NOVA: registra a fonte de cada campo reconciliável já preenchido. Sem isso, quando
    uma segunda fonte entrar em `sources` o dono do campo viraria "legacy" (ambíguo)."""
    sources = {
        f: source_type for f in fields
        if comparable(f, getattr(company, f)) is not None and f not in company.field_sources
    }
    return company.model_copy(update={"field_sources": {**company.field_sources, **sources}}) if sources else company


def reconcile(
    persisted: Company, fetched: Company, source_type: str,
    rejected: frozenset[tuple[str, str, str]] = frozenset(), fields: tuple[str, ...] = RECONCILED_FIELDS,
) -> ReconcileResult:
    """Reconcilia o que a fonte `source_type` trouxe com a empresa já gravada.
    - campo vazio no gravado: preenche (não é sobrescrita);
    - mesma fonte que gravou o campo, valor diferente: ATUALIZA e devolve a mudança (vai pra auditoria);
    - outra fonte, valor diferente: abre CONFLITO e mantém o valor atual;
    - valor ausente na fonte nunca apaga nem discorda; `mapping` (escolha explícita do usuário) nunca
      é contestado pela fonte padrão; um par (campo, fonte, valor) já rejeitado numa resolução não reabre.
    O resto da empresa (is_customer, last_activity_at, sources…) segue `merge_pair`."""
    base = merge_pair(persisted, fetched)
    updates: dict[str, Any] = {}
    sources = dict(persisted.field_sources)
    changes: list[FieldChange] = []
    conflicts: list[ConflictProposal] = []
    for field in fields:
        current, incoming = getattr(persisted, field), getattr(fetched, field)
        current_key, incoming_key = comparable(field, current), comparable(field, incoming)
        if current_key is not None and field not in sources:
            # Fixa o dono AGORA: depois do merge `sources` ganha outra fonte e o dono derivado viraria "legacy".
            owner_now = effective_field_source(persisted, field)
            if owner_now != LEGACY_SOURCE:  # "legacy" nunca é gravado: é só "não sei", e uma resolução/fonte real o substitui
                sources[field] = owner_now
        if incoming_key is None or incoming_key == current_key:
            continue
        if field == "address" and current_key is not None and not _address_differs(current, incoming):
            continue
        if current_key is None:
            updates[field] = incoming
            sources[field] = source_type
            continue
        owner = effective_field_source(persisted, field)
        if owner == "mapping":
            continue
        if owner == source_type:
            new_value = _merged_address(current, incoming) if field == "address" else incoming
            updates[field] = new_value
            sources[field] = source_type
            changes.append(FieldChange(field, current, new_value))
        elif (field, source_type, incoming_key) not in rejected:
            conflicts.append(ConflictProposal(field, current, owner, incoming, source_type))
    company = base.model_copy(update={**updates, "field_sources": sources})
    return ReconcileResult(company=company, changes=changes, conflicts=conflicts)
