"""Smoke tests do CRUD e merge de portfólio."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import Portfolio
from core.portfolio import add_product, add_service, merge_portfolio, remove_product, remove_service


def test_add_and_remove_product_dedup():
    pf = Portfolio(company_id="c1")
    pf = add_product(pf, "p1")
    pf = add_product(pf, "p1")  # duplicado, não deve repetir
    assert pf.product_ids == ["p1"]

    pf = remove_product(pf, "p1")
    assert pf.product_ids == []


def test_add_and_remove_service():
    pf = Portfolio(company_id="c1")
    pf = add_service(pf, "s1")
    assert pf.service_ids == ["s1"]
    pf = remove_service(pf, "s1")
    assert pf.service_ids == []


def test_merge_first_sync_returns_candidate():
    candidate = Portfolio(company_id="c1", product_ids=["p1"])
    result = merge_portfolio(None, candidate, mode="add")
    assert result == candidate


def test_merge_add_mode_preserves_existing_and_appends_new():
    existing = Portfolio(company_id="c1", product_ids=["p1"], notes="nota antiga")
    candidate = Portfolio(company_id="c1", product_ids=["p1", "p2"])

    result = merge_portfolio(existing, candidate, mode="add")

    assert result.product_ids == ["p1", "p2"]
    assert result.notes == "nota antiga"  # candidate sem notes não apaga a existente


def test_merge_overwrite_mode_replaces_content():
    existing = Portfolio(company_id="c1", product_ids=["p1"], notes="nota antiga")
    candidate = Portfolio(company_id="c1", product_ids=["p2"], notes="nota nova")

    result = merge_portfolio(existing, candidate, mode="overwrite")

    assert result.product_ids == ["p2"]
    assert result.notes == "nota nova"
    assert result.company_id == "c1"


def test_merge_never_silently_drops_data_without_explicit_mode():
    existing = Portfolio(company_id="c1", product_ids=["p1"])
    candidate = Portfolio(company_id="c1", product_ids=["p2"])

    add_result = merge_portfolio(existing, candidate, mode="add")
    assert "p1" in add_result.product_ids  # modo add nunca perde dado existente


if __name__ == "__main__":
    test_add_and_remove_product_dedup()
    test_add_and_remove_service()
    test_merge_first_sync_returns_candidate()
    test_merge_add_mode_preserves_existing_and_appends_new()
    test_merge_overwrite_mode_replaces_content()
    test_merge_never_silently_drops_data_without_explicit_mode()
    print("OK — todos os testes de portfólio passaram")
