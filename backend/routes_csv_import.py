"""
Importação de empresas + portfólio via CSV — fecha o gap encontrado em teste
manual: sem Salesforce/Google Maps configurados, não havia nenhuma forma de
colocar dado real no sistema em lote (Manual é só um stub de arquitetura,
sem persistência). Reaproveita a mesma dedup/merge de empresa do sync
(core/normalization.py) e o mesmo motor de regras
(backend.sync.evaluate_rules_for_synced_companies) — nunca um pipeline
paralelo. Nunca inventa vendor/produto/serviço: nomes que não batem com o
catálogo já cadastrado viram erro reportado, a linha é ignorada.

Formato esperado (cabeçalho obrigatório: company_name):
  company_name,is_customer,segment,region,rep_id,vendor,product,service

Uma linha por empresa + item de portfólio (vendor+product juntos, OU service
sozinho, OU nenhum dos dois se a linha só carrega metadado da empresa).
Metadados da empresa (is_customer/segment/region/rep_id) são lidos só da
primeira linha de cada empresa — repetir nas linhas seguintes é ignorado,
nunca sobrescreve.
"""
from __future__ import annotations

import csv
import io
from typing import Literal

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from backend.db_session import session_factory
from backend.http_errors import raise_http
from backend.sync import evaluate_rules_for_synced_companies
from core.errors import DomainError, ErrorCategory
from core.models import Company, Portfolio
from core.normalization import dedup_key, merge_pair
from core.repository import (
    get_portfolio_by_company, list_companies, list_products, list_services, list_vendors, save_company,
    save_portfolio,
)

router = APIRouter()

_REQUIRED_COLUMNS = {"company_name"}


class CsvImportResult(BaseModel):
    companies_imported: int
    portfolios_updated: int
    opportunities_generated: int
    errors: list[str]


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "sim", "yes"}


@router.post("/csv-import")
async def import_csv(
    file: UploadFile = File(...), mode: Literal["merge", "replace"] = Form("merge"),
) -> CsvImportResult:
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise_http(DomainError(ErrorCategory.INVALID_DATA, "Arquivo não parece ser um CSV em UTF-8 válido."))

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or not _REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):
        raise_http(DomainError(
            ErrorCategory.INVALID_DATA,
            "CSV precisa ter pelo menos a coluna 'company_name'. Colunas opcionais: "
            "is_customer, segment, region, rep_id, vendor, product, service.",
        ))
    rows = list(reader)

    async with session_factory() as session:
        vendor_by_name = {v.name.strip().lower(): v.id for v in await list_vendors(session)}
        product_by_name = {p.name.strip().lower(): p.id for p in await list_products(session)}
        service_by_name = {s.name.strip().lower(): s.id for s in await list_services(session)}
        existing_by_key = {dedup_key(c): c for c in await list_companies(session)}

    errors: list[str] = []
    companies_by_name: dict[str, Company] = {}
    vendor_ids_by_company: dict[str, set[str]] = {}
    product_ids_by_company: dict[str, set[str]] = {}
    service_ids_by_company: dict[str, set[str]] = {}

    for i, row in enumerate(rows, start=2):  # linha 1 é o cabeçalho
        name = (row.get("company_name") or "").strip()
        if not name:
            errors.append(f"Linha {i}: company_name em branco — ignorada.")
            continue

        if name not in companies_by_name:
            new_company = Company(
                name=name,
                is_customer=_parse_bool(row.get("is_customer") or ""),
                segment=(row.get("segment") or "").strip() or None,
                region=(row.get("region") or "").strip() or None,
                rep_id=(row.get("rep_id") or "").strip() or None,
            )
            existing = existing_by_key.get(dedup_key(new_company))
            companies_by_name[name] = merge_pair(existing, new_company) if existing else new_company
            vendor_ids_by_company[name] = set()
            product_ids_by_company[name] = set()
            service_ids_by_company[name] = set()

        vendor_name = (row.get("vendor") or "").strip()
        if vendor_name:
            vendor_id = vendor_by_name.get(vendor_name.lower())
            if vendor_id is None:
                errors.append(f"Linha {i}: fabricante '{vendor_name}' não encontrado no portfólio — cadastre antes de importar.")
            else:
                vendor_ids_by_company[name].add(vendor_id)

        product_name = (row.get("product") or "").strip()
        if product_name:
            product_id = product_by_name.get(product_name.lower())
            if product_id is None:
                errors.append(f"Linha {i}: produto '{product_name}' não encontrado no portfólio — cadastre antes de importar.")
            else:
                product_ids_by_company[name].add(product_id)

        service_name = (row.get("service") or "").strip()
        if service_name:
            service_id = service_by_name.get(service_name.lower())
            if service_id is None:
                errors.append(f"Linha {i}: serviço '{service_name}' não encontrado no portfólio — cadastre antes de importar.")
            else:
                service_ids_by_company[name].add(service_id)

    async with session_factory() as session:
        for company in companies_by_name.values():
            await save_company(session, company)

    portfolios_updated = 0
    async with session_factory() as session:
        for name, company in companies_by_name.items():
            new_vendor_ids = vendor_ids_by_company[name]
            new_product_ids = product_ids_by_company[name]
            new_service_ids = service_ids_by_company[name]
            if not (new_vendor_ids or new_product_ids or new_service_ids):
                continue

            existing_portfolio = await get_portfolio_by_company(session, company.id)
            if existing_portfolio is not None:
                if mode == "merge":
                    vendor_ids = sorted(set(existing_portfolio.vendor_ids) | new_vendor_ids)
                    product_ids = sorted(set(existing_portfolio.product_ids) | new_product_ids)
                    service_ids = sorted(set(existing_portfolio.service_ids) | new_service_ids)
                else:
                    vendor_ids, product_ids, service_ids = (
                        sorted(new_vendor_ids), sorted(new_product_ids), sorted(new_service_ids),
                    )
                portfolio = existing_portfolio.model_copy(update={
                    "vendor_ids": vendor_ids, "product_ids": product_ids, "service_ids": service_ids,
                })
            else:
                portfolio = Portfolio(
                    company_id=company.id, vendor_ids=sorted(new_vendor_ids),
                    product_ids=sorted(new_product_ids), service_ids=sorted(new_service_ids),
                )
            await save_portfolio(session, portfolio)
            portfolios_updated += 1

    opportunities_generated = await evaluate_rules_for_synced_companies(session_factory, companies_by_name.values())

    return CsvImportResult(
        companies_imported=len(companies_by_name), portfolios_updated=portfolios_updated,
        opportunities_generated=opportunities_generated, errors=errors,
    )
