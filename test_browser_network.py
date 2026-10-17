"""Offline tests: run with Python 3.12, plain asserts, no pytest required.

The real fetch.py and Playwright are neither imported nor started. HTTPX is
installed but its Client is always replaced. Run without Python's -O option.
"""

import importlib.util
import ipaddress
from pathlib import Path
import socket
import sys
import threading
import types
from unittest.mock import patch
from urllib.parse import urlsplit


# A deliberately small contract fake, NOT a replacement for your fetch.py.
fake_fetch = types.ModuleType("fetch")
fake_fetch.ALLOWED_HOSTS = {"approved.example"}
fake_fetch.session_hosts = set()
fake_fetch.USER_AGENT = "offline-test-agent"


def check_url(url):
    try:
        parts = urlsplit(url)
        host = parts.hostname
        if (parts.scheme != "https" or not host or parts.port not in (None, 443)
                or parts.username is not None or parts.password is not None
                or not host.isascii() or host.startswith("xn--")
                or host == "localhost" or host.endswith(".local")):
            return None, "Rejected URL"
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return host, None
        return None, "Raw IP rejected"
    except Exception:
        return None, "Invalid URL"


fake_fetch.check_new_site = check_url
fake_fetch.safe_ip = lambda host: ipaddress.ip_address("93.184.216.34")
spec = importlib.util.spec_from_file_location(
    "browser_tool_under_test", Path(__file__).with_name("browser_tool.py")
)
bt = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bt  # dataclasses resolves its module during import.
with patch.dict(sys.modules, {"fetch": fake_fetch}):
    spec.loader.exec_module(bt)


class FakeRoute:
    def __init__(self, url="https://approved.example/page", method="GET",
                 kind="document", main=True, navigation=True):
        self.aborted = False
        self.fulfilled = None
        self.request = types.SimpleNamespace(
            url=url, method=method, resource_type=kind,
            frame=types.SimpleNamespace(parent_frame=None if main else object()),
            is_navigation_request=lambda: navigation,
        )

    def abort(self, code):
        assert code == "blockedbyclient"
        self.aborted = True

    def fulfill(self, **kwargs):
        assert not self.aborted
        self.fulfilled = kwargs

    def continue_(self, **kwargs):
        raise AssertionError("Chromium must never receive permission to fetch")


class FakeResponse:
    def __init__(self, chunks=(b"<body>Hello</body>",), status=200, headers=None):
        self.status_code = status
        self.headers = {"content-type": "text/html"} if headers is None else headers
        self.chunks = chunks
        self.iterated = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_raw(self, chunk_size):
        assert chunk_size == 64 * 1024
        self.iterated = True
        yield from self.chunks


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.options = None
        self.calls = []

    def factory(self, **kwargs):
        self.options = kwargs
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def stream(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


def route_case(route=None, response=None, safe_ip=None):
    session = bt._Session()
    session.page_host = "approved.example"
    route = route or FakeRoute()
    client = FakeClient(response or FakeResponse())
    with patch.object(bt.httpx, "Client", side_effect=client.factory):
        if safe_ip is None:
            result = session.handle_route(route)
        else:
            with patch.object(fake_fetch, "safe_ip", side_effect=safe_ip):
                result = session.handle_route(route)
    assert isinstance(result, str)
    return session, route, client


def test_post_blocked():
    session, route, client = route_case(FakeRoute(method="POST"))
    assert route.aborted and session.blocked == 1 and not client.calls


def test_blocked_resource_types():
    for kind in ("image", "media", "font", "websocket", "eventsource", "script"):
        session, route, client = route_case(FakeRoute(kind=kind))
        assert route.aborted and session.blocked == 1 and not client.calls


def test_main_frame_unapproved():
    session, route, client = route_case(FakeRoute(url="https://unknown.example/"))
    assert route.aborted and session.blocked == 1 and not client.calls


def test_private_ip_frame():
    session, route, client = route_case(FakeRoute(url="https://192.168.1.1/", main=False))
    assert route.aborted and session.blocked == 1 and not client.calls


def test_dns_rejection():
    def denied(host):
        raise ValueError("At least one DNS address is private")

    session, route, client = route_case(safe_ip=denied)
    assert route.aborted and session.blocked == 1 and not client.calls


def test_pinned_ip_host_sni_and_headers():
    looked_up = []

    def safe(host):
        looked_up.append(host)
        return ipaddress.ip_address("93.184.216.34")

    response = FakeResponse(headers={
        "content-type": "text/html", "content-length": "18",
        "set-cookie": "secret=x", "connection": "keep-alive",
        "refresh": "0;url=https://evil.example/", "alt-svc": "h3=evil.example:443",
    })
    session, route, client = route_case(response=response, safe_ip=safe)
    assert looked_up == ["approved.example"]
    assert not route.aborted and session.blocked == 0
    assert route.fulfilled["body"] == b"<body>Hello</body>"
    args, kwargs = client.calls[0]
    assert args == ("GET", "https://93.184.216.34/page")
    assert kwargs["headers"] == {
        "Host": "approved.example", "User-Agent": "offline-test-agent",
        "Accept-Encoding": "identity",
    }
    assert kwargs["extensions"] == {"sni_hostname": "approved.example"}
    assert client.options == {
        "timeout": 10.0, "follow_redirects": False, "trust_env": False,
        "verify": True, "http2": False,
    }
    for name in ("set-cookie", "connection", "content-length", "refresh", "alt-svc"):
        assert name not in route.fulfilled["headers"]
    assert "sandbox" in route.fulfilled["headers"]["content-security-policy"]


def test_ipv6_url():
    _, route, client = route_case(
        FakeRoute(url="https://approved.example:443/path?q=1#fragment"),
        safe_ip=lambda host: ipaddress.ip_address("2606:4700:4700::1111"),
    )
    assert not route.aborted
    assert client.calls[0][0][1] == "https://[2606:4700:4700::1111]/path?q=1"


def test_subresource_and_session_approval():
    _, route, _ = route_case(FakeRoute(
        url="https://cdn.example/style.css", kind="stylesheet", navigation=False,
    ))
    assert route.aborted
    _, route, _ = route_case(FakeRoute(url="https://frame.example/", main=False))
    assert route.aborted
    with patch.object(fake_fetch, "session_hosts", {"temporary.example"}):
        session = bt._Session()
        session.page = types.SimpleNamespace(goto=lambda *a, **kw: None)
        with patch.object(session, "start", return_value="Browser ready."):
            assert session.open("https://temporary.example/") == "Page opened."
        route = FakeRoute(url="https://temporary.example/")
        with patch.object(bt.httpx, "Client", side_effect=FakeClient(FakeResponse()).factory):
            assert session.handle_route(route) == "Fulfilled."
        assert route.fulfilled is not None


def test_no_page_scope_fails_closed_before_dns():
    session, route = bt._Session(), FakeRoute()
    with patch.object(fake_fetch, "safe_ip", side_effect=AssertionError("must not resolve")), \
            patch.object(bt.httpx, "Client", side_effect=AssertionError("must not fetch")):
        assert session.handle_route(route) == "Blocked."
    assert route.aborted and session.page_requests == 1


def test_third_party_approved_hosts_subdomains_and_frames_blocked_before_dns():
    for host in ("cdn.example", "sub.approved.example", "approved.example.evil.example"):
        with patch.object(fake_fetch, "ALLOWED_HOSTS", {"approved.example", host}), \
                patch.object(fake_fetch, "session_hosts", {host}), \
                patch.object(fake_fetch, "safe_ip", side_effect=AssertionError("must not resolve")):
            for kind, navigation, main in (("stylesheet", False, False), ("document", True, False),
                                            ("document", True, True)):
                session, route, client = route_case(FakeRoute(
                    url=f"https://{host}/", kind=kind, navigation=navigation, main=main))
                assert route.aborted and not client.calls and session.blocked == 1


def test_same_host_resources_and_frames_share_pinned_fetch_path():
    for kind, navigation in (("stylesheet", False), ("document", True)):
        session, route, client = route_case(FakeRoute(
            url="https://approved.example/resource", kind=kind, main=False, navigation=navigation))
        assert route.fulfilled and session.page_requests == 1
        assert session.page_bytes == len(route.fulfilled["body"])
        assert client.calls[0][0][1] == "https://93.184.216.34/resource"


def test_request_limit_includes_blocked_routes_and_websockets():
    session = bt._Session()
    session.page_host = "approved.example"
    client = FakeClient(FakeResponse())
    with patch.object(bt, "MAX_PAGE_REQUESTS", 3), \
            patch.object(bt.httpx, "Client", side_effect=client.factory):
        assert session.handle_route(FakeRoute(kind="image")) == "Blocked."
        ws = types.SimpleNamespace(close=lambda: None)
        assert session.block_websocket(ws) == "Blocked."
        assert session.handle_route(FakeRoute(main=False)) == "Fulfilled."
        route = FakeRoute()
        assert session.handle_route(route) == "Blocked."
        assert route.aborted and session.budget_exhausted and session.page_requests == 4
        assert len(client.calls) == 1
        assert session.handle_route(FakeRoute()) == "Blocked."
        assert len(client.calls) == 1


def test_default_request_budget_stops_dns_and_fetch_after_100():
    assert bt.MAX_PAGE_REQUESTS == 100 and bt.MAX_PAGE_BYTES == 10_000_000
    session = bt._Session()
    session.page_host = "approved.example"
    client = FakeClient(FakeResponse())
    with patch.object(bt.httpx, "Client", side_effect=client.factory), \
            patch.object(fake_fetch, "safe_ip", return_value=ipaddress.ip_address("93.184.216.34")) as dns:
        for _ in range(100):
            assert session.handle_route(FakeRoute(main=False)) == "Fulfilled."
        assert session.handle_route(FakeRoute(main=False)) == "Blocked."
        assert session.page_requests == 101 and session.budget_exhausted
        assert len(client.calls) == dns.call_count == 100


def test_aggregate_byte_limit_spans_responses_and_frames():
    session = bt._Session()
    session.page_host = "approved.example"
    client = FakeClient(FakeResponse(chunks=(b"1234",)))
    with patch.object(bt, "MAX_PAGE_BYTES", 10), \
            patch.object(bt.httpx, "Client", side_effect=client.factory):
        assert session.handle_route(FakeRoute()) == "Fulfilled."
        assert session.handle_route(FakeRoute(main=False)) == "Fulfilled."
        client.response = FakeResponse(chunks=(b"12",))
        assert session.handle_route(FakeRoute(main=False)) == "Fulfilled."
        assert session.page_bytes == 10
        assert session.handle_route(FakeRoute()) == "Blocked."
        assert len(client.calls) == 3


def test_declared_or_streamed_page_byte_exhaustion_is_sticky():
    for response in (FakeResponse(chunks=(b"12345",), headers={"content-length": "5"}),
                     FakeResponse(chunks=(b"12345",))):
        session = bt._Session()
        session.page_host = "approved.example"
        session.page_bytes = 6
        client = FakeClient(response)
        with patch.object(bt, "MAX_PAGE_BYTES", 10), \
                patch.object(bt.httpx, "Client", side_effect=client.factory):
            route = FakeRoute(main=False)
            assert session.handle_route(route) == "Blocked."
            assert route.fulfilled is None and session.budget_exhausted
            if "content-length" in response.headers:
                assert not response.iterated and session.page_bytes == 6
            else:
                assert session.page_bytes == 11
            assert session.handle_route(FakeRoute()) == "Blocked."
            assert len(client.calls) == 1


def test_aborted_response_bytes_are_not_refunded():
    session = bt._Session()
    session.page_host = "approved.example"

    def broken_stream(chunk_size):
        yield b"1234"
        raise RuntimeError("connection lost")

    response = FakeResponse()
    response.iter_raw = broken_stream
    client = FakeClient(response)
    with patch.object(bt.httpx, "Client", side_effect=client.factory):
        assert session.handle_route(FakeRoute()) == "Blocked."
    assert session.page_bytes == 4


def test_read_and_navigation_preserve_budget_and_explicit_open_resets_it():
    session = bt._Session()
    main_frame = object()
    session.page = types.SimpleNamespace(
        main_frame=main_frame, url="https://approved.example/", goto=lambda *a, **kw: None,
        locator=lambda selector: types.SimpleNamespace(inner_text=lambda **kw: "x" * 9000))
    session.page_host = "approved.example"
    session.page_requests, session.page_bytes, session.budget_exhausted = 101, 10_000_001, True
    with patch.object(session, "list_elements", return_value=""), \
            patch.object(session, "start", return_value="Browser ready."):
        session.navigated(main_frame)
        text = session.read()
        assert len(text) <= bt.MAX_TEXT_CHARS and text.startswith(bt.TEXT_PREFIX)
        assert "101/100 requests" in text and "exhausted" in text
        assert session.page_requests == 101 and session.page_bytes == 10_000_001
        assert session.open("https://unknown.example/").startswith("Error:")
        assert session.budget_exhausted  # Refused opens do not renew anything.
        assert session.open("https://approved.example/") == "Page opened."
        assert session.page_requests == session.page_bytes == 0 and not session.budget_exhausted
        assert session.page_host == "approved.example"


def test_per_response_oversize_still_charges_received_bytes():
    session = bt._Session()
    session.page_host = "approved.example"
    client = FakeClient(FakeResponse(chunks=(b"1234", b"5")))
    with patch.object(bt, "MAX_RESPONSE_BYTES", 4), \
            patch.object(bt.httpx, "Client", side_effect=client.factory):
        route = FakeRoute()
        assert session.handle_route(route) == "Blocked."
        assert session.page_bytes == 5 and route.fulfilled is None


def test_response_size_cap():
    response = FakeResponse(headers={"content-length": str(bt.MAX_RESPONSE_BYTES + 1)})
    session, route, _ = route_case(response=response)
    assert route.aborted and not response.iterated and session.blocked == 1
    # No Content-Length: streamed bytes are still capped before being appended.
    response = FakeResponse(chunks=(b"x" * bt.MAX_RESPONSE_BYTES, b"y"))
    _, route, _ = route_case(response=response)
    assert route.aborted and route.fulfilled is None
    _, route, _ = route_case(response=FakeResponse(chunks=(b"x" * bt.MAX_RESPONSE_BYTES,)))
    assert len(route.fulfilled["body"]) == bt.MAX_RESPONSE_BYTES


def test_redirects_compression_downloads_and_bad_length_blocked():
    for response in (
        FakeResponse(status=301, headers={"location": "https://192.168.1.1/"}),
        FakeResponse(status=302), FakeResponse(status=307), FakeResponse(status=308),
        FakeResponse(headers={"content-encoding": "gzip"}),
        FakeResponse(headers={"content-disposition": "attachment; filename=x"}),
        FakeResponse(headers={"content-length": "invalid"}),
    ):
        session, route, _ = route_case(response=response)
        assert route.aborted and route.fulfilled is None and session.blocked == 1


def test_transport_failure_and_abort_failure_do_not_escape():
    with patch.object(bt.httpx, "Client", side_effect=RuntimeError("network failed")):
        session = bt._Session()
        route = FakeRoute()
        assert session.handle_route(route) == "Blocked."
        assert route.aborted
    route = FakeRoute(method="POST")
    route.abort = lambda code: (_ for _ in ()).throw(RuntimeError("page closed"))
    assert session.handle_route(route) == "Blocked."








def test_public_validation_errors_and_no_popup():
    for url in ("file:///C:/secret.txt", "http://approved.example/",
                "https://192.168.1.1/", "https://unknown.example/", None):
        assert bt.browser_open(url).startswith("Error: ")
    assert bt._worker is None




def test_worker_survives_tool_error():
    with patch.object(bt._Session, "open", side_effect=RuntimeError("example failure")):
        try:
            assert bt.browser_open("https://approved.example/").startswith("Error: RuntimeError")
            assert bt.browser_read() == "Error: No page is open."
            assert bt._worker.thread.is_alive()
        finally:
            assert bt.close_browser() == "Browser closed."


def test_command_timeout_retires_worker():
    entered = threading.Event()
    release = threading.Event()

    def slow_open(session, url):
        entered.set()
        release.wait(timeout=5)
        return "Page opened."

    with patch.object(bt._Session, "open", slow_open), patch.object(bt, "COMMAND_TIMEOUT", 0.1):
        try:
            assert "timed out" in bt.browser_open("https://approved.example/")
            assert entered.is_set()
            worker = bt._worker
            assert worker.stop.is_set()
            assert "still stopping" in bt.browser_read()
            assert bt._worker is worker
        finally:
            release.set()
            worker.thread.join(timeout=5)
            assert not worker.thread.is_alive()
            assert bt.close_browser() == "Browser closed."


def no_network(*args, **kwargs):
    raise AssertionError("Offline test attempted real networking")


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    # Defense in depth: accidental real network attempts fail the test.
    with patch.object(socket, "socket", side_effect=no_network), \
            patch.object(socket, "getaddrinfo", side_effect=no_network):
        for test in tests:
            test()
            print(f"PASS {test.__name__}")
    print(f"All {len(tests)} offline tests passed.")
