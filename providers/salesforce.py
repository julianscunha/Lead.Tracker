"""
SalesforceProvider — CRM real via OAuth 2.0 Client Credentials Flow
(https://help.salesforce.com/s/articleView?id=xcloud.remoteaccess_oauth_client_credentials_flow.htm)
+ consultas SOQL na REST API
(https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/dome_query.htm).

Timeout explícito e retry só em erro transitório (5xx/429) — nunca em
credencial inválida (CLAUDE.md 'Error handling & resilience'). `client` é
injetável para teste com httpx.MockTransport, sem chamada de rede real.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

import httpx

from core.errors import ErrorCategory
from core.models import Address, Company, Contact, SourceRef
from providers.base import ConnectionTestResult, DataProvider, ProviderContext, ProviderError

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_TRANSIENT_STATUS = {429, 500, 502, 503, 504}
_API_VERSION = "v59.0"
_MAX_PAGES = 1000  # guarda contra nextRecordsUrl em loop (bug do Salesforce ou resposta inesperada)

# IDs do Salesforce têm exatamente 15 ou 18 caracteres alfanuméricos — validar
# aqui fecha a fronteira de confiança antes de interpolar em SOQL (nunca
# confiar em company_id vindo do chamador para montar a query).
_SALESFORCE_ID_RE = re.compile(r"^[a-zA-Z0-9]{15}([a-zA-Z0-9]{3})?$")

# Fase C, Fatia 4a — mapeamento determinístico de Title -> nível hierárquico
# (proxy de autoridade). Ordem importa: checado de cima pra baixo, primeiro
# match vence (ex.: "diretor técnico" cai em decisor, não operacional).
_SENIORITY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("decisor", ["gestor", "diretor", "gerente", "head", "ceo", "cto", "cio"]),
    ("influenciador_tecnico", ["arquiteto", "especialista"]),
    ("operacional", ["técnico", "tecnico", "analista", "suporte"]),
]


def _parse_salesforce_date(value: str | None) -> datetime | None:
    """`LastActivityDate` é campo `Date` do Salesforce ("YYYY-MM-DD"),
    sem hora — vira meia-noite UTC do dia, consistente com o padrão UTC-aware
    do resto do projeto (core/models.py `_now()`)."""
    if not value:
        return None
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _billing_address(record: dict) -> Address | None:
    """`None` inteiro quando a conta não tem nenhum campo Billing
    preenchido — nunca um `Address` com os 4 campos `None` (spec:
    docs/specs/salesforce-account-standard-fields.md)."""
    city, state, postal_code, country = (
        record.get("BillingCity"), record.get("BillingState"),
        record.get("BillingPostalCode"), record.get("BillingCountry"),
    )
    if not any((city, state, postal_code, country)):
        return None
    return Address(city=city, state=state, postal_code=postal_code, country=country)


def _infer_seniority_tier(title: str | None) -> str | None:
    if not title:
        return None
    lowered = title.lower()
    for tier, keywords in _SENIORITY_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return tier
    return None


class SalesforceProvider(DataProvider):

    def __init__(self, client_id: str, client_secret: str, login_url: str, client: httpx.AsyncClient | None = None) -> None:
        if not client_id or not client_secret or not login_url:
            raise ProviderError(
                "Configuração do Salesforce incompleta.",
                category=ErrorCategory.CONFIGURATION,
                recommended_action="Defina SALESFORCE_CLIENT_ID, SALESFORCE_CLIENT_SECRET e SALESFORCE_LOGIN_URL nas configurações do módulo.",
            )
        self._client_id = client_id
        self._client_secret = client_secret
        self._login_url = login_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=_TIMEOUT)
        self._access_token: str | None = None
        self._instance_url: str | None = None

    @property
    def id(self) -> str:
        return "salesforce"

    async def _send(self, method: str, url: str, max_retries: int = 1, **kwargs) -> httpx.Response:
        attempt = 0
        while True:
            try:
                response = await self._client.request(method, url, **kwargs)
            except httpx.TimeoutException as exc:
                raise ProviderError(
                    "Tempo esgotado ao contatar o Salesforce.",
                    category=ErrorCategory.TIMEOUT,
                    recommended_action="Tente novamente em alguns instantes.",
                ) from exc
            except httpx.RequestError as exc:
                raise ProviderError(
                    "Falha de conexão com o Salesforce.",
                    category=ErrorCategory.CONNECTIVITY,
                    recommended_action="Verifique sua conexão com a internet.",
                ) from exc

            if response.status_code in _TRANSIENT_STATUS and attempt < max_retries:
                attempt += 1
                await asyncio.sleep(0.5 * attempt)
                continue
            return response

    async def _authenticate(self) -> None:
        response = await self._send(
            "POST",
            f"{self._login_url}/services/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        if response.status_code in (400, 401, 403):
            raise ProviderError(
                "Credenciais do Salesforce inválidas ou sem permissão.",
                category=ErrorCategory.AUTHENTICATION,
                recommended_action="Verifique SALESFORCE_CLIENT_ID/SALESFORCE_CLIENT_SECRET nas configurações do módulo.",
            )
        if response.status_code in _TRANSIENT_STATUS:
            raise ProviderError(
                "Salesforce temporariamente indisponível.",
                category=ErrorCategory.CONNECTIVITY,
                recommended_action="Tente novamente em alguns instantes.",
            )
        if response.status_code != 200:
            raise ProviderError(f"Salesforce retornou erro ({response.status_code}) ao autenticar.", category=ErrorCategory.INTEGRATION)

        try:
            data = response.json()
            self._access_token = data["access_token"]
            self._instance_url = data["instance_url"]
        except (ValueError, KeyError, TypeError) as exc:
            # ValueError cobre json.JSONDecodeError — resposta 200 mas corpo
            # inesperado nunca pode vazar como exceção técnica crua.
            raise ProviderError(
                "Resposta inesperada do Salesforce ao autenticar.",
                category=ErrorCategory.INTEGRATION,
            ) from exc

    async def _query(self, soql: str, _reauthed: bool = False, treat_malformed_query_as_empty: bool = False) -> list[dict]:
        if self._access_token is None:
            await self._authenticate()

        records: list[dict] = []
        url = f"{self._instance_url}/services/data/{_API_VERSION}/query"
        params: dict | None = {"q": soql}
        pages = 0

        while url:
            pages += 1
            if pages > _MAX_PAGES:
                raise ProviderError("Salesforce retornou páginas em excesso — consulta abortada.", category=ErrorCategory.INTEGRATION)

            response = await self._send(
                "GET", url, params=params, headers={"Authorization": f"Bearer {self._access_token}"},
            )
            if response.status_code in (401, 403):
                # Token pode ter expirado no meio da sessão (não é credencial errada de
                # fato) — reautentica uma vez; só vira erro de credencial se persistir.
                if not _reauthed:
                    self._access_token = None
                    await self._authenticate()
                    return await self._query(soql, _reauthed=True, treat_malformed_query_as_empty=treat_malformed_query_as_empty)
                raise ProviderError(
                    "Sessão do Salesforce expirada ou sem permissão.",
                    category=ErrorCategory.AUTHENTICATION,
                    recommended_action="Verifique as credenciais do Salesforce nas configurações do módulo.",
                )
            if treat_malformed_query_as_empty and response.status_code == 400:
                # FIELDS(CUSTOM) numa org sem nenhum campo personalizado devolve
                # MALFORMED_QUERY (400) — não é falha real, é a resposta esperada
                # pra "sem customização". Só esse errorCode específico vira lista
                # vazia; qualquer outro 400 (SOQL malformado de verdade) continua
                # caindo no `raise` genérico abaixo. Corpo não-JSON (proxy/WAF
                # atípico na frente do 400) nunca vira exceção técnica crua —
                # cai no `raise` genérico abaixo como qualquer outro 400.
                try:
                    errors = response.json()
                except ValueError:
                    errors = None
                if isinstance(errors, list) and any(e.get("errorCode") == "MALFORMED_QUERY" for e in errors):
                    return []
            if response.status_code in _TRANSIENT_STATUS:
                raise ProviderError(
                    "Salesforce temporariamente indisponível.",
                    category=ErrorCategory.CONNECTIVITY,
                    recommended_action="Tente novamente em alguns instantes.",
                )
            if response.status_code != 200:
                raise ProviderError(f"Salesforce retornou erro ({response.status_code}).", category=ErrorCategory.INTEGRATION)

            body = response.json()
            records.extend(body.get("records", []))
            next_url = body.get("nextRecordsUrl")
            url = f"{self._instance_url}{next_url}" if next_url else None
            params = None  # nextRecordsUrl já vem com a querystring embutida

        return records

    async def test_connection(self) -> ConnectionTestResult:
        try:
            await self._authenticate()
            return ConnectionTestResult.ok("salesforce acessível")
        except ProviderError as exc:
            return ConnectionTestResult.fail(str(exc))

    async def fetch_companies(self) -> list[Company]:
        records = await self._query(
            "SELECT Id, Name, Website, LastActivityDate, Industry, AnnualRevenue, NumberOfEmployees, "
            "BillingCity, BillingState, BillingPostalCode, BillingCountry FROM Account"
        )
        return [
            Company(
                id=record["Id"],
                name=record["Name"],
                website=record.get("Website"),
                sources=[SourceRef(type="salesforce")],
                last_activity_at=_parse_salesforce_date(record.get("LastActivityDate")),
                industry=record.get("Industry"),
                annual_revenue=record.get("AnnualRevenue"),
                employee_count=record.get("NumberOfEmployees"),
                address=_billing_address(record),
            )
            for record in records
        ]

    async def fetch_contacts(self, company_id: str) -> list[Contact]:
        if not _SALESFORCE_ID_RE.fullmatch(company_id):
            raise ProviderError("Identificador de empresa inválido.", category=ErrorCategory.INVALID_DATA)

        records = await self._query(f"SELECT Id, Name, Email, Phone, Title FROM Contact WHERE AccountId = '{company_id}'")
        return [
            Contact(
                id=record["Id"],
                company_id=company_id,
                name=record["Name"],
                email=record.get("Email"),
                phone=record.get("Phone"),
                role=record.get("Title"),
                sources=[SourceRef(type="salesforce")],
                seniority_tier=_infer_seniority_tier(record.get("Title")),
            )
            for record in records
        ]

    async def fetch_context(self, company_id: str) -> ProviderContext:
        """Campos personalizados (`__c`) da conta, como contexto bruto pra
        uso futuro de IA — nunca interpretado aqui, nunca vira regra de
        oportunidade (isso é trabalho do opportunity_engine). `FIELDS(CUSTOM)`
        (spec: docs/specs/salesforce-custom-fields-context.md) evita precisar
        conhecer os nomes dos campos de antemão — cada org Salesforce tem um
        conjunto diferente. Sem contexto rico ainda (raw_text/pages) —
        Salesforce não tem "texto de site"."""
        if not _SALESFORCE_ID_RE.fullmatch(company_id):
            raise ProviderError("Identificador de empresa inválido.", category=ErrorCategory.INVALID_DATA)

        records = await self._query(
            f"SELECT FIELDS(CUSTOM) FROM Account WHERE Id = '{company_id}' LIMIT 1",
            treat_malformed_query_as_empty=True,
        )
        if not records:
            return ProviderContext(company_id=company_id)
        custom_fields = {key: value for key, value in records[0].items() if key != "attributes"}
        return ProviderContext(company_id=company_id, extra={"custom_fields": custom_fields})
