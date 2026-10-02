"""Fase P — coleta segura (SSRF, limites, redirects). Nenhum teste depende de rede real."""
import asyncio
import gzip
import logging
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.safe_fetch import SafeFetchError, ensure_public_ip, fetch_page, validate_url  # noqa: E402

PUBLIC = ["93.184.216.34"]


class _Net:
    """Resolvedor + transporte falsos que contam chamadas: URL recusada não pode tocar nenhum dos dois."""

    def __init__(self, handler=None, dns=None):
        self.dns_calls: list[str] = []
        self.requests: list[httpx.Request] = []
        self._handler = handler or (lambda req: httpx.Response(200, headers={"content-type": "text/html"}, text="<p>oi</p>"))
        self._dns = dns or {}

    async def resolver(self, host, port):
        self.dns_calls.append(host)
        return self._dns.get(host, PUBLIC)

    def client(self):
        def handler(request):
            self.requests.append(request)
            return self._handler(request)
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)


def _run(net, url, **kw):
    async def go():
        async with net.client() as client:
            return await fetch_page(url, client=client, resolver=net.resolver, **kw)
    return asyncio.run(go())


BAD_URLS = [
    "file:///etc/passwd", "ftp://x.com", "gopher://x.com", "javascript:alert(1)", "data:text/html,x",
    "http://127.0.0.1", "http://127.1", "http://2130706433", "http://0x7f000001", "http://017700000001",
    "http://0.0.0.0", "http://localhost", "http://localhost:8000", "http://[::1]", "http://[::ffff:127.0.0.1]",
    "http://[fe80::1]", "http://[fc00::1]", "http://10.0.0.5", "http://192.168.1.1", "http://172.16.0.1",
    "http://100.64.0.1", "http://169.254.169.254/latest/meta-data", "http://metadata.google.internal",
    "http://user:pass@good.com", "http://good.com@127.0.0.1", "http://good.com:22", "http://good.com:8080",
    "http://a.com/\r\nX", "http://a.com/ x", "http://a\tb.com", "https://" + "a" * 2050 + ".com", "", "   ",
    "https://servidor.local", "https://painel.internal", "http://example.com:0",
]


@pytest.mark.parametrize("url", BAD_URLS)
def test_malicious_or_internal_urls_are_refused_without_touching_dns_or_network(url):
    net = _Net()
    with pytest.raises(SafeFetchError) as exc:
        _run(net, url)
    assert net.dns_calls == [] and net.requests == []
    assert "127.0.0.1" not in str(exc.value) and "bloque" not in str(exc.value).lower()  # mensagem genérica


def test_user_never_sees_the_technical_reason_and_message_is_friendly():
    with pytest.raises(SafeFetchError) as exc:
        validate_url("http://10.0.0.5")
    assert exc.value.message == "Não foi possível ler o site informado."
    assert "Configurações" in str(exc.value)


@pytest.mark.parametrize("ip", [
    "127.0.0.1", "10.1.2.3", "192.168.0.1", "172.31.0.1", "169.254.169.254", "100.64.0.1", "0.0.0.0", "224.0.0.1",
    "::1", "fe80::1", "fc00::1", "::ffff:127.0.0.1", "::ffff:10.0.0.1", "64:ff9b::7f00:1", "2002:7f00:1::", "::",
])
def test_non_public_ips_are_refused(ip):
    with pytest.raises(SafeFetchError):
        ensure_public_ip(ip)


def test_public_ips_pass():
    assert ensure_public_ip("93.184.216.34") == "93.184.216.34"
    assert ensure_public_ip("::ffff:93.184.216.34") == "93.184.216.34"


def test_host_that_resolves_to_private_or_mixes_private_is_refused():
    for dns in ({"good.com": ["127.0.0.1"]}, {"good.com": ["93.184.216.34", "10.0.0.1"]}, {"good.com": []}):
        net = _Net(dns=dns)
        with pytest.raises(SafeFetchError):
            _run(net, "https://good.com")
        assert net.requests == []


def test_connection_goes_to_the_validated_ip_with_original_host_and_sni_no_second_resolution():
    net = _Net()
    page = _run(net, "https://good.com/produtos?x=1")
    request = net.requests[0]
    assert request.url.host == "93.184.216.34" and request.headers["host"] == "good.com"
    assert request.extensions["sni_hostname"] == "good.com" and request.url.path == "/produtos"
    assert net.dns_calls == ["good.com"] and page.text == "<p>oi</p>"
    assert request.headers["accept-encoding"] == "identity" and "LeadTracker" in request.headers["user-agent"]
    assert "cookie" not in request.headers and "authorization" not in request.headers


def test_redirect_to_internal_other_site_downgrade_loop_and_too_many_hops_are_refused():
    def redirect_to(location):
        return lambda req: httpx.Response(302, headers={"location": location})

    for location in ("http://127.0.0.1/", "http://169.254.169.254/x", "https://outro.com/", "file:///etc/passwd", "//10.0.0.1/"):
        net = _Net(handler=redirect_to(location))
        with pytest.raises(SafeFetchError):
            _run(net, "https://good.com")
        assert all(r.url.host == "93.184.216.34" for r in net.requests)  # nada além do IP público validado
    net = _Net(handler=redirect_to("http://good.com/x"))
    with pytest.raises(SafeFetchError) as exc:
        _run(net, "https://good.com")
    assert exc.value.reason == "downgrade"
    net = _Net(handler=redirect_to("/a"))  # laço infinito
    with pytest.raises(SafeFetchError) as exc:
        _run(net, "https://good.com")
    assert exc.value.reason == "redirect" and len(net.requests) == 4  # 1 + 3 saltos


def test_same_site_redirect_with_www_swap_is_followed_and_revalidated():
    def handler(request):
        if request.headers["host"] == "good.com":
            return httpx.Response(301, headers={"location": "https://www.good.com/home"})
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text="ok")
    net = _Net(handler=handler)
    assert _run(net, "https://good.com").url == "https://www.good.com/home"
    assert net.dns_calls == ["good.com", "www.good.com"]  # revalida o DNS a cada salto


def test_rebinding_second_resolution_private_is_refused_on_redirect_hop():
    calls = {"n": 0}

    async def rebinding(host, port):
        calls["n"] += 1
        return PUBLIC if calls["n"] == 1 else ["10.0.0.1"]

    net = _Net(handler=lambda req: httpx.Response(302, headers={"location": "https://good.com/b"}))

    async def go():
        async with net.client() as client:
            await fetch_page("https://good.com", client=client, resolver=rebinding)
    with pytest.raises(SafeFetchError):
        asyncio.run(go())
    assert len(net.requests) == 1


def test_body_over_limit_is_aborted_and_gzip_is_not_accepted():
    big = httpx.Response(200, headers={"content-type": "text/html"}, content=b"a" * 5_000_000)
    with pytest.raises(SafeFetchError) as exc:
        _run(_Net(handler=lambda r: big), "https://good.com", max_bytes=1000)
    assert exc.value.reason == "grande_demais"
    bomb = gzip.compress(b"a" * 5_000_000)
    net = _Net(handler=lambda r: httpx.Response(200, headers={"content-type": "text/html", "content-encoding": "gzip"}, content=bomb))
    with pytest.raises(SafeFetchError):
        _run(net, "https://good.com", max_bytes=100_000)  # o limite vale sobre os bytes DECODIFICADOS
    assert net.requests[0].headers["accept-encoding"] == "identity"


@pytest.mark.parametrize("content_type", ["application/pdf", "image/png", "application/octet-stream", ""])
def test_non_text_content_types_are_refused_without_reading_the_body(content_type):
    class Boom(httpx.AsyncByteStream):
        async def __aiter__(self):
            raise AssertionError("corpo não pode ser lido")
            yield b""

    net = _Net(handler=lambda r: httpx.Response(200, headers={"content-type": content_type}, stream=Boom()))
    with pytest.raises(SafeFetchError) as exc:
        _run(net, "https://good.com")
    assert exc.value.reason == "tipo_de_conteudo"


def test_total_deadline_stops_a_response_that_never_ends():
    class Slow(httpx.AsyncByteStream):
        async def __aiter__(self):
            while True:
                await asyncio.sleep(0.05)
                yield b"a"

    net = _Net(handler=lambda r: httpx.Response(200, headers={"content-type": "text/html"}, stream=Slow()))
    with pytest.raises(SafeFetchError) as exc:
        _run(net, "https://good.com", deadline=0.3, max_bytes=10_000_000)
    assert exc.value.reason == "rede"


def test_non_200_is_an_error_unless_expect_ok_is_false_for_robots():
    net = _Net(handler=lambda r: httpx.Response(404, headers={"content-type": "text/plain"}, text="x"))
    with pytest.raises(SafeFetchError):
        _run(net, "https://good.com/p")
    page = _run(net, "https://good.com/robots.txt", expect_ok=False)
    assert page.status == 404


def test_origin_host_restricts_links_to_the_same_site():
    with pytest.raises(SafeFetchError) as exc:
        _run(_Net(), "https://outro.com/p", origin_host="good.com")
    assert exc.value.reason == "fora_do_site"
    assert _run(_Net(), "https://www.good.com/p", origin_host="good.com").status == 200


def test_logs_never_contain_the_url_query_or_body(caplog):
    caplog.set_level(logging.DEBUG)
    with pytest.raises(SafeFetchError):
        _run(_Net(), "http://10.0.0.5/segredo?token=abc123")
    assert "abc123" not in caplog.text and "segredo" not in caplog.text


@pytest.mark.parametrize("ip", ["::7f00:1", "::10.0.0.1", "::1.2.3.4", "::ffff:0:0", "100::1", "3fff::1"])
def test_ipv4_compatible_and_non_global_ipv6_are_refused(ip):
    """Regressão da revisão: `::7f00:1` (== ::127.0.0.1) tinha is_global True."""
    with pytest.raises(SafeFetchError):
        ensure_public_ip(ip)


def test_global_unicast_ipv6_still_passes():
    assert ensure_public_ip("2606:2800:220:1:248:1893:25c8:1946") == "2606:2800:220:1:248:1893:25c8:1946"


def test_ipv4_is_tried_first_and_next_validated_ip_is_used_when_one_cannot_connect():
    """Regressão da revisão: só o primeiro IP era usado e a ordem era por texto (IPv6 antes de IPv4)."""
    from core.safe_fetch import default_resolver  # noqa: F401
    tried: list[str] = []

    def handler(request):
        tried.append(request.url.host)
        if request.url.host != "93.184.216.34":
            raise httpx.ConnectError("sem rota IPv6")
        return httpx.Response(200, headers={"content-type": "text/html"}, text="ok")

    net = _Net(handler=handler, dns={"good.com": ["2606:2800:220:1:248:1893:25c8:1946", "93.184.216.34"]})
    # o resolvedor falso devolve nessa ordem; o fetch usa na ordem recebida e cai para o seguinte
    assert _run(net, "https://good.com").text == "ok"
    assert tried == ["2606:2800:220:1:248:1893:25c8:1946", "93.184.216.34"]


def test_default_resolver_orders_ipv4_before_ipv6(monkeypatch):
    import socket
    from core.safe_fetch import default_resolver

    async def fake(self, host, port, **kw):
        return [(socket.AF_INET6, 0, 0, "", ("2606:2800::1", port, 0, 0)), (socket.AF_INET, 0, 0, "", ("93.184.216.34", port))]

    monkeypatch.setattr(asyncio.get_event_loop_policy().new_event_loop().__class__, "getaddrinfo", fake, raising=False)
    assert asyncio.run(default_resolver("good.com", 443)) == ["93.184.216.34", "2606:2800::1"]


def test_all_validated_ips_failing_to_connect_is_a_friendly_error():
    def handler(request):
        raise httpx.ConnectError("sem rota")
    net = _Net(handler=handler)
    with pytest.raises(SafeFetchError) as exc:
        _run(net, "https://good.com")
    assert exc.value.reason == "sem_conexao"
