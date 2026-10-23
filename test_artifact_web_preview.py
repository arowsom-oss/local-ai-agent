"""Offline plain asserts with fake browser and worker; no real network/browser."""
from io import BytesIO
import threading
from types import SimpleNamespace as NS
from unittest.mock import patch

from PIL import Image
import artifact_web_preview as web


def test_detection_is_bounded_and_does_not_execute_other_languages():
    for text in ('<html><body>Hi</body></html>', '<!DOCTYPE html><h1>Hello</h1>',
                 '```html\n<div>Card</div>\n```'):
        assert web.html_source(text)
    for text in ('print(42)', 'const x = 2;', '<script>alert(1)</script>', '', None, '<div>'+'a'*32000):
        assert web.html_source(text) is None


def test_static_markup_retains_layout_but_strips_active_elements_and_url_attributes():
    result = web.static_document('''<html><head><meta http-equiv="refresh" content="0;url=file:///x">
      <base href="https://bad.invalid/"><link rel="stylesheet" href="https://bad.invalid/a.css">
      <style>.card{color:blue;display:grid}</style></head><body onload="evil()">
      <script>evil()</script><iframe srcdoc="evil">secret frame</iframe><svg onload="evil()">bad</svg>
      <h1 class="card">A &amp; B</h1><form action="https://bad.invalid"><input type="file">
      <button onclick="evil()">Go</button><img src="file:///x"><a href="javascript:evil()">link</a>
      </form></body></html>''')
    for value in ('<script', '<iframe', '<svg', '<meta', '<link', '<base', '<img', 'evil()',
                  'file://', 'https://bad', 'onclick', 'onload', 'secret frame', 'type="file"'):
        assert value not in result, value
    assert '<style>.card{color:blue;display:grid}</style>' in result
    assert '<h1 class="card">A &amp; B</h1>' in result
    assert '<button>Go</button>' in result


def test_attribute_quotes_stay_escaped_and_node_budget_fails_closed():
    result = web.static_document('<div title="&quot; onmouseover=&quot;evil()">safe</div>')
    assert 'title="&quot; onmouseover=&quot;evil()"' in result
    try:
        web.static_document('<div>'*2501)
    except ValueError:
        pass
    else:
        raise AssertionError('oversized node count accepted')


class Route:
    def __init__(self, url=web.PREVIEW_URL, method='GET', frame=None, navigation=True):
        self.request = NS(url=url,method=method,frame=frame,is_navigation_request=lambda:navigation)
        self.fulfilled = None
        self.aborted = False
    def fulfill(self,**kwargs): self.fulfilled=kwargs
    def abort(self): self.aborted=True


class Browser:
    def __init__(self):
        self.closed=False
        self.frame=object()
        self.page=NS(main_frame=self.frame,url=web.PREVIEW_URL,on=lambda *a:None,
                     goto=self.goto,screenshot=self.screenshot)
        self.context=NS(new_page=lambda:self.page,route=self.route,route_web_socket=self.socket_route,
                        on=lambda *a:None,pages=[self.page])
        self.requests=[]
    def new_context(self,**kwargs): self.options=kwargs;return self.context
    def route(self,pattern,handler): assert pattern=='**/*';self.handler=handler
    def socket_route(self,pattern,handler): self.socket_handler=handler
    def goto(self,url,**kwargs):
        self.first=Route(frame=self.frame);self.handler(self.first)
        for route in (Route(frame=self.frame),Route('file:///C:/secret.txt',frame=self.frame),
                      Route('http://127.0.0.1/a',frame=self.frame),
                      Route(method='POST',frame=self.frame),Route(frame=object()),
                      Route(frame=self.frame,navigation=False)):
            self.handler(route);self.requests.append(route)
    def screenshot(self,**kwargs): self.shot=kwargs;return b'fake PNG'
    def close(self): self.closed=True


def fake_playwright(browser):
    def launch(**kwargs): browser.launch_options=kwargs;return browser
    return NS(chromium=NS(launch=launch))


def test_only_one_synthetic_get_is_fulfilled_all_other_routes_abort():
    browser=Browser()
    result=web.render_document('<h1>safe</h1>',fake_playwright(browser))
    assert browser.first.fulfilled['body']=='<h1>safe</h1>'
    assert browser.first.fulfilled['headers']['Content-Security-Policy']==web.CSP
    assert web.CSP.startswith('sandbox;') and "default-src 'none'" in web.CSP
    assert all(route.aborted and route.fulfilled is None for route in browser.requests)
    assert result['blocked']==6 and browser.closed
    assert browser.options['java_script_enabled'] is False
    assert browser.options['service_workers']=='block' and browser.options['offline'] is True
    assert browser.options['accept_downloads'] is False and browser.options['permissions']==[]
    assert browser.launch_options['chromium_sandbox'] is True
    assert browser.launch_options['proxy']['server']=='http://127.0.0.1:9'
    assert browser.shot['full_page'] is False
    closed=[];browser.socket_handler(NS(close=lambda:closed.append(True)));assert closed


def test_changed_navigation_and_oversized_pixel_result_close_the_browser():
    for fail in ('navigation','size'):
        browser=Browser()
        if fail=='navigation': browser.page.url='file:///C:/secret'
        else: browser.page.screenshot=lambda **kwargs:b'x'*8_000_001
        try:
            web.render_document('<h1>safe</h1>',fake_playwright(browser))
        except ValueError:
            pass
        else:
            raise AssertionError('bad renderer result accepted')
        assert browser.closed


def test_worker_cleanup_success_failure_stop_and_bad_source():
    data=BytesIO();Image.new('RGB',(800,1000),'navy').save(data,format='PNG')
    workers=[]
    class Worker:
        def __init__(self,target,initial,memory_mb):
            assert memory_mb==1536;self.stopped=False;workers.append(self)
        def receive(self,seconds,event): assert seconds==20;return {'png':data.getvalue()}
        def stop(self): self.stopped=True
    with patch.object(web,'Worker',Worker):
        image=web.prepare_web_preview('<h1>Hi</h1>')
        assert image.width==800 and workers[-1].stopped
        with patch.object(Worker,'receive',return_value={'error':'timeout'}):
            try: web.prepare_web_preview('<h1>Hi</h1>')
            except ValueError: pass
            else: raise AssertionError('timeout accepted')
        assert workers[-1].stopped
        count=len(workers);event=threading.Event();event.set()
        for text,stop in (('print(1)',None),('<h1>Hi</h1>',event)):
            try: web.prepare_web_preview(text,stop)
            except ValueError: pass
            else: raise AssertionError('invalid/stopped preview accepted')
        assert len(workers)==count
    assert not web._render_lock.locked()


if __name__=='__main__':
    tests=[v for name,v in list(globals().items()) if name.startswith('test_')]
    for test in tests:
        test();print('PASS '+test.__name__)
    print(f'All {len(tests)} offline HTML preview tests passed.')
