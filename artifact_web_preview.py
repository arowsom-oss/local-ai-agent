"""Static HTML/CSS -> pixels only. Never a model tool or a general code runner."""
from html import escape
from html.parser import HTMLParser
import re
import threading
import time

from artifacts import MAX_TEXT
from process_guard import Worker

PREVIEW_URL = 'https://artifact-preview.invalid/'
VIEWPORT = {'width': 800, 'height': 1000}
CSP = ("sandbox; default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; "
       "img-src 'none'; font-src 'none'; connect-src 'none'; frame-src 'none'; "
       "object-src 'none'; media-src 'none'; base-uri 'none'; form-action 'none'")
_ALLOWED = set(('html head body title style main section article aside header footer nav '
                'div span h1 h2 h3 h4 h5 h6 p br hr strong em b i u small blockquote '
                'pre code ul ol li dl dt dd a button input textarea label form '
                'table thead tbody tfoot tr th td caption figure figcaption details summary').split())
_DROP = {'script', 'iframe', 'object', 'embed', 'svg', 'math', 'template', 'noscript'}
_ATTRS = {'class', 'id', 'style', 'title', 'lang', 'dir', 'placeholder', 'value',
          'rows', 'cols', 'colspan', 'rowspan', 'disabled', 'checked', 'aria-label'}
_render_lock = threading.Lock()


def html_source(content):
    """Recognize bounded HTML documents/fragments; do not guess Python/JS execution."""
    if not isinstance(content, str) or not 1 <= len(content) <= MAX_TEXT:
        return None
    source = content.strip()
    if source.startswith('```html\n') and source.endswith('```'):
        source = source[8:-3].strip()
    if re.match(r'<(?:!doctype\s+html\b|html\b|head\b|body\b|main\b|section\b|'
                r'div\b|article\b|header\b|h[1-6]\b|p\b|style\b|form\b|table\b)', source, re.I):
        return source
    return None


class _StaticHTML(HTMLParser):
    """Reduce markup to display elements. Network/CSP gates remain independent."""
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts, self.drop, self.nodes = [], None, 0
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        self.nodes += 1
        if self.nodes > 2500:
            raise ValueError('HTML preview exceeds 2500 elements')
        if self.drop:
            return
        if tag in _DROP:
            self.drop = tag
            return
        if tag not in _ALLOWED:
            return
        safe = []
        for name, value in attrs:
            if name in _ATTRS and value is not None:
                safe.append(' ' + name + '="' + escape(value, quote=True) + '"')
            elif name == 'type' and tag in {'input', 'button'} and value in {'text', 'search', 'button', 'checkbox', 'radio'}:
                safe.append(' type="' + value + '"')
        self.parts.append('<' + tag + ''.join(safe) + '>')
        self.in_style = tag == 'style'

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.drop:
            if tag == self.drop:
                self.drop = None
            return
        if tag in _ALLOWED:
            self.parts.append('</' + tag + '>')
        if tag == 'style':
            self.in_style = False

    def handle_data(self, data):
        if not self.drop:
            self.parts.append(data if self.in_style else escape(data))

    def handle_entityref(self, name):
        if not self.drop:
            self.parts.append('&' + name + ';')

    def handle_charref(self, name):
        if not self.drop:
            self.parts.append('&#' + name + ';')


def static_document(content):
    source = html_source(content)
    if source is None:
        raise ValueError('Visual preview supports HTML/CSS only; use Code for this draft')
    parser = _StaticHTML()
    parser.feed(source)
    parser.close()
    return '<!doctype html>\n' + ''.join(parser.parts)


def render_document(document, playwright):
    """Fixed browser policy; injectable Playwright solely for offline tests."""
    blocked = [0]
    served = [False]
    browser = playwright.chromium.launch(headless=True, chromium_sandbox=True,
        args=['--disable-background-networking', '--disable-component-update', '--disable-sync',
              '--disable-extensions', '--no-first-run', '--disable-gpu'],
        proxy={'server': 'http://127.0.0.1:9', 'bypass': '<-loopback>'})
    try:
        context = browser.new_context(java_script_enabled=False, accept_downloads=False,
            service_workers='block', permissions=[], offline=True, viewport=VIEWPORT,
            device_scale_factor=1)
        page = context.new_page()
        def intercept(route):
            request = route.request
            if (not served[0] and request.url == PREVIEW_URL and request.method == 'GET'
                    and request.is_navigation_request() and request.frame == page.main_frame):
                served[0] = True
                route.fulfill(status=200, headers={'Content-Type': 'text/html; charset=utf-8',
                    'Content-Security-Policy': CSP, 'Cache-Control': 'no-store',
                    'X-Content-Type-Options': 'nosniff'}, body=document)
            else:
                blocked[0] += 1
                route.abort()
        context.route('**/*', intercept)
        context.route_web_socket('**/*', lambda socket: socket.close())
        page.on('dialog', lambda dialog: dialog.dismiss())
        page.on('download', lambda download: download.cancel())
        page.on('filechooser', lambda chooser: chooser.set_files([]))
        context.on('page', lambda other: other.close() if other != page else None)
        page.goto(PREVIEW_URL, wait_until='load', timeout=5000)
        if not served[0] or page.url != PREVIEW_URL or len(context.pages) != 1:
            raise ValueError('Preview navigation changed unexpectedly')
        png = page.screenshot(type='png', full_page=False, animations='disabled',
                              caret='hide', timeout=5000)
        if not isinstance(png, bytes) or not 1 <= len(png) <= 8_000_000:
            raise ValueError('Preview pixels exceed the size limit')
        return {'png': png, 'blocked': blocked[0]}
    finally:
        browser.close()


def _render(connection, initial):
    from playwright.sync_api import sync_playwright
    document = static_document(initial['content'])
    with sync_playwright() as playwright:
        connection.send(render_document(document, playwright))


def prepare_web_preview(content, stop_event=None):
    """Bound source, process-tree memory and lifetime; return immutable local pixels."""
    static_document(content)  # Refuse before starting a worker/browser.
    if stop_event is not None and stop_event.is_set():
        raise ValueError('Preview cancelled by Stop')
    deadline = time.monotonic() + 5
    while not _render_lock.acquire(timeout=.05):
        if time.monotonic() > deadline or (stop_event is not None and stop_event.is_set()):
            raise ValueError('Another preview is stopping; retry shortly')
    worker = None
    try:
        if stop_event is not None and stop_event.is_set():
            raise ValueError('Preview cancelled by Stop')
        worker = Worker(_render, {'content': content}, memory_mb=1536)
        result = worker.receive(20, stop_event)
        if 'error' in result:
            raise ValueError('HTML preview stopped, timed out or Chromium unavailable')
        from vision_input import prepare_image
        image = prepare_image(result['png'], 'Static HTML/CSS preview')
        if (image.width, image.height) != (VIEWPORT['width'], VIEWPORT['height']):
            raise ValueError('Unexpected preview dimensions')
        return image
    finally:
        if worker is not None:
            worker.stop()
        _render_lock.release()
