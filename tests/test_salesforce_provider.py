"""Smoke tests do SalesforceProvider. Nenhuma chamada de rede real:
httpx.MockTransport injeta as respostas (CLAUDE.md: providers sempre mockados em teste)."""
import asyncio
import sys
from pathlib import Path

from urllib.parse import unquote_plus as unquote

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.errors import ErrorCategory
from providers.base import DataProvider, ProviderError
from providers.salesforce import SalesforceProvider, _infer_seniority_tier

_TOKEN_BODY = {"access_token": "tok-123", "instance_url": "https://example.my.salesforce.com"}
_VALID_ACCOUNT_ID = "001XX000003DHPh"  # 15 chars, formato válido de ID do Salesforce


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _provider(handler) -> SalesforceProvider:
    return SalesforceProvider("cid", "csecret", "https://login.salesforce.com", client=_client(handler))


def test_salesforce_provider_implements_contract():
    assert issubclass(SalesforceProvider, DataProvider)


def test_missing_config_raises_configuration_error():
    try:
        SalesforceProvider("", "csecret", "https://login.salesforce.com")
        assert False, "deveria ter levantado ProviderError"
    except ProviderError as exc:
        assert exc.category == ErrorCategory.CONFIGURATION


def test_fetch_companies_authenticates_then_queries():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/services/oauth2/token":
            return httpx.Response(200, json=_TOKEN_BODY)
        assert "Bearer tok-123" == request.headers["Authorization"]
        assert "FROM Account" in unquote(str(request.url))
        return httpx.Response(200, json={
            "totalSize": 1, "done": True,
            "records": [{"Id": _VALID_ACCOUNT_ID, "Name": "Acme", "Website": "acme.com"}],
        })

    async def run():
        provider = _provider(handler)
        companies = await provider.fetch_companies()
        assert len(companies) == 1
        assert companies[0].id == _VALID_ACCOUNT_ID
        assert companies[0].name == "Acme"
        assert companies[0].website == "acme.com"
        assert companies[0].sources[0].type == "salesforce"

    asyncio.run(run())


def test_fetch_contacts_filters_by_account_id():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/services/oauth2/token":
            return httpx.Response(200, json=_TOKEN_BODY)
        assert f"AccountId = '{_VALID_ACCOUNT_ID}'" in unquote(str(request.url))
        return httpx.Response(200, json={
            "totalSize": 1, "done": True,
            "records": [{"Id": "003XX0004TQhPh", "Name": "Fulano", "Email": "f@acme.com", "Phone": None, "Title": "CTO"}],
        })

    async def run():
        provider = _provider(handler)
        contacts = await provider.fetch_contacts(_VALID_ACCOUNT_ID)
        assert len(contacts) == 1
        assert contacts[0].name == "Fulano"
        assert contacts[0].role == "CTO"

    asyncio.run(run())


def test_invalid_company_id_rejected_before_any_request():
    async def run():
        def handler(request: httpx.Request) -> httpx.Response:
            assert False, "nenhuma requisição deveria ter sido feita"
        provider = _provider(handler)
        try:
            await provider.fetch_contacts("' OR '1'='1")
            assert False, "deveria ter levantado ProviderError"
        except ProviderError as exc:
            assert exc.category == ErrorCategory.INVALID_DATA

    asyncio.run(run())


def test_invalid_credentials_raise_authentication_error_without_retry():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(401, json={"error": "invalid_client"})

    async def run():
        provider = _provider(handler)
        try:
            await provider.fetch_companies()
            assert False, "deveria ter levantado ProviderError"
        except ProviderError as exc:
            assert exc.category == ErrorCategory.AUTHENTICATION

    asyncio.run(run())
    assert calls["count"] == 1  # 401 não é transiente — nunca reautentica/repete sozinho


def test_transient_error_retries_then_succeeds():
    state = {"query_attempts": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/services/oauth2/token":
            return httpx.Response(200, json=_TOKEN_BODY)
        state["query_attempts"] += 1
        if state["query_attempts"] == 1:
            return httpx.Response(503, json={"error": "unavailable"})
        return httpx.Response(200, json={"totalSize": 0, "done": True, "records": []})

    async def run():
        provider = _provider(handler)
        companies = await provider.fetch_companies()
        assert companies == []

    asyncio.run(run())
    assert state["query_attempts"] == 2


def test_token_reused_across_multiple_calls():
    calls = {"token": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/services/oauth2/token":
            calls["token"] += 1
            return httpx.Response(200, json=_TOKEN_BODY)
        return httpx.Response(200, json={"totalSize": 0, "done": True, "records": []})

    async def run():
        provider = _provider(handler)
        await provider.fetch_companies()
        await provider.fetch_companies()

    asyncio.run(run())
    assert calls["token"] == 1  # segunda chamada reusa o token já obtido


def test_malformed_token_response_raises_friendly_integration_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})  # 200 mas sem access_token/instance_url

    async def run():
        provider = _provider(handler)
        try:
            await provider.fetch_companies()
            assert False, "deveria ter levantado ProviderError"
        except ProviderError as exc:
            assert exc.category == ErrorCategory.INTEGRATION

    asyncio.run(run())


def test_transient_error_after_retries_exhausted_maps_to_connectivity_not_authentication():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/services/oauth2/token":
            return httpx.Response(200, json=_TOKEN_BODY)
        return httpx.Response(503, json={"error": "unavailable"})  # sempre indisponível

    async def run():
        provider = _provider(handler)
        try:
            await provider.fetch_companies()
            assert False, "deveria ter levantado ProviderError"
        except ProviderError as exc:
            assert exc.category == ErrorCategory.CONNECTIVITY

    asyncio.run(run())


def test_expired_session_reauthenticates_once_then_succeeds():
    calls = {"token": 0, "query": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/services/oauth2/token":
            calls["token"] += 1
            return httpx.Response(200, json=_TOKEN_BODY)
        calls["query"] += 1
        if calls["query"] == 1:
            return httpx.Response(401, json={"error": "session_expired"})
        return httpx.Response(200, json={"totalSize": 0, "done": True, "records": []})

    async def run():
        provider = _provider(handler)
        companies = await provider.fetch_companies()
        assert companies == []

    asyncio.run(run())
    assert calls["token"] == 2  # autenticação inicial + reautenticação após 401
    assert calls["query"] == 2


def test_expired_session_reauth_still_failing_raises_authentication_once():
    calls = {"token": 0, "query": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/services/oauth2/token":
            calls["token"] += 1
            return httpx.Response(200, json=_TOKEN_BODY)
        calls["query"] += 1
        return httpx.Response(401, json={"error": "session_expired"})  # continua 401 mesmo após reauth

    async def run():
        provider = _provider(handler)
        try:
            await provider.fetch_companies()
            assert False, "deveria ter levantado ProviderError"
        except ProviderError as exc:
            assert exc.category == ErrorCategory.AUTHENTICATION

    asyncio.run(run())
    assert calls["query"] == 2  # tenta de novo só uma vez após reautenticar, nunca em loop


def test_pagination_follows_next_records_url():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/services/oauth2/token":
            return httpx.Response(200, json=_TOKEN_BODY)
        if request.url.path == "/services/data/v59.0/query":
            return httpx.Response(200, json={
                "totalSize": 2, "done": False,
                "records": [{"Id": "001XX000003DHP1", "Name": "Empresa 1", "Website": None}],
                "nextRecordsUrl": "/services/data/v59.0/query/01gXX-2000",
            })
        return httpx.Response(200, json={
            "totalSize": 2, "done": True,
            "records": [{"Id": "001XX000003DHP2", "Name": "Empresa 2", "Website": None}],
        })

    async def run():
        provider = _provider(handler)
        companies = await provider.fetch_companies()
        assert [c.name for c in companies] == ["Empresa 1", "Empresa 2"]

    asyncio.run(run())


def test_fetch_companies_maps_last_activity_date():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/services/oauth2/token":
            return httpx.Response(200, json=_TOKEN_BODY)
        assert "LastActivityDate" in unquote(str(request.url))
        return httpx.Response(200, json={
            "totalSize": 1, "done": True,
            "records": [{"Id": _VALID_ACCOUNT_ID, "Name": "Acme", "Website": None, "LastActivityDate": "2026-08-01"}],
        })

    async def run():
        provider = _provider(handler)
        companies = await provider.fetch_companies()
        assert companies[0].last_activity_at is not None
        assert companies[0].last_activity_at.year == 2026
        assert companies[0].last_activity_at.month == 8

    asyncio.run(run())


def test_fetch_companies_without_last_activity_date_leaves_it_none():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/services/oauth2/token":
            return httpx.Response(200, json=_TOKEN_BODY)
        return httpx.Response(200, json={
            "totalSize": 1, "done": True,
            "records": [{"Id": _VALID_ACCOUNT_ID, "Name": "Acme", "Website": None, "LastActivityDate": None}],
        })

    async def run():
        provider = _provider(handler)
        companies = await provider.fetch_companies()
        assert companies[0].last_activity_at is None

    asyncio.run(run())


def test_fetch_contacts_infers_seniority_tier_from_title():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/services/oauth2/token":
            return httpx.Response(200, json=_TOKEN_BODY)
        return httpx.Response(200, json={
            "totalSize": 1, "done": True,
            "records": [{"Id": "003XX0004TQhPh", "Name": "Fulano", "Email": None, "Phone": None, "Title": "Diretor de TI"}],
        })

    async def run():
        provider = _provider(handler)
        contacts = await provider.fetch_contacts(_VALID_ACCOUNT_ID)
        assert contacts[0].seniority_tier == "decisor"

    asyncio.run(run())


def test_infer_seniority_tier_covers_each_category_and_defaults_to_none():
    assert _infer_seniority_tier("Gerente de Infraestrutura") == "decisor"
    assert _infer_seniority_tier("Arquiteto de Soluções") == "influenciador_tecnico"
    assert _infer_seniority_tier("Analista de Suporte") == "operacional"
    assert _infer_seniority_tier("Estagiário de Marketing") is None
    assert _infer_seniority_tier(None) is None
    assert _infer_seniority_tier("") is None


def test_connection_ok_when_authentication_succeeds():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_TOKEN_BODY)

    async def run():
        provider = _provider(handler)
        result = await provider.test_connection()
        assert result.is_connected is True

    asyncio.run(run())


def test_connection_fails_with_friendly_message_on_bad_credentials():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid_client"})

    async def run():
        provider = _provider(handler)
        result = await provider.test_connection()
        assert result.is_connected is False
        assert "Credenciais" in result.message

    asyncio.run(run())


if __name__ == "__main__":
    test_salesforce_provider_implements_contract()
    test_missing_config_raises_configuration_error()
    test_fetch_companies_authenticates_then_queries()
    test_fetch_contacts_filters_by_account_id()
    test_invalid_company_id_rejected_before_any_request()
    test_invalid_credentials_raise_authentication_error_without_retry()
    test_transient_error_retries_then_succeeds()
    test_malformed_token_response_raises_friendly_integration_error()
    test_token_reused_across_multiple_calls()
    test_transient_error_after_retries_exhausted_maps_to_connectivity_not_authentication()
    test_expired_session_reauthenticates_once_then_succeeds()
    test_expired_session_reauth_still_failing_raises_authentication_once()
    test_pagination_follows_next_records_url()
    test_fetch_companies_maps_last_activity_date()
    test_fetch_companies_without_last_activity_date_leaves_it_none()
    test_fetch_contacts_infers_seniority_tier_from_title()
    test_infer_seniority_tier_covers_each_category_and_defaults_to_none()
    test_connection_ok_when_authentication_succeeds()
    test_connection_fails_with_friendly_message_on_bad_credentials()
    print("OK — todos os testes do provider Salesforce passaram")
