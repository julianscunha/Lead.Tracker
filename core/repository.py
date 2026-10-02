"""
Repositório — ponte entre os modelos de domínio (Pydantic,
core/models.py) e as tabelas (SQLAlchemy, core/db_models.py).

Upsert via session.merge() (insere ou atualiza pela PK, sem exists-check
manual). Mapeamento Pydantic<->ORM fica explícito por entidade — 9 entidades
com forma idêntica de CRUD justificam esse tanto de repetição; um
Repository[T] genérico esconderia a diferença de campos entre elas.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.geo_discovery import GEO_DISCOVERY_OPPORTUNITY_TYPE
from core.normalization import ConflictProposal, FieldChange, comparable
from core.db_models import (
    AuditLogORM, FieldConflictORM, CompanyORM, CompanySignalORM, ContactORM, CorrelationRuleORM, DoNotContactORM, FieldMappingORM, ICPProfileORM, OpportunityORM,
    OpportunitySnapshotORM, OpportunityStatusChangeORM, OutreachTouchORM, PortfolioORM, ProductORM, RepTargetORM,
    ServiceORM, VendorORM,
)
from core.models import (
    Address, AuditEntry, FieldConflict, FieldConflictCandidate, Company, CompanySignal, ContextNote, Contact, CorrelationRule, DismissalReason,
    DiscoveryRequiredError, DismissalReasonRequiredError, DoNotContact, DoNotContactReason, FieldMapping, ICPProfile, Opportunity, OpportunitySnapshot,
    OpportunityStatus, OpportunityStatusChange, OutreachTouch, PeriodType, Portfolio, Product, ProductRelation,
    RepTarget, SemanticFieldRole, Service, SourceRef, StatusChangeRequiresJustificationError, Vendor,
)
from core.opportunity_engine import (
    is_discovery_complete, is_valid_discovery_text, is_zombie_opportunity, requires_discovery_gate, requires_status_change_justification,
)


def _sources_to_json(sources: list[SourceRef]) -> list[dict]:
    return [s.model_dump() for s in sources]


def _sources_from_json(data: list[dict] | None) -> list[SourceRef]:
    return [SourceRef(**d) for d in (data or [])]


def _note_to_json(note: ContextNote | None) -> dict | None:
    return note.model_dump(mode="json") if note else None


def _note_from_json(data: dict | None) -> ContextNote | None:
    return ContextNote(**data) if data else None


def _notes_to_json(notes: list[ContextNote]) -> list[dict]:
    return [n.model_dump(mode="json") for n in notes]


def _notes_from_json(data: list[dict] | None) -> list[ContextNote]:
    return [ContextNote(**d) for d in (data or [])]


def _address_to_json(address: Address | None) -> dict | None:
    return address.model_dump(mode="json") if address else None


def _address_from_json(data: dict | None) -> Address | None:
    return Address(**data) if data else None


def _relations_to_json(relations: list[ProductRelation]) -> list[dict]:
    return [r.model_dump() for r in relations]


def _relations_from_json(data: list[dict] | None) -> list[ProductRelation]:
    return [ProductRelation(**d) for d in (data or [])]


def _ensure_utc(value: datetime) -> datetime:
    """SQLite/SQLAlchemy descarta tzinfo ao ler de volta — sempre gravamos em
    UTC (core/models.py _now()), então reanexa aqui em vez de deixar o
    chamador comparar aware com naive silenciosamente."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


async def _upsert(session: AsyncSession, row) -> None:
    await session.merge(row)
    await session.commit()


# ── Vendor ───────────────────────────────────────────────────────────────────

async def save_vendor(session: AsyncSession, vendor: Vendor) -> None:
    await _upsert(session, VendorORM(id=vendor.id, name=vendor.name))


async def list_vendors(session: AsyncSession) -> list[Vendor]:
    rows = (await session.execute(select(VendorORM))).scalars().all()
    return [Vendor(id=r.id, name=r.name) for r in rows]


async def delete_vendor(session: AsyncSession, vendor_id: str) -> bool:
    row = await session.get(VendorORM, vendor_id)
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


# ── Product ──────────────────────────────────────────────────────────────────

async def save_product(session: AsyncSession, product: Product) -> None:
    await _upsert(session, ProductORM(
        id=product.id, vendor_id=product.vendor_id, name=product.name,
        aliases=product.aliases, description=product.description,
        status=product.status, category=product.category,
        related_services=_relations_to_json(product.related_services),
    ))


def _product_from_row(r: ProductORM) -> Product:
    return Product(
        id=r.id, vendor_id=r.vendor_id, name=r.name, aliases=r.aliases,
        description=r.description, status=r.status, category=r.category,
        related_services=_relations_from_json(r.related_services),
    )


async def list_products(session: AsyncSession) -> list[Product]:
    rows = (await session.execute(select(ProductORM))).scalars().all()
    return [_product_from_row(r) for r in rows]


async def get_product(session: AsyncSession, product_id: str) -> Product | None:
    row = await session.get(ProductORM, product_id)
    return _product_from_row(row) if row else None


async def delete_product(session: AsyncSession, product_id: str) -> bool:
    row = await session.get(ProductORM, product_id)
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


# ── Service ──────────────────────────────────────────────────────────────────

async def save_service(session: AsyncSession, service: Service) -> None:
    await _upsert(session, ServiceORM(
        id=service.id, name=service.name, description=service.description,
        status=service.status, category=service.category,
    ))


def _service_from_row(r: ServiceORM) -> Service:
    return Service(id=r.id, name=r.name, description=r.description, status=r.status, category=r.category)


async def list_services(session: AsyncSession) -> list[Service]:
    rows = (await session.execute(select(ServiceORM))).scalars().all()
    return [_service_from_row(r) for r in rows]


async def get_service(session: AsyncSession, service_id: str) -> Service | None:
    row = await session.get(ServiceORM, service_id)
    return _service_from_row(row) if row else None


async def delete_service(session: AsyncSession, service_id: str) -> bool:
    row = await session.get(ServiceORM, service_id)
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


# ── Company ──────────────────────────────────────────────────────────────────

def _company_from_row(row: CompanyORM) -> Company:
    return Company(
        id=row.id, name=row.name, legal_name=row.legal_name, website=row.website,
        is_customer=row.is_customer, customer_status=row.customer_status,
        sources=_sources_from_json(row.sources), created_at=_ensure_utc(row.created_at), updated_at=_ensure_utc(row.updated_at),
        rep_id=row.rep_id, segment=row.segment, region=row.region,
        trigger_event=_note_from_json(row.trigger_event),
        attempted_solutions=_notes_from_json(row.attempted_solutions),
        strategic_context=_note_from_json(row.strategic_context),
        last_activity_at=_ensure_utc(row.last_activity_at) if row.last_activity_at else None,
        renewal_date=_ensure_utc(row.renewal_date) if row.renewal_date else None,
        industry=row.industry, annual_revenue=row.annual_revenue, employee_count=row.employee_count,
        address=_address_from_json(row.address), deal_size_hint=row.deal_size_hint,
        field_sources=dict(row.field_sources or {}),
    )


async def save_company(session: AsyncSession, company: Company) -> None:
    """Caminho de escrita do sync (chamado por backend/sync.py com o objeto
    já reconciliado por merge_pair). Upsert atômico (mesmo padrão de
    save_opportunity, mesma classe de TOCTOU encontrada aqui por revisão de
    código): `renewal_date` nunca entra no SET do upsert, mesmo que o
    `Company` recebido carregue um valor — o objeto em memória do sync pode
    ter sido capturado antes de um `update_company_renewal_date` concorrente
    confirmar, e um merge de linha inteira reverteria a edição manual mais
    recente. `renewal_date` só é gravado por `update_company_renewal_date`."""
    engine_columns = dict(
        name=company.name, legal_name=company.legal_name, website=company.website,
        is_customer=company.is_customer, customer_status=company.customer_status,
        sources=_sources_to_json(company.sources), created_at=company.created_at, updated_at=company.updated_at,
        rep_id=company.rep_id, segment=company.segment, region=company.region,
        trigger_event=_note_to_json(company.trigger_event),
        attempted_solutions=_notes_to_json(company.attempted_solutions),
        strategic_context=_note_to_json(company.strategic_context),
        last_activity_at=company.last_activity_at,
        industry=company.industry, annual_revenue=company.annual_revenue, employee_count=company.employee_count,
        address=_address_to_json(company.address), deal_size_hint=company.deal_size_hint,
        field_sources=company.field_sources or None,
    )
    stmt = sqlite_insert(CompanyORM).values(id=company.id, renewal_date=None, **engine_columns)
    stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=engine_columns)
    await session.execute(stmt)
    await session.commit()


async def get_company(session: AsyncSession, company_id: str) -> Company | None:
    row = await session.get(CompanyORM, company_id)
    return _company_from_row(row) if row else None


# ── AuditLog (Fase M) ────────────────────────────────────────────────────────

def _to_utc(value):
    """Datetime com offset vira UTC ANTES de gravar: o SQLite guarda a data sem fuso, então um
    `-03:00` gravado cru seria relido como UTC e geraria uma "alteração" falsa a cada sync."""
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc)
    return value


def _audit_text(value) -> str | None:
    """Texto estável pra comparar/gravar: data em ISO UTC, enum pelo `.value`."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return _ensure_utc(_to_utc(value)).isoformat()
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _text_marker(old: str | None, new: str | None) -> tuple[str | None, str | None] | None:
    """Campo de texto livre pessoal: nunca grava o conteúdo, só o tipo da mudança.
    `None` quando nada mudou (sem entrada no log)."""
    if (old or None) == (new or None):
        return None
    if not old:
        return None, "preenchido"
    if not new:
        return "preenchido", "removido"
    return "preenchido", "alterado"


def _audit(
    session: AsyncSession, entity_type: str, entity_id: str, company_id: str | None, field: str,
    old, new, actor: str | None = None,
) -> None:
    """Adiciona a entrada à sessão SEM commit: quem chama commita junto com a mudança
    (mesma transação). Valor igual = nenhuma entrada."""
    old_text, new_text = _audit_text(old), _audit_text(new)
    if old_text == new_text:
        return
    session.add(AuditLogORM(
        id=AuditEntry(entity_type=entity_type, entity_id=entity_id, field=field).id,
        entity_type=entity_type, entity_id=entity_id, company_id=company_id, field=field,
        old_value=old_text, new_value=new_text, changed_at=datetime.now(timezone.utc), actor=actor,
    ))


def _audit_marker(
    session: AsyncSession, entity_type: str, entity_id: str, company_id: str | None, field: str,
    old: str | None, new: str | None, actor: str | None = None,
) -> None:
    marker = _text_marker(old, new)
    if marker is not None:
        _audit(session, entity_type, entity_id, company_id, field, marker[0], marker[1], actor)


# ── FieldConflict (Fase N) ───────────────────────────────────────────────────

def _json_value(value):
    """Valor de campo em JSON puro (endereço vira dict)."""
    return value.model_dump() if isinstance(value, Address) else value


def _typed_value(field: str, value):
    return Address(**value) if field == "address" and isinstance(value, dict) else value


def _conflict_from_row(r: FieldConflictORM) -> FieldConflict:
    return FieldConflict(
        id=r.id, company_id=r.company_id, field=r.field,
        candidates=[FieldConflictCandidate(**c) for c in (r.candidates or [])], status=r.status,
        resolved_value=r.resolved_value, resolved_source=r.resolved_source,
        resolved_at=_ensure_utc(r.resolved_at) if r.resolved_at else None,
        rejected=list(r.rejected or []), created_at=_ensure_utc(r.created_at),
    )


async def list_field_conflicts(session: AsyncSession, status: str = "open") -> list[FieldConflict]:
    rows = (await session.execute(select(FieldConflictORM).where(FieldConflictORM.status == status))).scalars().all()
    return sorted((_conflict_from_row(r) for r in rows), key=lambda c: c.created_at)


async def rejected_conflict_keys(session: AsyncSession) -> dict[str, frozenset[tuple[str, str, str]]]:
    """company_id -> {(campo, fonte, valor comparável)} já recusados em resoluções (Fase N)."""
    rows = (await session.execute(select(FieldConflictORM).where(FieldConflictORM.status == "resolved"))).scalars().all()
    out: dict[str, set[tuple[str, str, str]]] = {}
    for r in rows:
        for key in r.rejected or []:
            field, source, value_key = key.split("|", 2)
            out.setdefault(r.company_id, set()).add((field, source, value_key))
    return {company_id: frozenset(keys) for company_id, keys in out.items()}


async def record_reconciliation(
    session: AsyncSession, company_id: str, changes: list[FieldChange], conflicts: list[ConflictProposal],
    source_type: str,
) -> None:
    """Depois do `save_company`: audita a atualização feita pela mesma fonte (`sync:<fonte>`) e abre
    (ou atualiza) um conflito por campo, sem duplicar. Um commit só."""
    for change in changes:
        _audit(session, "company", company_id, company_id, change.field, change.old, change.new, f"sync:{source_type}")
    now = datetime.now(timezone.utc)
    for proposal in conflicts:
        existing = (await session.execute(select(FieldConflictORM).where(
            FieldConflictORM.company_id == company_id, FieldConflictORM.field == proposal.field,
            FieldConflictORM.status == "open",
        ))).scalars().first()
        current = FieldConflictCandidate(source=proposal.current_source, value=_json_value(proposal.current_value), seen_at=now)
        incoming = FieldConflictCandidate(source=proposal.incoming_source, value=_json_value(proposal.incoming_value), seen_at=now)
        if existing is None:
            session.add(FieldConflictORM(
                id=FieldConflict(company_id=company_id, field=proposal.field).id, company_id=company_id,
                field=proposal.field, candidates=[current.model_dump(mode="json"), incoming.model_dump(mode="json")],
                status="open", resolved_value=None, rejected=[], created_at=now,
            ))
            continue
        kept = [c for c in (existing.candidates or []) if c.get("source") not in (current.source, incoming.source)]
        existing.candidates = [*kept, current.model_dump(mode="json"), incoming.model_dump(mode="json")]
    await session.commit()


async def resolve_field_conflict(
    session: AsyncSession, conflict_id: str, chosen_source: str, actor: str | None = None,
) -> FieldConflict | None:
    """Aplica o valor da fonte escolhida: grava no campo, passa a fonte a dona do campo, audita
    (R3) e guarda os pares recusados (não reabrem). `None` se o conflito não existe/já foi resolvido
    ou a fonte não é candidata (rota decide a mensagem)."""
    row = await session.get(FieldConflictORM, conflict_id)
    if row is None or row.status != "open":
        return None
    chosen = next((c for c in (row.candidates or []) if c.get("source") == chosen_source), None)
    company = await session.get(CompanyORM, row.company_id)
    if chosen is None or company is None:
        return None
    new_value = chosen.get("value")
    old_value = getattr(company, row.field)
    if comparable(row.field, old_value) != comparable(row.field, new_value):
        _audit(session, "company", company.id, company.id, row.field, old_value, new_value, actor)
        setattr(company, row.field, new_value)
    company.field_sources = {**(company.field_sources or {}), row.field: chosen_source}
    row.rejected = [
        f"{row.field}|{c['source']}|{comparable(row.field, _typed_value(row.field, c.get('value')))}"
        for c in (row.candidates or [])
        if c.get("source") != chosen_source and comparable(row.field, _typed_value(row.field, c.get("value"))) is not None
    ]
    row.status = "resolved"
    row.resolved_value = new_value
    row.resolved_source = chosen_source
    row.resolved_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(row)
    return _conflict_from_row(row)


async def list_audit_entries(
    session: AsyncSession, *, company_id: str | None = None, entity_type: str | None = None,
    entity_id: str | None = None,
) -> list[AuditEntry]:
    """Mais recentes primeiro."""
    stmt = select(AuditLogORM)
    if company_id is not None:
        stmt = stmt.where(AuditLogORM.company_id == company_id)
    if entity_type is not None:
        stmt = stmt.where(AuditLogORM.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditLogORM.entity_id == entity_id)
    rows = (await session.execute(stmt)).scalars().all()
    entries = [AuditEntry(
        id=r.id, entity_type=r.entity_type, entity_id=r.entity_id, company_id=r.company_id, field=r.field,
        old_value=r.old_value, new_value=r.new_value, changed_at=_ensure_utc(r.changed_at), actor=r.actor,
    ) for r in rows]
    return sorted(entries, key=lambda e: e.changed_at, reverse=True)


async def update_company_renewal_date(
    session: AsyncSession, company_id: str, renewal_date: datetime | None, actor: str | None = None,
) -> Company | None:
    """Único caminho de escrita de renewal_date (manual, cadência de QBR) —
    só essa coluna, nunca session.merge() da linha inteira. Sem o risco de
    TOCTOU do save_opportunity original: um UPDATE de coluna única não
    reconstrói o resto da linha, não há nada pra sobrescrever."""
    row = await session.get(CompanyORM, company_id)
    if row is None:
        return None
    renewal_date = _to_utc(renewal_date)
    _audit(session, "company", company_id, company_id, "renewal_date", row.renewal_date, renewal_date, actor)
    row.renewal_date = renewal_date
    await session.commit()
    return _company_from_row(row)


async def apply_field_mapping_updates(session: AsyncSession, company_id: str, updates: dict) -> None:
    """Fase F, módulo 4 (`mapping-driven-context-split`) — escrita
    direcionada só das colunas mapeadas (`industry`/`renewal_date`/
    `deal_size_hint`, ver `core/field_mapping.py::split_custom_fields`),
    mesmo padrão de coluna única de `update_company_renewal_date`: nunca
    um upsert de linha inteira, que reverteria uma edição concorrente em
    outro campo. `renewal_date` é a única exceção deliberada ao bloqueio
    de `save_company` — aqui é o usuário escolhendo explicitamente uma
    fonte externa como verdade pra esse campo (Salesforce Architect
    consultado), não o /sync automático de sempre."""
    if not updates:
        return
    row = await session.get(CompanyORM, company_id)
    if row is None:
        return
    for column, value in updates.items():
        value = _to_utc(value)
        # Escrita automática do sync: sem isso o renewal_date mudaria sem rastro (Fase M).
        _audit(session, "company", company_id, company_id, column, getattr(row, column, None), value, "sync")
        setattr(row, column, value)
    # Escolha explícita do usuário de uma fonte externa como verdade pro campo (Fase N).
    row.field_sources = {**(row.field_sources or {}), **{column: "mapping" for column in updates}}
    await session.commit()


async def list_companies(session: AsyncSession) -> list[Company]:
    rows = (await session.execute(select(CompanyORM))).scalars().all()
    return [_company_from_row(r) for r in rows]


async def count_geo_discoveries_today(session: AsyncSession, rep_id: str, today: date) -> int:
    """Cota diária de `anti-spam-promotion-gate` — conta OPORTUNIDADES
    `geo-discovery` criadas hoje (UTC) em empresas do rep, não empresas novas:
    desde a Fase K a promoção pode reaproveitar uma empresa existente, e
    contar `Company` criada hoje deixaria esse caso fora da cota. ponytail:
    a empresa reaproveitada mantém o rep original, então a cota é do rep dono
    da empresa; o volume por rep/dia é pequeno (cap default 20), por isso o
    filtro por data roda em Python."""
    stmt = (
        select(OpportunityORM.first_detected_at)
        .join(CompanyORM, CompanyORM.id == OpportunityORM.company_id)
        .where(CompanyORM.rep_id == rep_id, OpportunityORM.type == GEO_DISCOVERY_OPPORTUNITY_TYPE)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return sum(1 for detected_at in rows if _ensure_utc(detected_at).date() == today)


# ── Contact ──────────────────────────────────────────────────────────────────

def _contact_from_row(row: ContactORM) -> Contact:
    return Contact(
        id=row.id, company_id=row.company_id, name=row.name, email=row.email,
        role=row.role, phone=row.phone, sources=_sources_from_json(row.sources),
        impacted_area=row.impacted_area, seniority_tier=row.seniority_tier, stance=row.stance,
    )


async def save_contact(session: AsyncSession, contact: Contact) -> None:
    """Caminho de escrita do sync (mesmo padrão de `save_company`):
    `stance` nunca entra no SET do upsert, mesmo que o `Contact` recebido
    carregue um valor — é preenchimento manual do rep (Deal Strategist
    consultado, Fase H módulo 2), e um /sync que roda depois reverteria a
    avaliação mais recente se a linha inteira fosse sobrescrita. Só
    `update_contact_stance` grava essa coluna."""
    engine_columns = dict(
        company_id=contact.company_id, name=contact.name, email=contact.email, phone=contact.phone,
        role=contact.role, sources=_sources_to_json(contact.sources), impacted_area=contact.impacted_area,
        seniority_tier=contact.seniority_tier,
    )
    stmt = sqlite_insert(ContactORM).values(id=contact.id, stance=None, **engine_columns)
    stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=engine_columns)
    await session.execute(stmt)
    await session.commit()


async def update_contact_stance(
    session: AsyncSession, contact_id: str, stance: str | None, actor: str | None = None,
) -> Contact | None:
    """Único caminho de escrita de `stance` — só essa coluna, nunca
    `session.merge()` da linha inteira (mesmo padrão de
    `update_company_renewal_date`)."""
    row = await session.get(ContactORM, contact_id)
    if row is None:
        return None
    _audit(session, "contact", contact_id, row.company_id, "stance", row.stance, stance, actor)
    row.stance = stance
    await session.commit()
    return _contact_from_row(row)


async def list_contacts(session: AsyncSession, company_id: str) -> list[Contact]:
    rows = (await session.execute(select(ContactORM).where(ContactORM.company_id == company_id))).scalars().all()
    return [_contact_from_row(r) for r in rows]


# ── Opportunity ──────────────────────────────────────────────────────────────

def _opportunity_from_row(row: OpportunityORM) -> Opportunity:
    return Opportunity(
        id=row.id, company_id=row.company_id, type=row.type, vendor_id=row.vendor_id,
        product_id=row.product_id, service_id=row.service_id, opportunity_score=row.opportunity_score,
        financial_potential=row.financial_potential, strategic_score=row.strategic_score,
        confidence_score=row.confidence_score, evidence=row.evidence, justification=row.justification,
        sources=_sources_from_json(row.sources), status=OpportunityStatus(row.status),
        risk_flag=row.risk_flag, evidence_summary=row.evidence_summary,
        discovery_prompt=row.discovery_prompt, synced_at=_ensure_utc(row.synced_at),
        first_detected_at=_ensure_utc(row.first_detected_at),
        scope_note=row.scope_note, criticality=row.criticality, severity_note=row.severity_note,
        dismissal_reason=DismissalReason(row.dismissal_reason) if row.dismissal_reason else None,
        root_cause_stated=row.root_cause_stated, trigger_event=row.trigger_event,
        champion_stake=row.champion_stake, discovery_skipped=bool(row.discovery_skipped),
        discovery_skip_reason=row.discovery_skip_reason,
        discovery_edited_at=_ensure_utc(row.discovery_edited_at) if row.discovery_edited_at else None,
    )


async def save_opportunity(session: AsyncSession, opportunity: Opportunity) -> None:
    """Caminho de escrita do MOTOR (chamado a cada `/sync`). O motor nunca
    sabe de scope_note/criticality/severity_note (Fase C, Fatia 5 — campos
    100% manuais). Upsert atômico via `INSERT ... ON CONFLICT DO UPDATE`
    que nunca lista essas 3 colunas no `set_` — ao contrário de um
    fetch-then-merge, não existe janela entre leitura e escrita onde um
    `update_opportunity_qualification` concorrente possa ser sobrescrito
    (revisão de código apontou o TOCTOU da versão anterior). Escrita
    manual desses 3 campos usa `update_opportunity_qualification`, nunca
    esta função.

    `status` segue a mesma regra (achado da Fase D, mesmo agente `Plan`):
    o motor sempre constrói a oportunidade em `detected`
    (`_build_opportunity`) e o id é determinístico — sem excluir `status`
    do `SET`, rodar `/sync` de novo pra uma empresa cujo portfólio não
    mudou resetaria pra `detected` qualquer oportunidade já avançada
    manualmente. Só entra no `INSERT` inicial (nova oportunidade nasce em
    `detected`); depois disso, `status` só muda por `update_opportunity_status`.

    `first_detected_at` também fica fora do `SET` (achado da revisão de
    código do snapshot diário): `synced_at`, ao contrário, É atualizado a
    cada `/sync` que ainda detecta a oportunidade — usá-lo como proxy de
    "há quanto tempo parada" faria uma oportunidade nunca-triada parecer
    sempre fresca, o motor "renovaria" o timestamp indefinidamente e o
    zumbi nunca dispararia pra exatamente a população que deveria capturar.
    `first_detected_at` é gravado só no `INSERT` e nunca mais tocado — é a
    base real do fallback de zumbi em `recompute_daily_snapshot`."""
    engine_columns = dict(
        company_id=opportunity.company_id, type=opportunity.type,
        vendor_id=opportunity.vendor_id, product_id=opportunity.product_id, service_id=opportunity.service_id,
        opportunity_score=opportunity.opportunity_score, financial_potential=opportunity.financial_potential,
        strategic_score=opportunity.strategic_score, confidence_score=opportunity.confidence_score,
        evidence=opportunity.evidence, justification=opportunity.justification,
        sources=_sources_to_json(opportunity.sources),
        risk_flag=opportunity.risk_flag, evidence_summary=opportunity.evidence_summary,
        discovery_prompt=opportunity.discovery_prompt, synced_at=opportunity.synced_at,
    )
    stmt = sqlite_insert(OpportunityORM).values(
        id=opportunity.id, status=opportunity.status.value,
        first_detected_at=opportunity.first_detected_at, **engine_columns,
    )
    stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=engine_columns)
    await session.execute(stmt)
    await session.commit()


async def update_opportunity_qualification(
    session: AsyncSession, opportunity_id: str,
    scope_note: str | None, criticality: str | None, severity_note: str | None, actor: str | None = None,
) -> Opportunity | None:
    """Único caminho de escrita de scope_note/criticality/severity_note
    (Fase C, Fatia 5) — entrada manual do vendedor, nunca tocada por
    `save_opportunity` (caminho do motor). Substituição completa dos 3
    campos a cada chamada — a UI sempre envia o estado atual dos 3
    controles, sem merge parcial ambíguo. `None` se a oportunidade não
    existir (rota decide o 404)."""
    row = await session.get(OpportunityORM, opportunity_id)
    if row is None:
        return None
    _audit(session, "opportunity", opportunity_id, row.company_id, "scope_note", row.scope_note, scope_note, actor)
    _audit(session, "opportunity", opportunity_id, row.company_id, "criticality", row.criticality, criticality, actor)
    _audit_marker(session, "opportunity", opportunity_id, row.company_id, "severity_note", row.severity_note, severity_note, actor)
    row.scope_note = scope_note
    row.criticality = criticality
    row.severity_note = severity_note
    await session.commit()
    return _opportunity_from_row(row)


async def update_opportunity_discovery(
    session: AsyncSession, opportunity_id: str,
    root_cause_stated: str | None, trigger_event: str | None, champion_stake: str | None, actor: str | None = None,
) -> Opportunity | None:
    """Único caminho de escrita dos 3 campos de discovery (Fase J) — manual,
    nunca tocado por `save_opportunity` (motor). Substituição completa, como
    `update_opportunity_qualification`. Não valida o conteúdo: o gate valida
    na saída de `detected`; aqui o rascunho parcial é permitido."""
    row = await session.get(OpportunityORM, opportunity_id)
    if row is None:
        return None
    new_values = {
        "root_cause_stated": (root_cause_stated or "").strip() or None,
        "trigger_event": (trigger_event or "").strip() or None,
        "champion_stake": (champion_stake or "").strip() or None,
    }
    changed = False
    for field, new in new_values.items():
        old = getattr(row, field)
        if (old or None) != new:
            changed = True
            # Texto pessoal: só o marcador, nunca o conteúdo (LGPD).
            _audit_marker(session, "opportunity", opportunity_id, row.company_id, field, old, new, actor)
            setattr(row, field, new)
    if changed:
        row.discovery_edited_at = datetime.now(timezone.utc)
    await session.commit()
    return _opportunity_from_row(row)


async def get_opportunity(session: AsyncSession, opportunity_id: str) -> Opportunity | None:
    row = await session.get(OpportunityORM, opportunity_id)
    return _opportunity_from_row(row) if row else None


async def list_opportunities(session: AsyncSession, company_id: str | None = None) -> list[Opportunity]:
    query = select(OpportunityORM)
    if company_id is not None:
        query = query.where(OpportunityORM.company_id == company_id)
    rows = (await session.execute(query)).scalars().all()
    return [_opportunity_from_row(r) for r in rows]


# ── Portfolio ────────────────────────────────────────────────────────────────

def _portfolio_from_row(row: PortfolioORM) -> Portfolio:
    return Portfolio(
        id=row.id, company_id=row.company_id, vendor_ids=row.vendor_ids, product_ids=row.product_ids,
        service_ids=row.service_ids, relations=row.relations, notes=row.notes, updated_at=_ensure_utc(row.updated_at),
    )


async def save_portfolio(session: AsyncSession, portfolio: Portfolio) -> None:
    await _upsert(session, PortfolioORM(
        id=portfolio.id, company_id=portfolio.company_id, vendor_ids=portfolio.vendor_ids,
        product_ids=portfolio.product_ids, service_ids=portfolio.service_ids,
        relations=portfolio.relations, notes=portfolio.notes, updated_at=portfolio.updated_at,
    ))


async def get_portfolio_by_company(session: AsyncSession, company_id: str) -> Portfolio | None:
    row = (await session.execute(select(PortfolioORM).where(PortfolioORM.company_id == company_id))).scalar_one_or_none()
    return _portfolio_from_row(row) if row else None


# ── CompanySignal ────────────────────────────────────────────────────────────

async def list_company_signals(session: AsyncSession, company_id: str) -> list[CompanySignal]:
    rows = (await session.execute(select(CompanySignalORM).where(CompanySignalORM.company_id == company_id))).scalars().all()
    return [CompanySignal(
        id=r.id, company_id=r.company_id, signal_type=r.signal_type, evidence=r.evidence,
        source=SourceRef(**r.source), confidence=r.confidence,
        detected_at=_ensure_utc(r.detected_at), status=r.status,
    ) for r in rows]


# ── OutreachTouch ────────────────────────────────────────────────────────────

async def save_outreach_touch(session: AsyncSession, touch: OutreachTouch) -> None:
    """Insert-only — fato consumado ("marcado como enviado"), nunca editado
    nem desfeito depois de registrado (mesmo espírito de
    `OpportunityStatusChange`: histórico imutável)."""
    session.add(OutreachTouchORM(
        id=touch.id, opportunity_id=touch.opportunity_id, rep_id=touch.rep_id,
        contact_id=touch.contact_id, channel=touch.channel, reason_label=touch.reason_label,
        sent_at=touch.sent_at, block_acknowledged=touch.block_acknowledged,
    ))
    await session.commit()


async def list_outreach_touches(session: AsyncSession, opportunity_id: str) -> list[OutreachTouch]:
    rows = (await session.execute(
        select(OutreachTouchORM).where(OutreachTouchORM.opportunity_id == opportunity_id)
    )).scalars().all()
    return [OutreachTouch(
        id=r.id, opportunity_id=r.opportunity_id, rep_id=r.rep_id, contact_id=r.contact_id,
        channel=r.channel, reason_label=r.reason_label, sent_at=_ensure_utc(r.sent_at),
        block_acknowledged=bool(r.block_acknowledged),
    ) for r in rows]


# ── DoNotContact (Fase L) ────────────────────────────────────────────────────

def _do_not_contact_from_row(r: DoNotContactORM) -> DoNotContact:
    return DoNotContact(
        id=r.id, company_id=r.company_id, contact_id=r.contact_id, contact_email=r.contact_email,
        channel=r.channel, reason=DoNotContactReason(r.reason), comment=r.comment, created_by=r.created_by,
        created_at=_ensure_utc(r.created_at),
        lifted_at=_ensure_utc(r.lifted_at) if r.lifted_at else None,
        lifted_by=r.lifted_by, lift_reason=r.lift_reason,
    )


async def save_do_not_contact(session: AsyncSession, entry: DoNotContact) -> None:
    """Só insere — retirar usa `lift_do_not_contact`. Quem chama já normalizou
    `contact_email`/`channel` (ver `core.opportunity_engine.normalize_block_text`)."""
    session.add(DoNotContactORM(
        id=entry.id, company_id=entry.company_id, contact_id=entry.contact_id,
        contact_email=entry.contact_email, channel=entry.channel, reason=entry.reason.value,
        comment=entry.comment, created_by=entry.created_by, created_at=entry.created_at,
    ))
    await session.commit()


async def list_do_not_contact(
    session: AsyncSession, company_id: str | None = None, active_only: bool = False,
) -> list[DoNotContact]:
    """`company_id=None` devolve de todas as empresas (o casamento por e-mail
    vale globalmente). Ativos primeiro, mais recentes antes."""
    stmt = select(DoNotContactORM)
    if company_id is not None:
        stmt = stmt.where(DoNotContactORM.company_id == company_id)
    if active_only:
        stmt = stmt.where(DoNotContactORM.lifted_at.is_(None))
    rows = (await session.execute(stmt)).scalars().all()
    entries = [_do_not_contact_from_row(r) for r in rows]
    return sorted(entries, key=lambda e: (e.lifted_at is not None, -e.created_at.timestamp()))


async def lift_do_not_contact(
    session: AsyncSession, entry_id: str, lifted_by: str, lift_reason: str | None,
) -> DoNotContact | None:
    """Retira UMA vez: `UPDATE ... WHERE lifted_at IS NULL` — a segunda chamada
    não sobrescreve quem/quando/por quê da primeira. `None` se o id não existe."""
    await session.execute(
        update(DoNotContactORM)
        .where(DoNotContactORM.id == entry_id, DoNotContactORM.lifted_at.is_(None))
        .values(lifted_at=datetime.now(timezone.utc), lifted_by=lifted_by, lift_reason=lift_reason)
    )
    await session.commit()
    row = await session.get(DoNotContactORM, entry_id)
    if row is not None:
        await session.refresh(row)
    return _do_not_contact_from_row(row) if row else None


async def count_outreach_touches_today(session: AsyncSession, rep_id: str, today: date) -> int:
    """Cota diária de prospecção fria (módulo 6) — mesmo padrão UTC de
    `count_geo_discoveries_today` (Fase E): comparar contra data LOCAL em vez
    de `datetime.now(timezone.utc).date()` desalinha a cota perto da meia-noite
    em qualquer servidor fora de UTC (bug real já encontrado e corrigido uma
    vez nesta base de código — nunca repetir aqui).

    ponytail: carrega todo o histórico do rep e filtra em Python — mesmo
    padrão aceito em `count_geo_discoveries_today`, mas aqui a suposição de
    volume é mais frágil (outreach não tem cota própria que limite o total
    acumulado ao longo da vida da oportunidade, diferente de descoberta
    geográfica). Upgrade quando doer: `WHERE sent_at >= início do dia UTC`,
    e um índice composto `(rep_id, sent_at)` se o volume justificar."""
    rows = (await session.execute(select(OutreachTouchORM).where(OutreachTouchORM.rep_id == rep_id))).scalars().all()
    return sum(1 for r in rows if _ensure_utc(r.sent_at).date() == today)


async def update_opportunity_status(
    session: AsyncSession, opportunity_id: str, new_status: OpportunityStatus, note: str | None = None,
    dismissal_reason: DismissalReason | None = None,
    skip_discovery_reason: str | None = None, discovery_gate_enabled: bool = True,
) -> Opportunity | None:
    """Único caminho de escrita de `status` após a criação — o motor
    (`save_opportunity`) nunca mais toca essa coluna depois do INSERT
    inicial (achado da Fase D, mesma classe de TOCTOU já corrigida em
    scope_note/criticality/renewal_date). Grava o novo status e o registro
    de histórico (`OpportunityStatusChange`, Fase D — até aqui existia no
    modelo mas nunca era escrito em código real) na MESMA transação: se a
    auditoria fosse um passo separado, um crash entre as duas escritas
    deixaria status mudado sem rastro no histórico, esvaziando o propósito
    da tabela (decisão do agente `Plan`). Sem-op (mesmo status) não grava
    histórico — não é uma transição real. `None` se a oportunidade não
    existir (rota decide o 404). A checagem de justificativa roda contra o
    `status` desta MESMA busca — nunca uma leitura separada feita antes de
    chamar esta função (a rota fazia isso e a revisão de código encontrou
    o TOCTOU: entre a leitura da rota e esta escrita, o status real podia
    mudar, por exemplo por outra aba do navegador). Levanta
    `StatusChangeRequiresJustificationError` se a transição pular 2+
    estágios ou reabrir um `dismissed` sem `note`. Levanta
    `DismissalReasonRequiredError` se o novo status for `dismissed` sem
    `dismissal_reason` categorizado (módulo 6, mesma checagem contra o
    status desta MESMA busca). Reabrir um `dismissed` (ir pra qualquer
    outro status) limpa `dismissal_reason` pra `None` — o campo só faz
    sentido enquanto a oportunidade está descartada. A linha de histórico
    (`OpportunityStatusChange`) grava o motivo de qualquer forma e nunca é
    limpa (achado da revisão de código: sem isso, um ciclo
    dismiss→reopen→dismiss-de-novo apagaria irrecuperavelmente o motivo do
    primeiro descarte, inviabilizando qualquer relatório futuro de "por que
    perdemos oportunidades")."""
    row = await session.get(OpportunityORM, opportunity_id)
    if row is None:
        return None
    if row.status == new_status.value:
        return _opportunity_from_row(row)
    if requires_status_change_justification(row.status, new_status.value) and not (note or "").strip():
        raise StatusChangeRequiresJustificationError()
    if new_status == OpportunityStatus.DISMISSED and dismissal_reason is None:
        raise DismissalReasonRequiredError()
    if discovery_gate_enabled and requires_discovery_gate(row.status, new_status.value):
        if not is_discovery_complete(row.root_cause_stated, row.trigger_event, row.champion_stake):
            # Skip já registrado antes (ex.: reabertura de descartada) continua valendo.
            if is_valid_discovery_text(skip_discovery_reason):
                _audit(session, "opportunity", opportunity_id, row.company_id, "discovery_skipped", bool(row.discovery_skipped), True)
                _audit_marker(session, "opportunity", opportunity_id, row.company_id, "discovery_skip_reason", row.discovery_skip_reason, skip_discovery_reason.strip())
                row.discovery_skipped = True
                row.discovery_skip_reason = skip_discovery_reason.strip()
            elif not row.discovery_skipped:
                raise DiscoveryRequiredError()
    row.status = new_status.value
    row.dismissal_reason = dismissal_reason.value if new_status == OpportunityStatus.DISMISSED else None
    change = OpportunityStatusChange(
        opportunity_id=opportunity_id, status=new_status, note=note,
        dismissal_reason=dismissal_reason if new_status == OpportunityStatus.DISMISSED else None,
    )
    session.add(OpportunityStatusChangeORM(
        id=change.id, opportunity_id=change.opportunity_id,
        status=change.status.value, entered_at=change.entered_at, note=change.note,
        dismissal_reason=change.dismissal_reason.value if change.dismissal_reason else None,
    ))
    await session.commit()
    return _opportunity_from_row(row)


# ── OpportunitySnapshot ──────────────────────────────────────────────────────

async def recompute_daily_snapshot(session: AsyncSession, today: date | None = None) -> None:
    """Chamada uma vez no fim de todo `POST /sync` (nunca por leitura do
    dashboard) — grava uma linha por oportunidade viva pro dia de hoje.
    Upsert atômico por `id` determinístico (`opportunity_id:snapshot_date`):
    rodar `/sync` várias vezes no mesmo dia sobrescreve a mesma linha, nunca
    duplica. `last_touch_at` vem do histórico real de transição quando
    existe; sem isso (oportunidade nunca mudou de status manualmente), usa
    `Opportunity.first_detected_at` como proxy (nunca `synced_at`, que o
    motor atualiza a cada `/sync` — ver docstring de `save_opportunity`).
    Todo `OpportunityStatusChange` é buscado numa única query (não uma por
    oportunidade, achado de performance da revisão de código — antes era
    O(n) consultas rodando dentro da mesma transação de escrita).

    Corrida com uma escrita concorrente (ex. alguém chamando
    `update_opportunity_status` no meio deste loop) é aceitável: o
    snapshot é uma foto aproximada do fim do sync, não uma transação
    distribuída — na pior hipótese a linha do dia fica com o estágio de
    um instante atrás e se autocorrige no próximo `/sync`."""
    today = today or date.today()
    now = datetime.now(timezone.utc)
    opportunities = await list_opportunities(session)
    companies = {c.id: c for c in await list_companies(session)}

    all_changes = (await session.execute(select(OpportunityStatusChangeORM))).scalars().all()
    latest_change_by_opportunity: dict[str, datetime] = {}
    for change in all_changes:
        entered_at = _ensure_utc(change.entered_at)
        current = latest_change_by_opportunity.get(change.opportunity_id)
        if current is None or entered_at > current:
            latest_change_by_opportunity[change.opportunity_id] = entered_at

    for o in opportunities:
        last_touch_at = latest_change_by_opportunity.get(o.id, o.first_detected_at)
        zombie = is_zombie_opportunity(o.status.value, last_touch_at, now)
        company = companies.get(o.company_id)
        source = o.sources[0].type if o.sources else None
        row_columns = dict(
            opportunity_id=o.id, snapshot_date=today, stage=o.status.value,
            first_detected_at=o.first_detected_at,
            financial_potential=o.financial_potential, confidence_score=o.confidence_score,
            rep_id=company.rep_id if company else None, segment=company.segment if company else None,
            source=source, is_zombie=zombie,
        )
        stmt = sqlite_insert(OpportunitySnapshotORM).values(id=f"{o.id}:{today.isoformat()}", **row_columns)
        stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=row_columns)
        await session.execute(stmt)
    await session.commit()


def _snapshot_from_row(row: OpportunitySnapshotORM) -> OpportunitySnapshot:
    return OpportunitySnapshot(
        id=row.id, opportunity_id=row.opportunity_id, snapshot_date=row.snapshot_date,
        stage=OpportunityStatus(row.stage), first_detected_at=_ensure_utc(row.first_detected_at),
        financial_potential=row.financial_potential,
        confidence_score=row.confidence_score, rep_id=row.rep_id, segment=row.segment,
        source=row.source, is_zombie=row.is_zombie,
    )


async def list_latest_snapshot(session: AsyncSession) -> list[OpportunitySnapshot]:
    """O dashboard sempre lê daqui — nunca das tabelas transacionais em
    tempo real (decisão de arquitetura do roadmap). Devolve o snapshot mais
    recente disponível (não necessariamente hoje: se `/sync` não rodou
    ainda hoje, mostra o último dia calculado em vez de fingir dado
    inexistente)."""
    latest_date = (await session.execute(select(OpportunitySnapshotORM.snapshot_date).order_by(
        OpportunitySnapshotORM.snapshot_date.desc(),
    ).limit(1))).scalar_one_or_none()
    if latest_date is None:
        return []
    rows = (await session.execute(
        select(OpportunitySnapshotORM).where(OpportunitySnapshotORM.snapshot_date == latest_date)
    )).scalars().all()
    return [_snapshot_from_row(r) for r in rows]


# ── CorrelationRule ──────────────────────────────────────────────────────────

async def save_rule(session: AsyncSession, rule: CorrelationRule) -> None:
    await _upsert(session, CorrelationRuleORM(
        id=rule.id, opportunity_type=rule.opportunity_type, justification=rule.justification,
        requires=rule.requires, absent=rule.absent,
        requires_category=rule.requires_category, absent_category=rule.absent_category,
        relation_type=rule.relation_type, opportunity_score=rule.opportunity_score,
        confidence_score=rule.confidence_score, active=rule.active,
        discovery_prompt=rule.discovery_prompt,
    ))


def _rule_from_row(row: CorrelationRuleORM) -> CorrelationRule:
    return CorrelationRule(
        id=row.id, opportunity_type=row.opportunity_type, justification=row.justification,
        requires=row.requires, absent=row.absent,
        requires_category=row.requires_category, absent_category=row.absent_category,
        relation_type=row.relation_type, opportunity_score=row.opportunity_score,
        confidence_score=row.confidence_score, active=row.active,
        discovery_prompt=row.discovery_prompt,
    )


async def list_rules(session: AsyncSession) -> list[CorrelationRule]:
    rows = (await session.execute(select(CorrelationRuleORM))).scalars().all()
    return [_rule_from_row(r) for r in rows]


async def list_active_rules(session: AsyncSession) -> list[CorrelationRule]:
    rows = (await session.execute(select(CorrelationRuleORM).where(CorrelationRuleORM.active == True))).scalars().all()  # noqa: E712
    return [_rule_from_row(r) for r in rows]


async def delete_rule(session: AsyncSession, rule_id: str) -> bool:
    row = await session.get(CorrelationRuleORM, rule_id)
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


# ── RepTarget ────────────────────────────────────────────────────────────────

async def save_rep_target(session: AsyncSession, target: RepTarget) -> None:
    """Id determinístico (`rep_target_id`) — cadastrar meta de novo pro
    mesmo rep+período é upsert via `_upsert`/`session.merge`, nunca gera
    uma 2ª meta concorrente pro mesmo rep/período. `created_at` do
    registro existente é preservado num upsert (achado da revisão de
    código: sem isso, `_now()` no `.model_construct()` de cada request
    reescreveria o carimbo a cada recadastro, e a coluna se comportaria
    como "última modificação" apesar do nome)."""
    existing = await session.get(RepTargetORM, target.id)
    created_at = existing.created_at if existing is not None else target.created_at
    await _upsert(session, RepTargetORM(
        id=target.id, rep_id=target.rep_id, period_type=target.period_type.value,
        period_key=target.period_key, target_amount=target.target_amount, created_at=created_at,
    ))


def _rep_target_from_row(row: RepTargetORM) -> RepTarget:
    return RepTarget(
        id=row.id, rep_id=row.rep_id, period_type=PeriodType(row.period_type),
        period_key=row.period_key, target_amount=row.target_amount, created_at=_ensure_utc(row.created_at),
    )


async def list_rep_targets(session: AsyncSession, period_type: PeriodType, period_key: str) -> list[RepTarget]:
    rows = (await session.execute(
        select(RepTargetORM).where(
            RepTargetORM.period_type == period_type.value, RepTargetORM.period_key == period_key,
        )
    )).scalars().all()
    return [_rep_target_from_row(r) for r in rows]


# ── ICPProfile ───────────────────────────────────────────────────────────────

async def save_icp_profile(session: AsyncSession, profile: ICPProfile) -> None:
    """Singleton — `profile.id` é sempre `'icp_profile'` (default do
    modelo), então salvar de novo é upsert via `_upsert`/`session.merge`,
    nunca uma 2ª linha."""
    await _upsert(session, ICPProfileORM(
        id=profile.id, reference_product_id=profile.reference_product_id,
        place_category=profile.place_category, company_size_hint=profile.company_size_hint,
        radius_km=profile.radius_km, search_origin_address=profile.search_origin_address,
        updated_at=profile.updated_at,
    ))


async def get_icp_profile(session: AsyncSession) -> ICPProfile | None:
    row = await session.get(ICPProfileORM, "icp_profile")
    if row is None:
        return None
    return ICPProfile(
        id=row.id, reference_product_id=row.reference_product_id, place_category=row.place_category,
        company_size_hint=row.company_size_hint, radius_km=row.radius_km,
        search_origin_address=row.search_origin_address, updated_at=_ensure_utc(row.updated_at),
    )


# ── FieldMapping ─────────────────────────────────────────────────────────────

async def save_field_mapping(session: AsyncSession, mapping: FieldMapping) -> None:
    """Id determinístico (`field_mapping_id`) — cadastrar mapeamento de
    novo pro mesmo (provider_id, source_field_api_name) é upsert via
    `_upsert`/`session.merge`, nunca duplicata."""
    await _upsert(session, FieldMappingORM(
        id=mapping.id, provider_id=mapping.provider_id,
        source_field_api_name=mapping.source_field_api_name,
        source_field_label=mapping.source_field_label, role=mapping.role.value,
    ))


def _field_mapping_from_row(row: FieldMappingORM) -> FieldMapping:
    return FieldMapping(
        id=row.id, provider_id=row.provider_id, source_field_api_name=row.source_field_api_name,
        source_field_label=row.source_field_label, role=SemanticFieldRole(row.role),
    )


async def list_field_mappings(session: AsyncSession, provider_id: str) -> list[FieldMapping]:
    rows = (await session.execute(
        select(FieldMappingORM).where(FieldMappingORM.provider_id == provider_id)
    )).scalars().all()
    return [_field_mapping_from_row(r) for r in rows]


async def delete_field_mapping(session: AsyncSession, mapping_id: str) -> None:
    """Desfazer um mapeamento — campo volta a ser contexto bruto pra IA
    (comportamento padrão da Fase A), sem exigir um valor "raw_context"
    explícito no enum (decisão confirmada no planejamento da Fase F)."""
    row = await session.get(FieldMappingORM, mapping_id)
    if row is not None:
        await session.delete(row)
        await session.commit()
