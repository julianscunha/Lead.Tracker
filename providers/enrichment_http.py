"""Fase Q — enriquecimento de porte e setor por uma API HTTP JSON que o OPERADOR configura (nenhum
fornecedor embutido). Provider SÓ coleta e normaliza: nenhuma IA, nenhum score, nenhuma UI. Não
participa do /sync (devolve listas vazias); quem chama é `POST /api/enrichment/run`, sob demanda.

Defesas (docs/implementacao/specs/fase-q-enriquecimento.md): o domínio sai de `normalize_domain`, é
revalidado e codificado na URL; a chave só vai em https e só no cabeçalho (nunca na URL, em log ou
em erro); toda chamada passa por `core/safe_fetch.py`; do JSON só se lê o que o operador mapeou
(`industry`, `employee_count`) e todo o resto é descartado — o JSON bruto nunca é gravado nem logado."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from urllib.parse import quote, urlsplit

import httpx

from core.errors import ErrorCategory
from core.models import Company, Contact
from core.normalization import GENERIC_DOMAINS, normalize_domain
from core.safe_fetch import _HOST_RE, Resolver, SafeFetchError, default_resolver, fetch_page
from providers.base import ConnectionTestResult, DataProvider, ProviderContext, ProviderError

log = logging.getLogger(__name__)

SOURCE_ID = "enrichment"
CALL_DEADLINE = 10.0  # por chamada (a tentativa extra tem o seu)
MAX_BYTES = 200_000
RETRY_WAIT = 1.0
TEST_DOMAIN = "example.com"
MAX_INDUSTRY = 100
MAX_EMPLOYEES = 10_000_000
_HEADER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]{0,63}$")
_PATH_RE = re.compile(r"^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+){0,7}$")
_RESERVED_HEADERS = {"host", "user-agent", "accept", "accept-encoding", "content-length", "connection"}


def eligible_domain(website: str | None) -> str | None:
    """Domínio próprio da empresa (nome de domínio válido, fora das plataformas genéricas) ou None."""
    domain = normalize_domain(website)
    if not domain or not _HOST_RE.match(domain):
        return None
    if any(domain == d or domain.endswith(f".{d}") for d in GENERIC_DOMAINS):
        return None
    return domain


def _pick(data, path: str):
    for part in path.split("."):
        if isinstance(data, dict):
            data = data.get(part)
        elif isinstance(data, list) and part.isdigit() and int(part) < len(data):
            data = data[int(part)]
        else:
            return None
    return data


def parse_employees(value) -> int | None:
    """Só inteiro > 0 (número ou texto numérico). Faixa ("51-200") e o resto viram vazio: sem ponto médio."""
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, str) and re.fullmatch(r"\d{1,9}", value.strip()):
        value = int(value.strip())
    if isinstance(value, int) and 0 < value <= MAX_EMPLOYEES:
        return value
    return None


def parse_industry(value) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    # leading = + - @ : neutraliza fórmula caso o valor um dia vá para planilha
    if not text or text[0] in "=+-@" or any(not c.isprintable() or c in "<>" for c in text):
        return None
    return text[:MAX_INDUSTRY]


class EnrichmentHttpProvider(DataProvider):
    def __init__(
        self, url_template: str, auth_header: str = "", api_key: str = "", map_employees: str = "",
        map_industry: str = "", client: httpx.AsyncClient | None = None, resolver: Resolver = default_resolver,
        retry_wait: float = RETRY_WAIT,
    ) -> None:
        template = (url_template or "").strip()
        header = (auth_header or "").strip()
        self._employees_path = (map_employees or "").strip()
        self._industry_path = (map_industry or "").strip()
        action = "Revise a configuração em Entrada de dados > Enriquecimento de empresas."
        if not template:
            raise ProviderError("Informe o endereço da API de enriquecimento.", ErrorCategory.CONFIGURATION, action)
        parts = urlsplit(template)
        if template.count("{domain}") != 1 or "{domain}" in parts.netloc or parts.scheme not in ("http", "https"):
            raise ProviderError(
                "O endereço da API precisa começar com https:// e ter {domain} uma vez, fora do nome do servidor.",
                ErrorCategory.CONFIGURATION, "Ex.: https://api.exemplo.com/v1/empresas?dominio={domain}",
            )
        paths = [p for p in (self._employees_path, self._industry_path) if p]
        if not paths:
            raise ProviderError("Informe onde estão o porte ou o setor na resposta da API.", ErrorCategory.CONFIGURATION, action)
        if any(not _PATH_RE.match(p) for p in paths):
            raise ProviderError("Os caminhos de leitura da resposta são inválidos.", ErrorCategory.CONFIGURATION, "Use nomes separados por ponto. Ex.: metrics.employees")
        self._headers: dict[str, str] = {}
        if api_key:
            if parts.scheme != "https":
                raise ProviderError("A chave da API só pode ser enviada por https.", ErrorCategory.CONFIGURATION, "Use um endereço https://.")
            if not _HEADER_RE.match(header) or header.lower() in _RESERVED_HEADERS or any(not c.isprintable() for c in api_key):
                raise ProviderError("O nome do cabeçalho de autenticação ou a chave é inválido.", ErrorCategory.CONFIGURATION, "Ex.: Authorization")
            self._headers = {header: api_key}
        self._template = template
        self._client = client
        self._resolver = resolver
        self._retry_wait = retry_wait

    @classmethod
    def from_env(cls, env: dict[str, str], **kwargs) -> "EnrichmentHttpProvider":
        return cls(
            env.get("ENRICHMENT_URL_TEMPLATE", ""), env.get("ENRICHMENT_AUTH_HEADER", ""), env.get("ENRICHMENT_API_KEY", ""),
            env.get("ENRICHMENT_MAP_EMPLOYEES", ""), env.get("ENRICHMENT_MAP_INDUSTRY", ""), **kwargs,
        )

    @property
    def id(self) -> str:
        return SOURCE_ID

    async def test_connection(self) -> ConnectionTestResult:
        try:
            found = await self.enrich(TEST_DOMAIN)
        except ProviderError as exc:
            return ConnectionTestResult.fail(str(exc))
        if found is None or (found.industry is None and found.employee_count is None):
            return ConnectionTestResult.ok("API acessível. O domínio de teste não trouxe dados (ou os caminhos configurados não existem na resposta).")
        return ConnectionTestResult.ok(
            f"API acessível. Leitura de teste: setor = {found.industry or 'vazio'}; funcionários = {found.employee_count or 'vazio'}.",
        )

    async def fetch_companies(self) -> list[Company]:
        return []  # não participa do /sync: roda só sob demanda

    async def fetch_contacts(self, company_id: str) -> list[Contact]:
        return []

    async def fetch_context(self, company_id: str) -> ProviderContext:
        return ProviderContext(company_id=company_id)

    async def enrich(self, website_or_domain: str | None) -> Company | None:
        """Company PARCIAL (só `industry` e `employee_count`) ou None (domínio não elegível ou API sem dado, 404)."""
        domain = eligible_domain(website_or_domain)
        if domain is None:
            return None
        url = self._template.replace("{domain}", quote(domain, safe=""))
        page = await self._get(url)
        if page.status == 404:
            return None
        try:
            data = json.loads(page.text)
        except ValueError:
            raise ProviderError("A API respondeu em um formato inesperado.", ErrorCategory.INVALID_DATA, "Confira o endereço e os caminhos de leitura.") from None
        industry = parse_industry(_pick(data, self._industry_path)) if self._industry_path else None
        employees = parse_employees(_pick(data, self._employees_path)) if self._employees_path else None
        return Company(  # o resto do JSON é descartado aqui; `name` é só obrigatório do modelo
            name=domain, industry=industry, employee_count=employees, sources=[],
        )

    async def _get(self, url: str):
        for attempt in (1, 2):
            try:
                page = await fetch_page(
                    url, client=self._client, resolver=self._resolver, deadline=CALL_DEADLINE, max_bytes=MAX_BYTES,
                    expect_ok=False, content_types=("application/json",), extra_headers=self._headers,
                )
            except SafeFetchError as exc:
                if exc.reason in ("rede", "sem_conexao"):
                    if attempt == 1:
                        await asyncio.sleep(self._retry_wait)
                        continue
                    raise ProviderError(
                        "A API de enriquecimento não respondeu a tempo ou está inacessível.", ErrorCategory.TIMEOUT,
                        "Tente novamente em instantes.",
                    ) from None
                if exc.reason in ("tipo_de_conteudo", "grande_demais"):
                    raise ProviderError("A API respondeu em um formato inesperado.", ErrorCategory.INVALID_DATA, "Confira o endereço configurado.") from None
                raise ProviderError(
                    "O endereço da API de enriquecimento não é aceito.", ErrorCategory.CONFIGURATION,
                    "Use um endereço https:// público, sem usuário, senha ou porta.",
                ) from None
            status = page.status
            if status in (401, 403):
                raise ProviderError(
                    "A API de enriquecimento recusou a chave.", ErrorCategory.AUTHENTICATION,
                    "Confira o nome do cabeçalho e a chave em Entrada de dados.",
                )
            if status == 429 or status >= 500:
                if attempt == 1:
                    await asyncio.sleep(self._retry_wait)
                    continue
                raise ProviderError(
                    "A API de enriquecimento está sobrecarregada ou indisponível.", ErrorCategory.API_LIMIT,
                    "Tente novamente mais tarde.",
                )
            if status == 404 or status == 200:
                return page
            log.warning("enrichment: API respondeu status %s", status)
            raise ProviderError("A API de enriquecimento não aceitou a consulta desta empresa.", ErrorCategory.INTEGRATION)
        raise AssertionError("inalcançável")  # pragma: no cover
