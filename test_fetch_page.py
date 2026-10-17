"""Plain-assert offline tests for the real fetch.py with fake HTTP and parser.

No Internet, Ollama, Playwright or third-party Python packages are required.
The unchanged URL/DNS helpers are tested directly, not replaced by weaker fakes.
"""
import importlib.util
import ipaddress
from pathlib import Path
import socket
import sys
import types
from unittest.mock import patch


class HTTPError(Exception):
    pass


fake_httpx = types.ModuleType("httpx")
fake_httpx.HTTPError = HTTPError
fake_httpx.Client = None
fake_htmltext = types.ModuleType("htmltext")
fake_htmltext.html_to_text = lambda text, region=None: text
fake_identity = types.ModuleType("identity")
fake_identity.USER_AGENT = "offline-fetch-test"
spec = importlib.util.spec_from_file_location("fetch_under_test", Path(__file__).with_name("fetch.py"))
fetch = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"httpx": fake_httpx, "htmltext": fake_htmltext, "identity": fake_identity}):
    spec.loader.exec_module(fetch)


class Response:
    def __init__(self, chunks=(b"Hello",), headers=None, status=200, encoding="utf-8"):
        self.chunks, self.headers = chunks, headers or {}
        self.status_code, self.encoding = status, encoding
        self.is_redirect = 300 <= status < 400
        self.consumed = 0
        self.iterated = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_raw(self, chunk_size):
        assert chunk_size == 64 * 1024
        self.iterated = True
        for chunk in self.chunks:
            self.consumed += len(chunk)
            yield chunk


class Client:
    def __init__(self, response):
        self.response, self.options, self.calls = response, None, []

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


def run(response=None, url="https://approved.example/path?q=hello"):
    response = response or Response()
    client = Client(response)
    with patch.object(fetch, "ALLOWED_HOSTS", {"approved.example"}), \
            patch.object(fetch, "safe_ip", return_value=ipaddress.ip_address("93.184.216.34")) as dns, \
            patch.object(fake_httpx, "Client", side_effect=client.factory):
        result = fetch.fetch_page(url)
    assert isinstance(result, str)
    return result, client, response, dns


def test_valid_fetch_keeps_ip_host_sni_and_disables_proxies():
    result, client, _, dns = run()
    assert result == "Hello"
    dns.assert_called_once_with("approved.example")
    args, kwargs = client.calls[0]
    assert args == ("GET", "https://93.184.216.34/path?q=hello")
    assert kwargs["headers"] == {"User-Agent": "offline-fetch-test", "Host": "approved.example", "Accept-Encoding": "identity"}
    assert kwargs["extensions"] == {"sni_hostname": "approved.example"}
    assert client.options == {"timeout": 10.0, "follow_redirects": False, "trust_env": False}


def test_declared_oversize_rejected_before_body():
    result, _, response, _ = run(Response(headers={"content-length": "5000001"}))
    assert result.startswith("Error:") and not response.iterated


def test_streaming_cap_without_content_length():
    response = Response(chunks=(b"a" * 5_000_000, b"b", b"must not read"))
    result, _, _, _ = run(response)
    assert result == "Error: response exceeds 5 MB"
    assert response.consumed == 5_000_001  # Over-limit chunk is never buffered/parsed.
    result, _, _, _ = run(Response(chunks=(b"a" * 5_000_000,)))
    assert result == "a" * 2000


def test_compressed_or_attachment_response_refused():
    for headers in ({"content-encoding": "gzip"}, {"content-encoding": "br"},
                    {"content-disposition": "attachment; filename=x"}):
        result, _, response, _ = run(Response(headers=headers))
        assert result.startswith("Error:") and not response.iterated


def test_redirect_bad_status_and_bad_length_refused():
    for response in (Response(status=302), Response(status=404),
                     Response(headers={"content-length": "not a number"}),
                     Response(headers={"content-length": "-1"})):
        result, _, _, _ = run(response)
        assert result.startswith("Error:") and not response.iterated


def test_unapproved_host_never_reaches_dns_or_http():
    result, client, _, dns = run(url="https://other.example/")
    assert result.startswith("Error:") and not client.calls
    dns.assert_not_called()


def test_timeout_and_http_errors_are_strings():
    with patch.object(fetch.time, "monotonic", side_effect=[0, 0, 11]):
        result, _, _, _ = run()
    assert result == "Error: fetch timed out"
    with patch.object(fake_httpx, "Client", side_effect=HTTPError("network failed")), \
            patch.object(fetch, "ALLOWED_HOSTS", {"approved.example"}), \
            patch.object(fetch, "safe_ip", return_value=ipaddress.ip_address("93.184.216.34")):
        assert fetch.fetch_page("https://approved.example/").startswith("Error:")


def test_encoding_fallback_and_normal_unicode():
    for encoding in ("utf-8", "unknown-charset"):
        result, _, _, _ = run(Response(chunks=("café".encode(),), encoding=encoding))
        assert result == "café"


def test_real_url_policy_rejects_private_and_non_https_forms():
    for url in ("file:///C:/x", "http://approved.example/", "https://192.168.1.1/",
                "https://localhost/", "https://server.local/", "https://server.internal/",
                "https://xn--example.com/", "https://exämple.com/", "https://approved.example:444/"):
        host, problem = fetch.check_new_site(url)
        assert host is None and problem


def test_real_dns_policy_rejects_any_private_answer():
    for ip in ("192.168.1.1", "127.0.0.1", "169.254.1.1", "::1", "::ffff:127.0.0.1", "224.0.0.1"):
        answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
                   (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]
        with patch.object(socket, "getaddrinfo", return_value=answers) as dns:
            try:
                fetch.safe_ip("approved.example")
            except ValueError:
                pass
            else:
                raise AssertionError("A private DNS answer was accepted")
            assert dns.call_count == 1


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    with patch.object(socket, "socket", side_effect=AssertionError("No network allowed")), \
            patch.object(socket, "getaddrinfo", side_effect=AssertionError("No network allowed")):
        for test in tests:
            test()
            print("PASS", test.__name__)
    print(f"All {len(tests)} offline fetch tests passed.")
