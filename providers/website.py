"""Fase P — Website da própria empresa (COMPANY_WEBSITE). Provider SÓ coleta o texto das páginas:
nenhuma IA, nenhum score, nenhuma UI (contrato de providers/base.py). Não participa do /sync de
empresas (devolve listas vazias); o texto coletado é consumido por `ai/portfolio_extract.py`.

Toda busca passa por `core/safe_fetch.py` (única porta de rede para dado não confiável). Respeita
robots.txt, lê no máximo `MAX_PAGES` páginas do MESMO site (a inicial + links dela) e extrai só o
texto visível (sem script/style/iframe/comentários; nenhum JavaScript é executado)."""
from __future__ import annotations

import asyncio
import logging
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import httpx

from core.models import Company, Contact
from core.safe_fetch import SafeFetchError, USER_AGENT, Resolver, default_resolver, fetch_page, validate_url
from providers.base import ConnectionTestResult, DataProvider, ProviderContext, ProviderError

log = logging.getLogger(__name__)

MAX_PAGES = 5
COLLECT_DEADLINE = 60.0  # prazo TOTAL da coleta (robots + páginas); o de safe_fetch é por página
MAX_TEXT_PER_PAGE = 12_000
MAX_TEXT_TOTAL = 30_000
_SKIP_TAGS = {"script", "style", "noscript", "iframe", "template", "svg", "canvas", "object"}  # só tags COM fechamento
_BLOCK_TAGS = {"p", "div", "li", "br", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "ul", "ol", "td", "th"}
_SKIP_HREF_PREFIXES = ("mailto:", "tel:", "javascript:", "data:", "#")
_SKIP_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".zip", ".mp4", ".webp", ".css", ".js", ".xml")


class _TextAndLinks(HTMLParser):
    """Texto visível + <title> + links. Ignora conteúdo de script/style/etc. e comentários."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._in_title = False
        self.title = ""
        self.chunks: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
        if tag in _BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        if tag == "title":
            self._in_title = False
        if tag in _BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif self._skip_depth == 0:
            self.chunks.append(data)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self.chunks).splitlines()]
        body = "\n".join(line for line in lines if line)
        title = " ".join(self.title.split())
        return (f"{title}\n{body}" if title else body)[:MAX_TEXT_PER_PAGE]


def extract_text_and_links(html: str) -> tuple[str, list[str]]:
    parser = _TextAndLinks()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 — HTML malformado nunca derruba a coleta; usa o que foi lido
        log.warning("website: HTML malformado, usando o texto lido até aqui")
    return parser.text(), parser.links


class WebsiteProvider(DataProvider):
    def __init__(
        self, site_url: str, client: httpx.AsyncClient | None = None, resolver: Resolver = default_resolver,
    ) -> None:
        if not (site_url or "").strip():
            raise ProviderError(
                "Informe o endereço do site da sua empresa.",
                recommended_action="Preencha o campo em Entrada de dados > Website da empresa.",
            )
        try:
            self._root = validate_url(site_url.strip())  # revalida SEMPRE na hora de usar, não confia no valor salvo
        except SafeFetchError as exc:
            raise ProviderError(str(exc.message), recommended_action=exc.recommended_action) from None
        self._client = client
        self._resolver = resolver

    @property
    def id(self) -> str:
        return "website"

    async def test_connection(self) -> ConnectionTestResult:
        try:
            await fetch_page(self._root.url, client=self._client, resolver=self._resolver, origin_host=self._root.host)
        except SafeFetchError as exc:
            return ConnectionTestResult.fail(str(exc))
        return ConnectionTestResult.ok("Site acessível.")

    async def fetch_companies(self) -> list[Company]:
        return []  # não participa do /sync de empresas

    async def fetch_contacts(self, company_id: str) -> list[Contact]:
        return []

    async def fetch_context(self, company_id: str = "self") -> ProviderContext:
        pages = await self.collect_pages()
        return ProviderContext(
            company_id=company_id, raw_text="\n\n".join(text for _, text in pages),
            pages=[text for _, text in pages], extra={"urls": [url for url, _ in pages]},
        )

    async def _allowed_by_robots(self) -> RobotFileParser | None:
        """None = tudo permitido (robots ausente). Levanta se robots.txt negar acesso (401/403)."""
        robots_url = f"{self._root.scheme}://{self._root.host}/robots.txt"
        page = await fetch_page(
            robots_url, client=self._client, resolver=self._resolver, expect_ok=False,
            origin_host=self._root.host, content_types=("text/plain", "text/html"),
        )
        if page.status in (401, 403):
            raise SafeFetchError("robots_negado")
        if page.status != 200 or not page.text.strip():
            return None
        parser = RobotFileParser()
        parser.parse(page.text.splitlines())
        return parser

    async def collect_pages(self, deadline: float | None = None) -> list[tuple[str, str]]:
        """[(url, texto)] — a página inicial e até MAX_PAGES-1 links do mesmo site. Texto total truncado.
        Um site lento (slowloris) não pode prender a requisição: há um prazo TOTAL, além do por página."""
        try:
            async with asyncio.timeout(deadline if deadline is not None else COLLECT_DEADLINE):
                return await self._collect_pages()
        except TimeoutError:
            log.warning("website: prazo total da coleta estourou")
            raise SafeFetchError("prazo_total") from None

    async def _collect_pages(self) -> list[tuple[str, str]]:
        robots = await self._allowed_by_robots()

        def allowed(url: str) -> bool:
            return robots is None or robots.can_fetch(USER_AGENT, url)

        if not allowed(self._root.url):
            raise SafeFetchError("robots_negado")
        home = await fetch_page(self._root.url, client=self._client, resolver=self._resolver, origin_host=self._root.host)
        text, links = extract_text_and_links(home.text)
        pages: list[tuple[str, str]] = [(home.url, text)]
        seen = {home.url}
        for href in links:
            if len(pages) >= MAX_PAGES:
                break
            if href.lower().startswith(_SKIP_HREF_PREFIXES) or href.lower().split("?")[0].endswith(_SKIP_EXTENSIONS):
                continue
            try:
                candidate = validate_url(urljoin(home.url, href).split("#")[0])
            except SafeFetchError:
                continue  # link inválido/interno é ignorado, nunca derruba a coleta
            if candidate.host.removeprefix("www.") != self._root.host.removeprefix("www.") or candidate.url in seen:
                continue
            seen.add(candidate.url)
            if not allowed(candidate.url):
                continue
            try:
                page = await fetch_page(candidate.url, client=self._client, resolver=self._resolver, origin_host=self._root.host)
            except SafeFetchError:
                continue  # uma página ruim não impede as outras
            pages.append((page.url, extract_text_and_links(page.text)[0]))
        total = 0
        trimmed: list[tuple[str, str]] = []
        for url, text in pages:
            room = MAX_TEXT_TOTAL - total
            if room <= 0:
                break
            trimmed.append((url, text[:room]))
            total += len(trimmed[-1][1])
        return trimmed
