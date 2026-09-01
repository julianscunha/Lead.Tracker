"""Tabelas SQLAlchemy — espelham core/models.py. Listas/dicts
(sources, evidence, aliases, relations) viram JSON — SQLite/SQLAlchemy serializa
automaticamente, sem precisar de tabela associativa pra isso aqui."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class VendorORM(Base):
    __tablename__ = "vendors"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)


class ProductORM(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    vendor_id: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    related_service_ids: Mapped[list] = mapped_column(JSON, default=list)


class ServiceORM(Base):
    __tablename__ = "services"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)


class CompanyORM(Base):
    __tablename__ = "companies"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    legal_name: Mapped[str | None] = mapped_column(String, nullable=True)
    website: Mapped[str | None] = mapped_column(String, nullable=True)
    is_customer: Mapped[bool] = mapped_column(Boolean, default=False)
    customer_status: Mapped[str | None] = mapped_column(String, nullable=True)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column()


class ContactORM(Base):
    __tablename__ = "contacts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str | None] = mapped_column(String, nullable=True)
    sources: Mapped[list] = mapped_column(JSON, default=list)


class OpportunityORM(Base):
    __tablename__ = "opportunities"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    vendor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    product_id: Mapped[str | None] = mapped_column(String, nullable=True)
    service_id: Mapped[str | None] = mapped_column(String, nullable=True)
    opportunity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    financial_potential: Mapped[float | None] = mapped_column(Float, nullable=True)
    strategic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    justification: Mapped[str | None] = mapped_column(String, nullable=True)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String)


class PortfolioORM(Base):
    __tablename__ = "portfolios"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(String, unique=True)
    vendor_ids: Mapped[list] = mapped_column(JSON, default=list)
    product_ids: Mapped[list] = mapped_column(JSON, default=list)
    service_ids: Mapped[list] = mapped_column(JSON, default=list)
    relations: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column()
