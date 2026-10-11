from urllib.parse import urlparse

ALLOWED_HOSTS = {"en.wikipedia.org", "www.novusdata.news"}


def is_allowed(url: str) -> bool:
    try:
        parts = urlparse(url)
        return parts.scheme == "https" and parts.hostname in ALLOWED_HOSTS
    except ValueError:
        return False


tests = [
    ("https://en.wikipedia.org/wiki/Dog", True),
    ("http://en.wikipedia.org/wiki/Dog", False),
    ("https://happywikipedia.org", False),
    ("https://evil.com/wikipedia.org", False),
    ("https://en.wikipedia.org@evil.com", False),
    ("https://EN.WIKIPEDIA.ORG/wiki/Dog", True),
    ("https://www.novusdata.news/", True),
    ("https://novusdata.news/", False),
    ("not a url", False),
]
for url, want in tests:
    got = is_allowed(url)
    print("OK  " if got == want else "FAIL", got, url)
