"""
GoogleMapsProvider — prospecção geográfica (Fase E, módulo 2
`places-signal-collector`).

Geocoding API (endereço → lat/lng):
https://developers.google.com/maps/documentation/geocoding/requests-geocoding
Places API (New), Nearby Search (POST /v1/places:searchNearby):
https://developers.google.com/maps/documentation/places/web-service/nearby-search

Coleta e normaliza sinal bruto — NUNCA decide oportunidade nem pontua
(isso é `geo-scoring-rules`, módulo 4, que ainda não existe nesta fatia).
`business_status`/`rating`/`user_ratings_total` são passados adiante
como vieram da API, sem interpretação.

Diferente de Salesforce/Website: não participa do laço de `/sync`
periódico (`fetch_companies()` devolve `[]` de propósito — não existe
"lista de empresas conhecidas" pra Maps, só busca sob demanda por
critério de ICP). A descoberta de verdade é `discover()`, chamada pelo
wizard (módulo 6, ainda não construído) com os critérios já configurados
em `icp-profile-store` (módulo 1).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

from core.errors import ErrorCategory
from core.models import Company, Contact
from providers.base import ConnectionTestResult, DataProvider, ProviderContext, ProviderError

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_TRANSIENT_STATUS = {429, 500, 502, 503, 504}
_MAX_RADIUS_KM = 50.0  # limite físico da Places API (New) — 50000m


@dataclass
class PlaceSignal:
    """Sinal bruto de um lugar do Google Places — nunca pontuado aqui.
    `business_status`/`category`/`rating`/`review_count` alimentam
    `geo-scoring-rules` (módulo 4), em camadas (categoria > OPERATIONAL >
    reviews como proxy fraco), nunca decidem sozinhos."""
    place_id: str
    name: str
    category: str | None
    business_status: str | None
    rating: float | None
    review_count: int
    formatted_address: str | None


class GoogleMapsProvider(DataProvider):

    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        if not api_key:
            raise ProviderError(
                "Configuração do Google Maps incompleta.",
                category=ErrorCategory.CONFIGURATION,
                recommended_action="Defina GOOGLE_MAPS_API_KEY nas configurações do módulo.",
            )
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(timeout=_TIMEOUT)

    @property
    def id(self) -> str:
        return "google_maps"

    async def _send(self, method: str, url: str, max_retries: int = 1, **kwargs) -> httpx.Response:
        attempt = 0
        while True:
            try:
                response = await self._client.request(method, url, **kwargs)
            except httpx.TimeoutException as exc:
                raise ProviderError(
                    "Tempo esgotado ao contatar o Google Maps.",
                    category=ErrorCategory.TIMEOUT,
                    recommended_action="Tente novamente em alguns instantes.",
                ) from exc
            except httpx.RequestError as exc:
                raise ProviderError(
                    "Falha de conexão com o Google Maps.",
                    category=ErrorCategory.CONNECTIVITY,
                    recommended_action="Verifique sua conexão com a internet.",
                ) from exc

            if response.status_code in _TRANSIENT_STATUS and attempt < max_retries:
                attempt += 1
                await asyncio.sleep(0.5 * attempt)
                continue
            return response

    async def _geocode(self, address: str) -> tuple[float, float]:
        response = await self._send(
            "GET", "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": address, "key": self._api_key},
        )
        if response.status_code in _TRANSIENT_STATUS:
            raise ProviderError(
                "Google Maps temporariamente indisponível.",
                category=ErrorCategory.CONNECTIVITY,
                recommended_action="Tente novamente em alguns instantes.",
            )
        if response.status_code != 200:
            raise ProviderError(f"Google Maps retornou erro ({response.status_code}) ao geocodificar.", category=ErrorCategory.INTEGRATION)

        body = response.json()
        status = body.get("status")
        if status == "OK":
            try:
                location = body["results"][0]["geometry"]["location"]
                return location["lat"], location["lng"]
            except (KeyError, IndexError) as exc:
                # Achado da revisão de código: status "OK" com corpo em
                # formato inesperado (results vazio, campo faltando) nunca
                # pode vazar KeyError/IndexError cru — discover() é chamado
                # direto pelo wizard (módulo 6), sem nenhum try/except
                # genérico entre ele e o usuário como test_connection tem.
                raise ProviderError(
                    "Resposta inesperada do Google Maps ao geocodificar.", category=ErrorCategory.INTEGRATION,
                ) from exc
        if status == "ZERO_RESULTS":
            raise ProviderError(
                "Endereço de origem não encontrado pelo Google Maps.",
                category=ErrorCategory.INVALID_DATA,
                recommended_action="Confira o endereço configurado no critério de ICP.",
            )
        if status in ("REQUEST_DENIED", "INVALID_REQUEST"):
            raise ProviderError(
                "Chave de API do Google Maps inválida ou sem permissão de Geocoding.",
                category=ErrorCategory.AUTHENTICATION,
                recommended_action="Verifique GOOGLE_MAPS_API_KEY nas configurações do módulo.",
            )
        if status == "OVER_QUERY_LIMIT":
            raise ProviderError(
                "Limite de uso da API do Google Maps excedido.",
                category=ErrorCategory.API_LIMIT,
                recommended_action="Tente novamente mais tarde ou revise sua cota no Google Cloud.",
            )
        raise ProviderError(f"Google Maps retornou status inesperado ({status}) ao geocodificar.", category=ErrorCategory.INTEGRATION)

    async def test_connection(self) -> ConnectionTestResult:
        try:
            # Endereço fixo e estável só pra validar a chave de API — nunca
            # depende de configuração do usuário (ICP pode nem existir ainda).
            await self._geocode("1600 Amphitheatre Parkway, Mountain View, CA")
            return ConnectionTestResult.ok("google maps acessível")
        except ProviderError as exc:
            return ConnectionTestResult.fail(str(exc))

    async def fetch_companies(self) -> list[Company]:
        # Google Maps não participa do /sync periódico — não existe "lista
        # de empresas conhecidas" pra essa fonte, só busca sob demanda por
        # critério de ICP (discover()). Retornar [] aqui é o comportamento
        # correto, não uma lacuna.
        return []

    async def fetch_contacts(self, company_id: str) -> list[Contact]:
        return []

    async def fetch_context(self, company_id: str) -> ProviderContext:
        return ProviderContext(company_id=company_id)

    async def discover(self, origin_address: str, radius_km: float, place_category: str | None) -> list[PlaceSignal]:
        """Busca sob demanda (não faz parte do `/sync` periódico) — centro
        vem de `origin_address` (endereço cadastrado no ICP, módulo 1),
        raio e categoria vêm do mesmo critério. Retorna sinal bruto, nunca
        decide oportunidade (módulo 4 faz isso a partir daqui)."""
        if radius_km <= 0:
            raise ProviderError("Raio de busca precisa ser maior que zero.", category=ErrorCategory.INVALID_DATA)
        if radius_km > _MAX_RADIUS_KM:
            raise ProviderError(
                f"Raio de busca não pode passar de {_MAX_RADIUS_KM:.0f} km (limite da API do Google Maps).",
                category=ErrorCategory.INVALID_DATA,
            )

        lat, lng = await self._geocode(origin_address)

        body: dict = {
            "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": radius_km * 1000}},
        }
        if place_category:
            body["includedTypes"] = [place_category]

        response = await self._send(
            "POST", "https://places.googleapis.com/v1/places:searchNearby",
            json=body,
            headers={
                "X-Goog-Api-Key": self._api_key,
                "X-Goog-FieldMask": "places.id,places.displayName,places.types,places.businessStatus,"
                                     "places.rating,places.userRatingCount,places.formattedAddress",
                "Content-Type": "application/json",
            },
        )
        if response.status_code == 403:
            raise ProviderError(
                "Chave de API do Google Maps inválida ou sem permissão da Places API.",
                category=ErrorCategory.AUTHENTICATION,
                recommended_action="Verifique GOOGLE_MAPS_API_KEY e se a Places API (New) está habilitada no projeto.",
            )
        if response.status_code == 429:
            raise ProviderError(
                "Limite de uso da Places API excedido.",
                category=ErrorCategory.API_LIMIT,
                recommended_action="Tente novamente mais tarde ou revise sua cota no Google Cloud.",
            )
        if response.status_code in _TRANSIENT_STATUS:
            raise ProviderError(
                "Google Maps temporariamente indisponível.",
                category=ErrorCategory.CONNECTIVITY,
                recommended_action="Tente novamente em alguns instantes.",
            )
        if response.status_code != 200:
            raise ProviderError(f"Google Maps retornou erro ({response.status_code}) na busca.", category=ErrorCategory.INTEGRATION)

        body_out = response.json()
        signals = []
        try:
            for place in body_out.get("places", []):
                types = place.get("types") or []
                signals.append(PlaceSignal(
                    place_id=place["id"],
                    name=place.get("displayName", {}).get("text", ""),
                    category=types[0] if types else None,
                    business_status=place.get("businessStatus"),
                    rating=place.get("rating"),
                    review_count=place.get("userRatingCount", 0),
                    formatted_address=place.get("formattedAddress"),
                ))
        except (KeyError, TypeError) as exc:
            # Mesmo motivo do try/except em _geocode: um "place" sem "id"
            # (campo mudou de nome, field mask divergiu) nunca pode vazar
            # KeyError cru pra quem chama discover() direto.
            raise ProviderError(
                "Resposta inesperada do Google Maps na busca de lugares.", category=ErrorCategory.INTEGRATION,
            ) from exc
        return signals
