"""Real Chromium adversarial fixture. Only synthetic HTML and owned loopback canaries."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from io import BytesIO
import threading
from types import SimpleNamespace as NS

from PIL import Image
from playwright.sync_api import sync_playwright,Error as BrowserError
import artifact_web_preview as web


def test_real_chromium_scripts_external_resources_and_navigation_are_blocked():
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path);self.send_response(200);self.end_headers();self.wfile.write(b'NETWORK_GATE_FAILED')
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    origin=f'http://127.0.0.1:{server.server_port}'
    raw=f'''<html><head><style>
      @import url('{origin}/import.css');
      body{{margin:0;background:rgb(0,128,0);background-image:url('{origin}/css-pixel')}}
      </style></head><body onload="document.body.style.background='red'">
      <script>document.body.style.background='red';fetch('{origin}/fetch');
      new WebSocket('ws://127.0.0.1:{server.server_port}/socket');location.href='{origin}/script-navigation';</script>
      <img src="{origin}/image"><iframe src="{origin}/frame"></iframe></body></html>'''
    try:
        with sync_playwright() as playwright:
            # Deliberately bypass the reducer: browser policy must hold independently.
            result=web.render_document(raw,playwright)
            with Image.open(BytesIO(result['png'])) as pixels:
                assert pixels.getpixel((790,990))==(0,128,0),'Inline script/event handler executed'
            assert not requests,requests
            observed={'attempted':False,'blocked':False}
            class Page:
                def __init__(self,page):self.base=page
                def __getattr__(self,name):return getattr(self.base,name)
                def goto(self,url,**kwargs):
                    result=self.base.goto(url,**kwargs)
                    observed['attempted']=True
                    try:self.base.goto(origin+'/forced-navigation',wait_until='load',timeout=3000)
                    except BrowserError:observed['blocked']=True
                    else:raise AssertionError('Second main-frame navigation was allowed')
                    return result
            class Context:
                def __init__(self,context):self.base=context
                def __getattr__(self,name):return getattr(self.base,name)
                def new_page(self):return Page(self.base.new_page())
            class Browser:
                def __init__(self,browser):self.base=browser
                def new_context(self,**kwargs):return Context(self.base.new_context(**kwargs))
                def close(self):self.base.close()
            def launch(**kwargs):return Browser(playwright.chromium.launch(**kwargs))
            try:web.render_document('<h1>Navigation probe</h1>',NS(chromium=NS(launch=launch)))
            except ValueError as exc:
                # Chromium can replace an aborted navigation with its internal error
                # document. The renderer's URL postcondition must then refuse pixels.
                assert str(exc)=='Preview navigation changed unexpectedly',str(exc)
            assert observed=={'attempted':True,'blocked':True}
            assert not requests,'Blocked external requests reached the owned canary: '+repr(requests)
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
        assert not thread.is_alive()


if __name__=='__main__':
    assert __debug__,'Run without -O'
    test_real_chromium_scripts_external_resources_and_navigation_are_blocked()
    print('PASS test_real_chromium_scripts_external_resources_and_navigation_are_blocked',flush=True)
