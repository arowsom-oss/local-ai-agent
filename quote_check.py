"""Check that long quotations in an answer really appear in the text the agent read.

This does not make the model quote anything. It only catches a quotation that is not in
any page or file read this turn, so a made-up quote cannot pass as a source. The check is
a plain text match done in Python, so the model cannot talk its way past it.
"""
import re

MIN_QUOTE_WORDS = 4      # shorter quoted phrases are usually names or terms, not claims
MIN_FRAGMENT_WORDS = 3   # when a quote has "..." in it, each piece must be at least this long
MAX_SHOWN = 3            # how many unverified quotes the warning lists

QUOTED = re.compile(r'"([^"\n]+)"|“([^”\n]+)”')
CITATION_MARKER = re.compile(r'\[(?:\d+|[a-z]|citation needed|failed verification)\]', re.I)
ELLIPSIS = re.compile(r'\.\.\.|…')
SIMPLE = str.maketrans({'–': '-', '—': '-', '−': '-',
                        '‘': "'", '’': "'", '“': '"', '”': '"'})


def normalize(text):
    """Lowercase, straighten quotes and dashes, drop [3]-style markers, collapse spaces."""
    text = CITATION_MARKER.sub('', text.translate(SIMPLE)).lower()
    return ' '.join(text.split())


def _pieces(quote):
    """The parts of a quotation that must each appear on a page, split at any ellipsis."""
    pieces = []
    for part in ELLIPSIS.split(quote):
        part = normalize(part).strip(' ,;:.-')
        if len(part.split()) >= MIN_FRAGMENT_WORDS:
            pieces.append(part)
    return pieces


def find_unverified_quotes(answer, sources, user_text=""):
    """Quotations in answer that are not in any source text.

    sources:   the text the agent read this turn. With nothing read, there is nothing to
               check against, so nothing is flagged.
    user_text: the person's own message, so quoting the person back is not flagged.
    """
    if not isinstance(answer, str) or not sources:
        return []
    haystack = normalize("\n".join([s for s in sources if isinstance(s, str)] + [str(user_text)]))
    missing = []
    for match in QUOTED.finditer(answer):
        quote = match.group(1) or match.group(2)
        if len(quote.split()) < MIN_QUOTE_WORDS:
            continue
        if any(piece not in haystack for piece in _pieces(quote)):
            missing.append(quote)
    return missing


def warning(missing):
    """Plain-language note added after the answer when a quotation could not be verified."""
    shown = []
    for quote in missing[:MAX_SHOWN]:
        shown.append('"' + (quote if len(quote) <= 80 else quote[:77] + '...') + '"')
    more = len(missing) - len(shown)
    tail = f" and {more} more" if more > 0 else ""
    return ("\n\nNOT VERIFIED: " + str(len(missing)) + " quotation(s) in this answer were not found in "
            "any page the agent read this turn: " + "; ".join(shown) + tail + ". "
            "Treat the claims they support as unconfirmed.")
