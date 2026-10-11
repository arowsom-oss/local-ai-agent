from html.parser import HTMLParser

SKIP_TAGS = {"script", "style", "noscript", "table"}


class _TextExtractor(HTMLParser):
    def __init__(self, region_id=None):
        super().__init__()
        self.region_id = region_id
        # With no region, keep everything (depth is unused).
        self.in_region = region_id is None
        self.depth = 0
        self.skip_depth = 0
        self.in_title = False
        self.title = ""
        self.description = ""
        self.parts = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in SKIP_TAGS:
            self.skip_depth += 1
        elif tag == "title":
            self.in_title = True
        elif tag == "meta" and a.get("name") == "description":
            self.description = a.get("content") or ""
        if self.region_id is not None and tag == "div":
            if a.get("id") == self.region_id:
                self.depth = 1
            elif self.depth > 0:
                self.depth += 1

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif tag == "title":
            self.in_title = False
        if self.region_id is not None and tag == "div" and self.depth > 0:
            self.depth -= 1

    def handle_data(self, data):
        if self.in_title:
            self.title += data
            return
        keep = self.in_region or self.depth > 0
        if keep and self.skip_depth == 0:
            text = data.strip()
            if text:
                self.parts.append(text)


def html_to_text(html: str, region_id=None) -> str:
    p = _TextExtractor(region_id)
    p.feed(html)
    p.close()
    head = []
    if p.title.strip():
        head.append("Title: " + p.title.strip())
    if p.description.strip():
        head.append("Description: " + p.description.strip())
    return "\n".join(head + p.parts)
