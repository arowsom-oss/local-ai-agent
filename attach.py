from pathlib import Path

from download import safe_filename, open_unique, WINDOWS_DEVICE_NAMES

ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".py"}   # plain text only; these are READ, never run
MAX_COPY_BYTES = 1024 * 1024                          # 1 MB


def copy_in(src, folder):
    """Copy a file the PERSON picked into folder. Returns the new file name.

    Raises ValueError with a plain-English reason if anything is wrong.
    The original is only ever opened for reading."""
    src = Path(src)
    if not src.is_file():
        raise ValueError("that is not a file")

    # the code decides the name and the type, not the model
    name = safe_filename(src.name)
    if not name or name.split(".")[0].upper() in WINDOWS_DEVICE_NAMES:
        raise ValueError("that file name is not allowed")
    if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("that file type is not allowed (only .txt .md .csv .py)")

    try:
        with open(src, "rb") as f:
            data = f.read(MAX_COPY_BYTES + 1)   # read at most the limit; never trust an earlier size check
    except OSError:
        raise ValueError("could not read that file")
    if len(data) > MAX_COPY_BYTES:
        raise ValueError("that file is too big (limit 1 MB)")
    if b"\x00" in data:
        raise ValueError("that does not look like a plain text file")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("that is not plain UTF-8 text")

    try:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        part, final, f = open_unique(folder, name)   # never overwrites an existing file
        with f:
            f.write(data)
        part.rename(final)
    except OSError:
        raise ValueError("could not save the copy")
    return final.name
