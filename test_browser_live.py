"""Real headed Chromium, with fake HTTPS responses and no Internet required.

Run: python -B test_browser_live.py
Needs installed Playwright/Chromium and HTTPX. Uses the real route handler,
real DOM extraction, dedicated thread, JS-disabled context and offline mode.
"""

import importlib.util
import ipaddress
from pathlib import Path
import sys
import threading
import types
from unittest.mock import patch

import httpx

HERE = Path(__file__).resolve().parent
fake_fetch = types.ModuleType("fetch")
fake_fetch.USER_AGENT = "offline-browser-integration-test"
fake_fetch.ALLOWED_HOSTS = {"fixture.example"}
fake_fetch.session_hosts = set()


def check_site(url):
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in {"fixture.example", "other.example"}:
        return None, "Test URL refused"
    return parts.hostname, None


fake_fetch.check_new_site = check_site
fake_fetch.safe_ip = lambda host: ipaddress.ip_address("93.184.216.34")
spec = importlib.util.spec_from_file_location("live_browser_target", HERE / "browser_tool.py")
browser = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = browser
with patch.dict(sys.modules, {"fetch": fake_fetch}):
    spec.loader.exec_module(browser)

HTML = b"""<!doctype html><html><head><title>Offline browser test</title></head>
<body><h1>Library</h1>
<a href='/next'>Next</a><a href='/hidden' style='display:none'>Invisible</a>
<input type='password' aria-label='Secret password'>
<form action='/find?discard=this#fragment' method='get'>
<input type='search' name='q' aria-label='Library search'></form>
<form action='/post' method='post'><input type='text' name='q' aria-label='POST search'></form>
<form action='/find'><input type='search' aria-label='Nameless'></form>
<script>document.body.innerHTML = 'JAVASCRIPT RAN';</script>
<img src='/image.png'></body></html>"""


class BodyStream(httpx.SyncByteStream):
    def __init__(self, content):
        self.content = content

    def __iter__(self):
        yield self.content


seen = []


def network(request):
    # HTTPX connects to a pinned address while preserving the site's identity.
    assert request.url.host == "93.184.216.34"
    assert request.headers["Host"] == "fixture.example"
    assert request.extensions["sni_hostname"] == "fixture.example"
    assert request.method == "GET"
    seen.append(str(request.url))
    if request.url.path == "/redirect":
        return httpx.Response(302, headers={"Location": "https://other.example/"}, stream=BodyStream(b""))
    body = HTML if request.url.path == "/" else b"<html><body><h1>Search results: dog</h1></body></html>"
    return httpx.Response(200, headers={"Content-Type": "text/html"}, stream=BodyStream(body))


real_client = httpx.Client


def client_factory(**options):
    assert options["follow_redirects"] is False
    assert options["trust_env"] is False
    return real_client(transport=httpx.MockTransport(network), **options)


def read_number(text, label):
    import re
    match = re.search(r'\[(\d+)\] (?:link|search box|text box) "' + re.escape(label) + '"', text)
    assert match, (label, text)
    return int(match.group(1))


if __name__ == "__main__":
    with patch.object(browser.httpx, "Client", side_effect=client_factory):
        try:
            assert browser.browser_open("https://fixture.example/") == "Page opened."
            text = browser.browser_read()
            assert text.startswith(browser.TEXT_PREFIX), text
            assert "Library" in text and "JAVASCRIPT RAN" not in text
            assert "password field(s): locked, no number" in text
            assert 'link "Invisible"' not in text
            link = read_number(text, "Next")
            search = read_number(text, "Library search")
            post = read_number(text, "POST search")
            nameless = read_number(text, "Nameless")
            assert browser.search_url_for(post, "dog")[0] is None
            assert browser.search_url_for(nameless, "dog")[0] is None
            assert browser.search_url_for(search, "dog") == (
                "https://fixture.example/find?q=dog", "Library search",
            )
            # Snapshot numbers cannot be reused on another read, even at the same URL.
            text2 = browser.browser_read()
            new_search = read_number(text2, "Library search")
            assert new_search != search
            assert browser.search_url_for(search, "dog")[0] is None
            assert browser.browser_search(new_search, "dog") == "Page opened."
            assert browser.link_for(link)[0] is None
            assert "Search results: dog" in browser.browser_read()
            assert not any("image.png" in url for url in seen)
            before_redirect = len(seen)
            assert browser.browser_open("https://fixture.example/redirect").startswith("Error:")
            assert len(seen) == before_redirect + 1

            results = []

            def turn():
                results.append(browser.browser_open("https://fixture.example/"))
                results.append(browser.browser_read())

            # Each turn really has a fresh caller thread; the worker remains the owner.
            for _ in range(2):
                thread = threading.Thread(target=turn)
                thread.start()
                thread.join(timeout=20)
                assert not thread.is_alive()
            assert results[0] == results[2] == "Page opened.", results
            assert results[1].startswith(browser.TEXT_PREFIX) and results[3].startswith(browser.TEXT_PREFIX)
            print("PASS real Chromium: offline routing, DOM/form extraction, JS off, password/hidden exclusion,")
            print("     URL encoding, POST/name refusal, stale numbers, redirect blocking and caller threads.")
        finally:
            assert browser.close_browser() == "Browser closed."
