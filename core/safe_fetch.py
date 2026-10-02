"""Fase P — única porta de rede para dado externo NÃO confiável: o site da própria empresa do
operador (COMPANY_WEBSITE). O resto do produto nunca busca URL de lead/Maps/CRM (Fase K).

Defesas (docs/implementacao/specs/fase-p-portfolio-do-site.md): só http/https nas portas 80/443,
sem userinfo, host precisa ser nome de domínio (nenhum IP literal, nem forma ofuscada); o DNS é
resolvido AQUI e TODOS os IPs precisam ser públicos; a conexão vai no IP já validado (sem nova
resolução: DNS rebinding) com `Host` e SNI do nome original; redirects são seguidos à mão (máx. 3,
mesmo site, https→http bloqueado) revalidando tudo a cada salto; leitura em stream com teto de bytes
DECODIFICADOS, só text/html e text/plain, prazo total, sem proxy do ambiente, sem cookies.

O usuário nunca vê o motivo técnico da recusa (não revela IP nem o que foi bloqueado): a mensagem é
sempre a mesma; o motivo vai só para o log, sem URL completa nem conteúdo."""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from core.errors import DomainError, ErrorCategory

log = logging.getLogger(__name__)

USER_AGENT = "LeadTracker/1.2 (+https://github.com/julianscunha/Lead.Tracker)"
MAX_URL_LEN = 2048
MAX_BYTES = 1_000_000
MAX_REDIRECTS = 3
TOTAL_DEADLINE = 30.0
_ALLOWED_PORTS = {80, 443}
_BLOCKED_NAMES = {"localhost", "metadata.google.internal", "metadata"}
_BLOCKED_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".home", ".corp", ".intranet")
# nome de domínio: rótulos alfanuméricos e o último (TLD) alfabético ou punycode — recusa 127.1,
# 2130706433, 0x7f000001, 017700000001 e qualquer IP literal (inclusive IPv6)
_HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})$"
)
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_REDIRECT_STATUS = {301, 302, 303, 307, 308}
_DEFAULT_TYPES = ("text/html", "text/plain", "application/xhtml+xml")

Resolver = Callable[[str, int], Awaitable[list[str]]]


class SafeFetchError(DomainError):
    """Mensagem sempre genérica; `reason` é só para teste e log (nunca para o usuário)."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(
            ErrorCategory.CONNECTIVITY,
            "Não foi possível ler o site informado.",
            "Verifique o endereço em Configurações.",
        )


@dataclass(frozen=True)
class Target:
    scheme: str
    host: str
    port: int
    path_query: str

    @property
    def url(self) -> str:
        default = 443 if self.scheme == "https" else 80
        netloc = self.host if self.port == default else f"{self.host}:{self.port}"
        return f"{self.scheme}://{netloc}{self.path_query}"


@dataclass(frozen=True)
class Page:
    url: str
    status: int
    content_type: str
    text: str


def validate_url(raw: str) -> Target:
    """Valida a URL SEM tocar a rede. Levanta `SafeFetchError` com o motivo."""
    if not isinstance(raw, str) or not raw or len(raw) > MAX_URL_LEN:
        raise SafeFetchError("tamanho")
    if any(c.isspace() or not c.isprintable() for c in raw):
        raise SafeFetchError("caractere_invalido")
    try:
        parts = urlsplit(raw)
        port = parts.port
        hostname = parts.hostname
    except ValueError:
        raise SafeFetchError("url_malformada") from None
    if parts.scheme not in ("http", "https"):
        raise SafeFetchError("esquema")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise SafeFetchError("userinfo")
    default_port = 443 if parts.scheme == "https" else 80
    port = port if port is not None else default_port
    if port not in _ALLOWED_PORTS:
        raise SafeFetchError("porta")
    if not hostname:
        raise SafeFetchError("host_vazio")
    try:
        host = hostname.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise SafeFetchError("idna") from None
    if host in _BLOCKED_NAMES or host.endswith(_BLOCKED_SUFFIXES) or not _HOST_RE.match(host):
        raise SafeFetchError("host_nao_permitido")
    path = parts.path or "/"
    return Target(parts.scheme, host, port, path + (f"?{parts.query}" if parts.query else ""))


def ensure_public_ip(address: str) -> str:
    """Devolve o IP normalizado se for público; senão levanta. IPv4 mapeado em IPv6 é validado como IPv4."""
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        raise SafeFetchError("ip_invalido") from None
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        elif ip in _NAT64 or ip.sixtofour is not None or ip.teredo is not None:
            raise SafeFetchError("ip_nao_publico")
    if not ip.is_global or ip.is_multicast:
        raise SafeFetchError("ip_nao_publico")
    return str(ip)


async def default_resolver(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


def _same_site(origin_host: str, host: str) -> bool:
    strip = lambda h: h[4:] if h.startswith("www.") else h  # noqa: E731
    return strip(origin_host) == strip(host)


def _ip_url(target: Target, ip: str) -> str:
    literal = f"[{ip}]" if ":" in ip else ip
    return f"{target.scheme}://{literal}:{target.port}{target.path_query}"


def _charset(content_type: str) -> str:
    match = re.search(r"charset=([\w-]+)", content_type, re.I)
    return match.group(1) if match else "utf-8"


async def fetch_page(
    url: str, *, client: httpx.AsyncClient | None = None, resolver: Resolver = default_resolver,
    max_bytes: int = MAX_BYTES, deadline: float = TOTAL_DEADLINE, expect_ok: bool = True,
    origin_host: str | None = None, content_types: tuple[str, ...] = _DEFAULT_TYPES,
) -> Page:
    """Busca UMA página com todas as defesas acima. `expect_ok=False` devolve também 4xx (robots.txt).
    `origin_host`: site de origem (para seguir redirects/links só dentro dele); padrão = o do próprio `url`."""
    first = validate_url(url)
    origin = origin_host or first.host
    if not _same_site(origin, first.host):
        raise SafeFetchError("fora_do_site")
    owns_client = client is None
    http = client or httpx.AsyncClient(
        trust_env=False, follow_redirects=False, timeout=httpx.Timeout(10.0, connect=5.0),
    )
    try:
        async with asyncio.timeout(deadline):
            return await _fetch_following(first, http, resolver, max_bytes, expect_ok, origin, content_types)
    except SafeFetchError as exc:
        log.warning("safe_fetch recusou: %s", exc.reason)
        raise
    except (TimeoutError, httpx.HTTPError, OSError) as exc:
        log.warning("safe_fetch falhou: %s", type(exc).__name__)
        raise SafeFetchError("rede") from None
    finally:
        if owns_client:
            await http.aclose()


async def _fetch_following(
    target: Target, http: httpx.AsyncClient, resolver: Resolver, max_bytes: int, expect_ok: bool,
    origin: str, content_types: tuple[str, ...],
) -> Page:
    for hop in range(MAX_REDIRECTS + 1):
        addresses = await resolver(target.host, target.port)
        if not addresses:
            raise SafeFetchError("dns_vazio")
        validated = [ensure_public_ip(a) for a in addresses]  # um IP privado entre os resolvidos já recusa tudo
        headers = {
            "Host": target.host, "User-Agent": USER_AGENT, "Accept": ", ".join(content_types),
            "Accept-Encoding": "identity",  # sem compressão: bomba de descompressão
        }
        async with http.stream(
            "GET", _ip_url(target, validated[0]), headers=headers, extensions={"sni_hostname": target.host},
        ) as response:
            if response.status_code in _REDIRECT_STATUS:
                location = response.headers.get("location")
                if not location or hop == MAX_REDIRECTS:
                    raise SafeFetchError("redirect")
                next_target = validate_url(urljoin(target.url, location))
                if target.scheme == "https" and next_target.scheme == "http":
                    raise SafeFetchError("downgrade")
                if not _same_site(origin, next_target.host):
                    raise SafeFetchError("fora_do_site")
                target = next_target
                continue
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if expect_ok and response.status_code != 200:
                raise SafeFetchError("status")
            if content_type not in content_types:
                if expect_ok or response.status_code == 200:
                    raise SafeFetchError("tipo_de_conteudo")
                return Page(target.url, response.status_code, content_type, "")
            buffer = bytearray()
            async for chunk in response.aiter_bytes():
                buffer.extend(chunk)
                if len(buffer) > max_bytes:
                    raise SafeFetchError("grande_demais")
            text = bytes(buffer).decode(_charset(response.headers.get("content-type", "")), errors="replace")
            return Page(target.url, response.status_code, content_type, text)
    raise SafeFetchError("redirect")  # inalcançável (o laço sempre retorna ou levanta)
