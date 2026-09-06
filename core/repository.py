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

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.db_models import (
    CompanyORM, CompanySignalORM, ContactORM, CorrelationRuleORM, ICPProfileORM, OpportunityORM,
    OpportunitySnapshotORM, OpportunityStatusChangeORM, PortfolioORM, ProductORM, RepTargetORM, ServiceORM,
    VendorORM,
)
from core.models import (
    Address, Company, CompanySignal, ContextNote, Contact, CorrelationRule, DismissalReason,
    DismissalReasonRequiredError, ICPProfile, Opportunity, OpportunitySnapshot,
    OpportunityStatus, OpportunityStatusChange, PeriodType, Portfolio, Product, ProductRelation, RepTarget,
    Service, SourceRef, StatusChangeRequiresJustificationError, Vendor,
)
from core.opportunity_engine import is_zombie_opportunity, requires_status_change_justification


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


# ── Product ──────────────────────────────────────────────────────────────────

async def save_product(session: AsyncSession, product: Product) -> None:
    await _upsert(session, ProductORM(
        id=product.id, vendor_id=product.vendor_id, name=product.name,
        aliases=product.aliases, description=product.description,
        status=product.status, category=product.category,
        related_services=_relations_to_json(product.related_services),
    ))


async def list_products(session: AsyncSession) -> list[Product]:
    rows = (await session.execute(select(ProductORM))).scalars().all()
    return [Product(
        id=r.id, vendor_id=r.vendor_id, name=r.name, aliases=r.aliases,
        description=r.description, status=r.status, category=r.category,
        related_services=_relations_from_json(r.related_services),
    ) for r in rows]


# ── Service ──────────────────────────────────────────────────────────────────

async def save_service(session: AsyncSession, service: Service) -> None:
    await _upsert(session, ServiceORM(
        id=service.id, name=service.name, description=service.description,
        status=service.status, category=service.category,
    ))


async def list_services(session: AsyncSession) -> list[Service]:
    rows = (await session.execute(select(ServiceORM))).scalars().all()
    return [Service(
        id=r.id, name=r.name, description=r.description, status=r.status, category=r.category,
    ) for r in rows]


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
        address=_address_from_json(row.address),
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
        address=_address_to_json(company.address),
    )
    stmt = sqlite_insert(CompanyORM).values(id=company.id, renewal_date=None, **engine_columns)
    stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=engine_columns)
    await session.execute(stmt)
    await session.commit()


async def get_company(session: AsyncSession, company_id: str) -> Company | None:
    row = await session.get(CompanyORM, company_id)
    return _company_from_row(row) if row else None


async def update_company_renewal_date(
    session: AsyncSession, company_id: str, renewal_date: datetime | None,
) -> Company | None:
    """Único caminho de escrita de renewal_date (manual, cadência de QBR) —
    só essa coluna, nunca session.merge() da linha inteira. Sem o risco de
    TOCTOU do save_opportunity original: um UPDATE de coluna única não
    reconstrói o resto da linha, não há nada pra sobrescrever."""
    row = await session.get(CompanyORM, company_id)
    if row is None:
        return None
    row.renewal_date = renewal_date
    await session.commit()
    return _company_from_row(row)


async def list_companies(session: AsyncSession) -> list[Company]:
    rows = (await session.execute(select(CompanyORM))).scalars().all()
    return [_company_from_row(r) for r in rows]


# ── Contact ──────────────────────────────────────────────────────────────────

async def save_contact(session: AsyncSession, contact: Contact) -> None:
    await _upsert(session, ContactORM(
        id=contact.id, company_id=contact.company_id, name=contact.name,
        email=contact.email, phone=contact.phone, role=contact.role,
        sources=_sources_to_json(contact.sources), impacted_area=contact.impacted_area,
        seniority_tier=contact.seniority_tier,
    ))


async def list_contacts(session: AsyncSession, company_id: str) -> list[Contact]:
    rows = (await session.execute(select(ContactORM).where(ContactORM.company_id == company_id))).scalars().all()
    return [Contact(
        id=r.id, company_id=r.company_id, name=r.name, email=r.email,
        role=r.role, phone=r.phone, sources=_sources_from_json(r.sources),
        impacted_area=r.impacted_area, seniority_tier=r.seniority_tier,
    ) for r in rows]


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
    scope_note: str | None, criticality: str | None, severity_note: str | None,
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
    row.scope_note = scope_note
    row.criticality = criticality
    row.severity_note = severity_note
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

async def save_company_signal(session: AsyncSession, signal: CompanySignal) -> None:
    await _upsert(session, CompanySignalORM(
        id=signal.id, company_id=signal.company_id, signal_type=signal.signal_type,
        evidence=signal.evidence, source=signal.source.model_dump(),
        confidence=signal.confidence, detected_at=signal.detected_at, status=signal.status,
    ))


async def list_company_signals(session: AsyncSession, company_id: str) -> list[CompanySignal]:
    rows = (await session.execute(select(CompanySignalORM).where(CompanySignalORM.company_id == company_id))).scalars().all()
    return [CompanySignal(
        id=r.id, company_id=r.company_id, signal_type=r.signal_type, evidence=r.evidence,
        source=SourceRef(**r.source), confidence=r.confidence,
        detected_at=_ensure_utc(r.detected_at), status=r.status,
    ) for r in rows]


# ── OpportunityStatusChange ──────────────────────────────────────────────────

async def save_opportunity_status_change(session: AsyncSession, change: OpportunityStatusChange) -> None:
    """Helper de teste/setup direto de fixture — NUNCA chamar a partir de
    código de aplicação para registrar uma transição real de status: o
    commit fica separado da escrita de `Opportunity.status`, reabrindo o
    TOCTOU que `update_opportunity_status` fecha ao gravar as duas coisas
    na mesma transação. Toda transição real usa `update_opportunity_status`."""
    await _upsert(session, OpportunityStatusChangeORM(
        id=change.id, opportunity_id=change.opportunity_id,
        status=change.status.value, entered_at=change.entered_at, note=change.note,
        dismissal_reason=change.dismissal_reason.value if change.dismissal_reason else None,
    ))


async def list_opportunity_status_changes(session: AsyncSession, opportunity_id: str) -> list[OpportunityStatusChange]:
    rows = (await session.execute(
        select(OpportunityStatusChangeORM).where(OpportunityStatusChangeORM.opportunity_id == opportunity_id)
    )).scalars().all()
    return [OpportunityStatusChange(
        id=r.id, opportunity_id=r.opportunity_id,
        status=OpportunityStatus(r.status), entered_at=_ensure_utc(r.entered_at), note=r.note,
        dismissal_reason=DismissalReason(r.dismissal_reason) if r.dismissal_reason else None,
    ) for r in rows]


async def update_opportunity_status(
    session: AsyncSession, opportunity_id: str, new_status: OpportunityStatus, note: str | None = None,
    dismissal_reason: DismissalReason | None = None,
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
        radius_km=profile.radius_km, updated_at=profile.updated_at,
    ))


async def get_icp_profile(session: AsyncSession) -> ICPProfile | None:
    row = await session.get(ICPProfileORM, "icp_profile")
    if row is None:
        return None
    return ICPProfile(
        id=row.id, reference_product_id=row.reference_product_id, place_category=row.place_category,
        company_size_hint=row.company_size_hint, radius_km=row.radius_km, updated_at=_ensure_utc(row.updated_at),
    )
