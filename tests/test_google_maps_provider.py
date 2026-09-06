"""Smoke tests do GoogleMapsProvider (Fase E, módulo 2 `places-signal-collector`).
httpx.MockTransport injeta as respostas (CLAUDE.md: providers sempre mockados em teste)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

from core.errors import ErrorCategory
from providers.base import DataProvider, ProviderError
from providers.google_maps import GoogleMapsProvider

_GEOCODE_OK_BODY = {
    "status": "OK",
    "results": [{"geometry": {"location": {"lat": 37.4224, "lng": -122.0842}}}],
}


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _provider(handler) -> GoogleMapsProvider:
    return GoogleMapsProvider("fake-key", client=_client(handler))


def test_google_maps_provider_implements_contract():
    assert issubclass(GoogleMapsProvider, DataProvider)


def test_missing_api_key_raises_configuration_error():
    try:
        GoogleMapsProvider("")
        assert False, "deveria ter levantado ProviderError"
    except ProviderError as exc:
        assert exc.category == ErrorCategory.CONFIGURATION


def test_fetch_companies_always_returns_empty_never_calls_network():
    """Não participa do /sync periódico — retornar [] é o comportamento
    correto, não uma lacuna (ver docstring do módulo)."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert False, "nenhuma requisição deveria ter sido feita"

    async def run():
        provider = _provider(handler)
        assert await provider.fetch_companies() == []
        assert await provider.fetch_contacts("qualquer") == []

    asyncio.run(run())


def test_connection_ok_when_geocode_succeeds():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_GEOCODE_OK_BODY)

    async def run():
        provider = _provider(handler)
        result = await provider.test_connection()
        assert result.is_connected is True

    asyncio.run(run())


def test_connection_fails_friendly_on_invalid_key():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "REQUEST_DENIED"})

    async def run():
        provider = _provider(handler)
        result = await provider.test_connection()
        assert result.is_connected is False
        assert "inválida" in result.message

    asyncio.run(run())


def test_discover_rejects_radius_above_50km_without_network_call():
    def handler(request: httpx.Request) -> httpx.Response:
        assert False, "nenhuma requisição deveria ter sido feita"

    async def run():
        provider = _provider(handler)
        try:
            await provider.discover("Av. Paulista, São Paulo", 51.0, "car_dealer")
            assert False, "deveria ter levantado ProviderError"
        except ProviderError as exc:
            assert exc.category == ErrorCategory.INVALID_DATA

    asyncio.run(run())


def test_discover_rejects_zero_or_negative_radius():
    def handler(request: httpx.Request) -> httpx.Response:
        assert False, "nenhuma requisição deveria ter sido feita"

    async def run():
        provider = _provider(handler)
        try:
            await provider.discover("Av. Paulista, São Paulo", 0, "car_dealer")
            assert False, "deveria ter levantado ProviderError"
        except ProviderError as exc:
            assert exc.category == ErrorCategory.INVALID_DATA

    asyncio.run(run())


def test_discover_geocodes_origin_then_searches_nearby_and_normalizes_signals():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if "geocode" in str(request.url):
            assert "Av. Paulista" in str(request.url) or "Paulista" in request.url.query.decode()
            return httpx.Response(200, json=_GEOCODE_OK_BODY)
        assert request.url.path == "/v1/places:searchNearby"
        assert request.headers["X-Goog-Api-Key"] == "fake-key"
        body = request.read()
        import json
        payload = json.loads(body)
        assert payload["locationRestriction"]["circle"]["radius"] == 5000.0
        assert payload["includedTypes"] == ["car_dealer"]
        return httpx.Response(200, json={
            "places": [{
                "id": "place-1", "displayName": {"text": "Concessionária Exemplo"},
                "types": ["car_dealer", "point_of_interest"], "businessStatus": "OPERATIONAL",
                "rating": 4.5, "userRatingCount": 120, "formattedAddress": "Rua Exemplo, 123",
            }],
        })

    async def run():
        provider = _provider(handler)
        signals = await provider.discover("Av. Paulista, São Paulo", 5.0, "car_dealer")
        assert len(signals) == 1
        s = signals[0]
        assert s.place_id == "place-1"
        assert s.name == "Concessionária Exemplo"
        assert s.category == "car_dealer"
        assert s.business_status == "OPERATIONAL"
        assert s.rating == 4.5
        assert s.review_count == 120
        assert s.formatted_address == "Rua Exemplo, 123"

    asyncio.run(run())
    assert calls["count"] == 2


def test_discover_without_category_omits_included_types():
    def handler(request: httpx.Request) -> httpx.Response:
        if "geocode" in str(request.url):
            return httpx.Response(200, json=_GEOCODE_OK_BODY)
        import json
        payload = json.loads(request.read())
        assert "includedTypes" not in payload
        return httpx.Response(200, json={"places": []})

    async def run():
        provider = _provider(handler)
        signals = await provider.discover("Av. Paulista, São Paulo", 5.0, None)
        assert signals == []

    asyncio.run(run())


def test_geocode_zero_results_raises_invalid_data():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ZERO_RESULTS"})

    async def run():
        provider = _provider(handler)
        try:
            await provider.discover("endereço que não existe", 5.0, None)
            assert False, "deveria ter levantado ProviderError"
        except ProviderError as exc:
            assert exc.category == ErrorCategory.INVALID_DATA

    asyncio.run(run())


def test_geocode_persistent_transient_error_retries_once_then_connectivity():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(503)

    async def run():
        provider = _provider(handler)
        try:
            await provider.discover("Av. Paulista, São Paulo", 5.0, None)
            assert False, "deveria ter levantado ProviderError"
        except ProviderError as exc:
            assert exc.category == ErrorCategory.CONNECTIVITY

    asyncio.run(run())
    assert calls["count"] == 2  # 1 tentativa original + 1 retry, nunca mais


def test_search_nearby_persistent_transient_error_retries_once_then_connectivity():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "geocode" in str(request.url):
            return httpx.Response(200, json=_GEOCODE_OK_BODY)
        calls["count"] += 1
        return httpx.Response(503)

    async def run():
        provider = _provider(handler)
        try:
            await provider.discover("Av. Paulista, São Paulo", 5.0, "car_dealer")
            assert False, "deveria ter levantado ProviderError"
        except ProviderError as exc:
            assert exc.category == ErrorCategory.CONNECTIVITY

    asyncio.run(run())
    assert calls["count"] == 2


def test_geocode_ok_status_with_empty_results_raises_friendly_integration_error():
    """Resposta com status "OK" mas formato inesperado (results vazio)
    nunca pode vazar IndexError cru — discover() é chamado direto pelo
    wizard, sem try/except genérico entre ele e o usuário."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "OK", "results": []})

    async def run():
        provider = _provider(handler)
        try:
            await provider.discover("Av. Paulista, São Paulo", 5.0, None)
            assert False, "deveria ter levantado ProviderError"
        except ProviderError as exc:
            assert exc.category == ErrorCategory.INTEGRATION

    asyncio.run(run())


def test_search_nearby_place_without_id_raises_friendly_integration_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if "geocode" in str(request.url):
            return httpx.Response(200, json=_GEOCODE_OK_BODY)
        return httpx.Response(200, json={"places": [{"displayName": {"text": "Sem id"}}]})

    async def run():
        provider = _provider(handler)
        try:
            await provider.discover("Av. Paulista, São Paulo", 5.0, None)
            assert False, "deveria ter levantado ProviderError"
        except ProviderError as exc:
            assert exc.category == ErrorCategory.INTEGRATION

    asyncio.run(run())


def test_search_nearby_403_raises_authentication_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if "geocode" in str(request.url):
            return httpx.Response(200, json=_GEOCODE_OK_BODY)
        return httpx.Response(403, json={"error": {"message": "forbidden"}})

    async def run():
        provider = _provider(handler)
        try:
            await provider.discover("Av. Paulista, São Paulo", 5.0, "car_dealer")
            assert False, "deveria ter levantado ProviderError"
        except ProviderError as exc:
            assert exc.category == ErrorCategory.AUTHENTICATION

    asyncio.run(run())


if __name__ == "__main__":
    test_google_maps_provider_implements_contract()
    test_missing_api_key_raises_configuration_error()
    test_fetch_companies_always_returns_empty_never_calls_network()
    test_connection_ok_when_geocode_succeeds()
    test_connection_fails_friendly_on_invalid_key()
    test_discover_rejects_radius_above_50km_without_network_call()
    test_discover_rejects_zero_or_negative_radius()
    test_discover_geocodes_origin_then_searches_nearby_and_normalizes_signals()
    test_discover_without_category_omits_included_types()
    test_geocode_zero_results_raises_invalid_data()
    test_geocode_persistent_transient_error_retries_once_then_connectivity()
    test_search_nearby_persistent_transient_error_retries_once_then_connectivity()
    test_geocode_ok_status_with_empty_results_raises_friendly_integration_error()
    test_search_nearby_place_without_id_raises_friendly_integration_error()
    test_search_nearby_403_raises_authentication_error()
    print("OK — todos os testes do provider Google Maps passaram")
