import httpx
from htmltext import html_to_text
from urllib.parse import urlparse

# Who we are, for websites that ask (Wikipedia does). Lives in identity.py, which is never published.
try:
    from identity import USER_AGENT
except ImportError:
    USER_AGENT = "local-agent-fetch/1.0"   # fallback: Wikipedia will probably refuse this

ALLOWED_HOSTS = {"en.wikipedia.org", "www.novusdata.news"}
REGIONS = {"en.wikipedia.org": "mw-content-text"}


def is_allowed(url: str) -> bool:
    try:
        parts = urlparse(url)
        return (parts.scheme == "https" and parts.hostname in ALLOWED_HOSTS
                and parts.port in (None, 443))   # same host on another port is a different service
    except ValueError:
        return False


def fetch_page(url: str) -> str:
    """Fetch the text of a web page from an allowed site

    Args:
      url: The full https address of the page

    Returns:
      The first 2000 characters of the page
    """
    if not is_allowed(url):
        return "Error: site not allowed"
    try:
        r = httpx.get(url, timeout=10, follow_redirects=False, headers={"User-Agent": USER_AGENT})
    except httpx.HTTPError:
        return "Error: could not fetch that page"
    if r.is_redirect:
        return "Error: redirects are not followed"
    if r.status_code != 200:
        return f"Error: page returned status {r.status_code}"
    return html_to_text(r.text, REGIONS.get(urlparse(url).hostname))[:2000]
