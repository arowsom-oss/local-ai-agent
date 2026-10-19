import ipaddress
import socket
import time

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

# Sites you allowed for READ-ONLY use in this chat. Only agent_core adds to this, after you
# click Yes. It is NOT a tool parameter, so the model has no way to add a site itself.
session_hosts = set()
BLOCKED_ENDINGS = (".local", ".localhost", ".internal", ".lan", ".home", ".arpa")
MAX_PAGE_BYTES = 5_000_000
FETCH_TIMEOUT = 10.0


def check_new_site(url):
    """Could this URL even be OFFERED to you as a new site? Returns (host, None) or (None, reason).

    Refuses anything that points back at your own computer or home network. Making a
    program fetch those for you is an attack called SSRF (server-side request forgery)."""
    try:
        parts = urlparse(str(url))
        host = parts.hostname
        port = parts.port
    except ValueError:
        return None, "that is not a valid address"
    if parts.scheme != "https" or port not in (None, 443):
        return None, "only normal https addresses are allowed"
    if not host or not host.isascii() or "xn--" in host:
        return None, "that site name has unusual characters"       # look-alike letters, raw or encoded
    try:
        ipaddress.ip_address(host)
        return None, "raw IP addresses are not allowed"
    except ValueError:
        pass
    if host == "localhost" or host.endswith(BLOCKED_ENDINGS):
        return None, "that points to your own computer or network"
    if "." not in host or not host.rsplit(".", 1)[1].isalpha():
        return None, "that is not a normal website name"           # blocks tricks like 127.1
    return host, None


def safe_ip(host):
    """Look the site name up ONCE and return the IP to connect to. Raises ValueError if any
    address is private or local. DNS answers come from whoever owns the name, so they are
    attacker-controlled: one bad address and the whole site is refused, no picking."""
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        raise ValueError("could not find that site")
    ips = []
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])     # "%" = IPv6 zone, not part of the address
        if ip.version == 6 and ip.ipv4_mapped:                  # ::ffff:127.0.0.1 is really 127.0.0.1
            ip = ip.ipv4_mapped
        if not ip.is_global or ip.is_multicast:                 # Python calls multicast "global"
            raise ValueError("that site points to a private or local address")
        ips.append(ip)
    if not ips:
        raise ValueError("could not find that site")
    return ips[0]


def is_allowed(url: str) -> bool:
    try:
        parts = urlparse(url)
        return (parts.scheme == "https"
                and (parts.hostname in ALLOWED_HOSTS or parts.hostname in session_hosts)
                and parts.port in (None, 443))   # same host on another port is a different service
    except ValueError:
        return False


def fetch_page(url: str) -> str:
    """Fetch the text of a web page. A site that is not approved yet needs the person's OK first

    Args:
      url: The full https address of the page

    Returns:
      The first 2000 characters of the page
    """
    if not is_allowed(url):
        return "Error: site not allowed"
    host, problem = check_new_site(url)
    if problem or host is None:
        return f"Error: {problem or 'invalid website address'}"
    parts = urlparse(url)
    started = time.monotonic()
    try:
        ip = safe_ip(host)
    except ValueError as e:
        return f"Error: {e}"
    # Connect to the IP we just checked, so DNS can't be swapped between the check and
    # the request. That swap is called DNS rebinding.
    ip_text = f"[{ip}]" if ip.version == 6 else str(ip)
    pinned = parts._replace(netloc=ip_text).geturl()
    try:
        if time.monotonic() - started >= FETCH_TIMEOUT:
            return "Error: fetch timed out"
        with httpx.Client(timeout=FETCH_TIMEOUT, follow_redirects=False, trust_env=False) as client:
            with client.stream("GET", pinned,
                               headers={"User-Agent": USER_AGENT, "Host": host,
                                        "Accept-Encoding": "identity"},
                               extensions={"sni_hostname": host}) as r:
                if r.is_redirect:
                    return "Error: redirects are not followed"
                if r.status_code != 200:
                    return f"Error: page returned status {r.status_code}"
                if r.headers.get("content-encoding", "identity").lower() != "identity":
                    return "Error: compressed responses are not allowed"
                if "attachment" in r.headers.get("content-disposition", "").lower():
                    return "Error: attachments are not allowed"
                length = r.headers.get("content-length")
                if length is not None and (int(length) < 0 or int(length) > MAX_PAGE_BYTES):
                    return "Error: response exceeds 5 MB or has an invalid length"
                body = bytearray()
                for chunk in r.iter_raw(chunk_size=64 * 1024):
                    if time.monotonic() - started >= FETCH_TIMEOUT:
                        return "Error: fetch timed out"
                    if len(body) + len(chunk) > MAX_PAGE_BYTES:
                        return "Error: response exceeds 5 MB"
                    body.extend(chunk)
                if time.monotonic() - started >= FETCH_TIMEOUT:
                    return "Error: fetch timed out"
                try:
                    text = bytes(body).decode(r.encoding or "utf-8", errors="replace")
                except LookupError:
                    text = bytes(body).decode("utf-8", errors="replace")
    except (httpx.HTTPError, ValueError):
        return "Error: could not fetch that page"
    return html_to_text(text, REGIONS.get(host))[:2000]
