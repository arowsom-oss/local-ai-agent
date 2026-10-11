import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

# ---- the rules (all enforced in code, not in a prompt) ------------------
DOWNLOAD_DIR = Path("C:/dev/agent/downloads")   # the ONLY place this tool writes
MAX_BYTES = 200 * 1024 * 1024                    # 200 MB hard limit
ALLOWED_HOSTS = {
    "en.wikipedia.org",
    "www.novusdata.news",
    # "upload.wikimedia.org",   # Wikipedia's images live here. Remove the # to allow them.
}
ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".pdf", ".png", ".jpg"}
WINDOWS_DEVICE_NAMES = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} \
                       | {f"LPT{i}" for i in range(1, 10)}
# Wikipedia wants a User-Agent that says who you are and how to contact you.
# That personal text lives in identity.py (one line: USER_AGENT = "..."), not in this file.
try:
    from identity import USER_AGENT
except ImportError:
    USER_AGENT = "local-agent-download/1.0"   # fallback: Wikipedia will probably refuse this


def safe_filename(name):
    """Keep only the last part of a path and only safe characters."""
    name = unquote(str(name)).replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip(".")
    path = Path(name)
    return path.stem[:80] + path.suffix[:10]


def open_unique(folder, name):
    """Create folder/<name>.part for writing. Never reuses a name that already exists.

    Returns (part_path, final_path, open_file)."""
    stem, suffix = Path(name).stem, Path(name).suffix
    for n in range(1000):
        final = folder / (name if n == 0 else f"{stem}_{n}{suffix}")
        part = final.with_name(final.name + ".part")
        if final.exists():
            continue
        try:
            return part, final, open(part, "xb")   # "x" = fail if the file already exists
        except FileExistsError:
            continue
    raise OSError("could not find a free file name")


def download_file(url: str, filename: str) -> str:
    """Download a file from an approved website into the downloads folder

    Args:
      url: The full https address of the file
      filename: A short file name with an extension, like report.pdf

    Returns:
      A message saying whether the file was saved
    """
    # 1. Is the address allowed?
    try:
        parsed = urlparse(str(url))
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        return "Error: that is not a valid address"
    if parsed.scheme != "https" or host not in ALLOWED_HOSTS or port not in (None, 443):
        return "Error: that address is not allowed"

    # 2. Is the file name allowed? (the code decides, not the model)
    name = safe_filename(str(filename).strip() or parsed.path)
    if not name or name.split(".")[0].upper() in WINDOWS_DEVICE_NAMES:
        return "Error: that file name is not allowed"
    if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
        return "Error: that file type is not allowed"

    # 3. Download, counting bytes as they arrive
    written = 0
    try:
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", str(url), follow_redirects=False, timeout=10,
                          headers={"User-Agent": USER_AGENT}) as r:
            if r.status_code == 403:
                return ("Error: the server answered 403 (forbidden). Some sites, like Wikipedia, "
                        "want a User-Agent with contact info: check identity.py")
            if r.status_code != 200:
                return f"Error: the server answered {r.status_code}"
            declared = r.headers.get("content-length", "")
            if declared.isdigit() and int(declared) > MAX_BYTES:
                return "Error: the file is too large"
            part_path, final_path, f = open_unique(DOWNLOAD_DIR, name)
            too_big = False
            with f:
                for chunk in r.iter_bytes(65536):
                    written += len(chunk)
                    if written > MAX_BYTES:
                        too_big = True
                        f.truncate(0)          # empty our own partial file; we never delete
                        break
                    f.write(chunk)
            if too_big:
                return "Error: the file is over the size limit, so it was not saved"
        part_path.rename(final_path)           # fails instead of overwriting
    except (httpx.HTTPError, httpx.InvalidURL, OSError):
        return "Error: the download failed"
    if final_path.name != name:
        return (f"Saved as {final_path.name} because {name} already exists (nothing was "
                f"overwritten). The download is complete ({written} bytes). Do not retry.")
    return (f"Saved {final_path.name} ({written} bytes) in the downloads folder. "
            "The download is complete.")
