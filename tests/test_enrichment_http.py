"""Fase Q — provider de enriquecimento por API HTTP JSON configurável. API sempre mockada, só empresas fictícias."""
import asyncio
import logging
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.errors import ErrorCategory  # noqa: E402
from providers.base import ProviderError  # noqa: E402
from providers.enrichment_http import EnrichmentHttpProvider, eligible_domain, parse_employees, parse_industry  # noqa: E402

TEMPLATE = "https://api.exemplo.com/v1/companies?domain={domain}"
KEY = "chave-super-secreta-123"
JSON = {"content-type": "application/json"}


def _provider(handler, template=TEMPLATE, **kw):
    seen: list[httpx.Request] = []

    def wrapped(request):
        seen.append(request)
        return handler(request)

    async def resolver(host, port):
        return ["93.184.216.34"]

    client = httpx.AsyncClient(transport=httpx.MockTransport(wrapped), follow_redirects=False)
    args = dict(auth_header="X-Api-Key", api_key=KEY, map_employees="metrics.employees", map_industry="category.industry")
    args.update(kw)
    return EnrichmentHttpProvider(template, client=client, resolver=resolver, retry_wait=0, **args), seen


def _ok(body):
    return lambda request: httpx.Response(200, headers=JSON, json=body)


def _enrich(provider, site="https://www.acme-teste.com.br/inicio"):
    return asyncio.run(provider.enrich(site))


def test_reads_dotted_paths_and_discards_every_other_field():
    provider, seen = _provider(_ok({
        "metrics": {"employees": 120, "revenue": 5_000_000}, "category": {"industry": "  Logística  "},
        "emails": ["a@acme.com"], "name": "Acme",
    }))
    found = _enrich(provider)
    assert found.industry == "Logística" and found.employee_count == 120
    assert found.annual_revenue is None and found.legal_name is None and found.sources == []
    assert seen[0].url.params["domain"] == "acme-teste.com.br"  # domínio nu: sem www, protocolo e path


def test_type_conversion_range_numeric_string_and_invalid_values():
    assert parse_employees("120") == 120 and parse_employees(120.0) == 120
    for bad in ("51-200", "11 a 50", 0, -3, True, 120.5, None, "abc", "", [10], 10**9):
        assert parse_employees(bad) is None
    assert parse_industry(" Software   e  Serviços ") == "Software e Serviços"
    assert len(parse_industry("x" * 500)) == 100
    assert parse_industry("=HYPERLINK(1)") is None and parse_industry("@x") is None
    for bad in (None, 5, "", "   ", "<script>alert(1)</script>", "a\x00b"):
        assert parse_industry(bad) is None


def test_missing_path_in_json_is_empty_not_error():
    found = _enrich(_provider(_ok({"outro": 1}))[0])
    assert found.industry is None and found.employee_count is None


def test_strange_domain_is_refused_without_calling_the_api():
    provider, seen = _provider(_ok({}))
    for site in ("http://127.0.0.1/x", "https://localhost", "x" * 300, "https://[::1]", "", None, "https://a b.com"):
        assert _enrich(provider, site) is None
    assert seen == []
    for strange in ("acme.com.br&admin=1", "https://127.0.0.1", "https://localhost", "a_b.com"):
        assert eligible_domain(strange) is None
    assert eligible_domain("https://www.Acme.com.br/x") == "acme.com.br"


def test_domain_is_url_encoded_in_the_template():
    provider, seen = _provider(_ok({}))
    assert _enrich(provider, "acme.com.br") is not None
    assert seen[0].url.query == b"domain=acme.com.br"


def test_generic_platform_domains_are_skipped_without_calling_the_api():
    provider, seen = _provider(_ok({}))
    assert _enrich(provider, "https://www.facebook.com/acme") is None
    assert _enrich(provider, "https://pagina.wixsite.com/acme") is None
    assert seen == []


def test_key_goes_only_in_header_never_in_url():
    provider, seen = _provider(_ok({"metrics": {"employees": 5}}))
    _enrich(provider)
    assert seen[0].headers["x-api-key"] == KEY and KEY not in str(seen[0].url)


def test_key_requires_https_and_valid_header_and_template():
    with pytest.raises(ProviderError):
        EnrichmentHttpProvider("http://api.exemplo.com/?d={domain}", "X-Api-Key", KEY, "a", "")
    with pytest.raises(ProviderError):
        EnrichmentHttpProvider(TEMPLATE, "Host", KEY, "a", "")
    with pytest.raises(ProviderError):
        EnrichmentHttpProvider(TEMPLATE, "X\r\nEvil", KEY, "a", "")
    for template in ("", "https://api.exemplo.com/sem-dominio", "https://{domain}/x", "https://a.com/{domain}/{domain}", "ftp://a.com/{domain}"):
        with pytest.raises(ProviderError):
            EnrichmentHttpProvider(template, "", "", "a", "")
    with pytest.raises(ProviderError):
        EnrichmentHttpProvider(TEMPLATE, "", "", "", "")  # sem nenhum caminho
    with pytest.raises(ProviderError):
        EnrichmentHttpProvider(TEMPLATE, "", "", "metrics..x; drop", "")


def test_401_and_403_raise_authentication_error_without_retry_or_key():
    for status in (401, 403):
        provider, seen = _provider(lambda r, s=status: httpx.Response(s, headers=JSON, json={"erro": "x"}))
        with pytest.raises(ProviderError) as exc:
            _enrich(provider)
        assert exc.value.category == ErrorCategory.AUTHENTICATION and KEY not in str(exc.value) and len(seen) == 1


def test_429_and_5xx_retry_exactly_once_then_friendly_error():
    for status in (429, 503):
        provider, seen = _provider(lambda r, s=status: httpx.Response(s, headers=JSON, json={}))
        with pytest.raises(ProviderError) as exc:
            _enrich(provider)
        assert len(seen) == 2 and "HTTPStatusError" not in str(exc.value)


def test_429_then_success_recovers():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429, headers=JSON, json={}) if len(calls) == 1 else httpx.Response(200, headers=JSON, json={"metrics": {"employees": 7}})
    assert _enrich(_provider(handler)[0]).employee_count == 7 and len(calls) == 2


def test_404_means_no_data_and_other_4xx_is_a_friendly_error_without_retry():
    provider, seen = _provider(lambda r: httpx.Response(404, headers=JSON, json={}))
    assert _enrich(provider) is None and len(seen) == 1
    provider, seen = _provider(lambda r: httpx.Response(400, headers=JSON, json={}))
    with pytest.raises(ProviderError):
        _enrich(provider)
    assert len(seen) == 1


def test_timeout_and_network_failure_become_friendly_error_after_one_retry():
    def boom(request):
        raise httpx.ReadTimeout("lento", request=request)
    provider, seen = _provider(boom)
    with pytest.raises(ProviderError) as exc:
        _enrich(provider)
    assert exc.value.category == ErrorCategory.TIMEOUT and "Timeout" not in str(exc.value) and len(seen) == 2


def test_non_json_oversized_and_invalid_json_are_friendly_errors():
    for response in (
        httpx.Response(200, headers={"content-type": "text/html"}, text="<html>"),
        httpx.Response(200, headers=JSON, text="{não é json"),
        httpx.Response(200, headers=JSON, content=b"{" + b" " * 300_000 + b"}"),
    ):
        provider, _ = _provider(lambda r, resp=response: resp)
        with pytest.raises(ProviderError) as exc:
            _enrich(provider)
        assert exc.value.category == ErrorCategory.INVALID_DATA


def test_redirect_to_another_host_is_refused_and_key_is_not_sent_there():
    provider, seen = _provider(lambda r: httpx.Response(302, headers={"location": "https://coletor.malvado.com/x"}))
    with pytest.raises(ProviderError):
        _enrich(provider)
    assert [r.headers.get("host") for r in seen] == ["api.exemplo.com"]


def test_test_connection_shows_values_read_and_never_the_key():
    provider, _ = _provider(_ok({"metrics": {"employees": 42}, "category": {"industry": "Varejo"}}))
    result = asyncio.run(provider.test_connection())
    assert result.is_connected and "Varejo" in result.message and "42" in result.message and KEY not in result.message
    provider, _ = _provider(lambda r: httpx.Response(401, headers=JSON, json={}))
    result = asyncio.run(provider.test_connection())
    assert not result.is_connected and KEY not in result.message


def test_key_never_appears_in_logs(caplog):
    caplog.set_level(logging.DEBUG)
    for status in (401, 429, 500, 400):
        provider, _ = _provider(lambda r, s=status: httpx.Response(s, headers=JSON, json={}))
        with pytest.raises(ProviderError):
            _enrich(provider)
    assert KEY not in caplog.text


def test_provider_does_not_take_part_in_sync():
    provider, _ = _provider(_ok({}))
    assert provider.id == "enrichment" and asyncio.run(provider.fetch_companies()) == [] and asyncio.run(provider.fetch_contacts("x")) == []
