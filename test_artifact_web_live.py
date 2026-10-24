"""Owned Windows renderer/Tk fixtures. Offline, synthetic, no model inference."""
from io import BytesIO
from pathlib import Path
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from PIL import Image, ImageGrab
import artifact_web_preview as web
import chat_window as ui
from artifacts import store
from process_guard import _workers

HTML='''<!doctype html><html><head><style>
body{margin:0;background:#edf2f7;color:#14213d;font-family:Arial}
.hero{background:#14213d;color:white;padding:48px;height:220px}
h1{font-size:44px;margin-top:0}.cards{display:grid;grid-template-columns:1fr 1fr;gap:20px;padding:24px}
.card{background:white;border-radius:16px;padding:24px}button{background:#62d2a2;border:0;padding:12px 24px}
</style></head><body><div class="hero"><h1>A place for ideas</h1>
<p>Your local website preview, made from HTML and CSS.</p><button>Get started</button></div>
<div class="cards"><div class="card"><h2>Create</h2><p>Build a simple page.</p></div>
<div class="card"><h2>Explore</h2><p>Switch between Preview and Code.</p></div></div></body></html>'''


def pump_until(test,timeout=35):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        ui.root.update()
        if test(): return
        time.sleep(.03)
    raise AssertionError('HTML preview fixture timed out')


def main():
    # Worker uses a fresh actual Chromium tree under a Windows Job, not fakes.
    image=web.prepare_web_preview(HTML)
    with Image.open(BytesIO(image.png)) as pixels:
        assert pixels.size==(800,1000) and pixels.getpixel((2,2))==(20,33,61)
        assert pixels.getpixel((2,950))==(237,242,247)
    assert not _workers
    print('PASS actual bounded Chromium worker renders HTML/CSS to expected pixels',flush=True)

    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path);self.send_response(200);self.end_headers();self.wfile.write(b'blocked canary')
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    origin='http://127.0.0.1:'+str(server.server_port)
    hostile=f'''<html><head><style>@import url('{origin}/css');
    body{{margin:0;background:rgb(0,128,0)}}div{{background-image:url('{origin}/pixel')}}</style>
    <link rel="preconnect" href="{origin}"></head><body onload="document.body.style.background='red'">
    <script>document.body.style.background='red';fetch('{origin}/fetch');new WebSocket('ws://127.0.0.1:{server.server_port}/ws');window.open('{origin}/popup')</script>
    <img src="{origin}/image"><iframe src="{origin}/frame"></iframe><iframe src="file:///C:/Windows/win.ini"></iframe>
    <form action="{origin}/form"><input name="secret"><button>Submit</button></form><div>Safe</div></body></html>'''
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            # Bypass HTML reduction to verify independent browser/CSP policy too.
            result=web.render_document(hostile,playwright)
        with Image.open(BytesIO(result['png'])) as pixels:
            assert pixels.getpixel((790,990))==(0,128,0),'page script changed pixels'
        time.sleep(.2)
        assert not requests,requests
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)
    print('PASS real CSP/disabled scripts/offline interception deny loopback resource and script attempts',flush=True)

    ui.build_window();ui.root.geometry('1440x900');errors=[]
    ui.root.report_callback_exception=lambda kind,value,trace:errors.append(value)
    try:
        artifact=store.create('Website preview','code',HTML)
        pump_until(lambda:ui.artifact_panel.web_image is not None)
        panel=ui.artifact_panel
        assert panel.winfo_ismapped() and panel.view_mode=='preview'
        assert panel.preview_button.winfo_ismapped() and panel.code_button.winfo_ismapped()
        assert not panel.editor.winfo_ismapped() and panel.web_canvas.winfo_ismapped()
        panel.code_button.invoke();ui.root.update()
        assert panel.view_mode=='code' and panel.editor.winfo_ismapped()
        panel.editor.insert('end','\n<!-- Unsaved human text -->');ui.root.update()
        assert panel.dirty
        panel.preview_button.invoke()
        pump_until(lambda:panel.web_image is not None)
        assert panel.dirty and 'Unsaved draft' in panel.status.get()
        assert store.get(artifact.number).current.number==1
        panel.code_button.invoke();ui.root.update()
        assert 'Unsaved human text' in panel.editor.get('1.0','end-1c')
        panel.save();pump_until(lambda:panel.web_image is not None)
        assert panel.version.number==2
        screenshot=Path(__file__).resolve().parents[2]/'outputs/local_studio_website_preview.png'
        screenshot.parent.mkdir(exist_ok=True)
        ui.root.update();time.sleep(.1)
        ImageGrab.grab(bbox=(ui.root.winfo_rootx(),ui.root.winfo_rooty(),
            ui.root.winfo_rootx()+ui.root.winfo_width(),ui.root.winfo_rooty()+ui.root.winfo_height())).save(screenshot)
        print('Preview screenshot:',screenshot,flush=True)
        panel.code_button.invoke();ui.root.update()
        panel.history.set('1');panel.choose_version()
        pump_until(lambda:panel.web_image is not None)
        assert panel.version.number==1 and 'Unsaved human text' not in panel.editor.get('1.0','end-1c')
        panel.code_button.invoke()
        plain=store.create('Python source','code','print(42)');panel.load(plain.number);ui.root.update()
        panel.preview_button.invoke();assert panel.view_mode=='code' and 'HTML/CSS' in panel.status.get()
        # A new HTML Artifact selects itself; unsaved source blocks replacement.
        second=store.create('Another website','code',HTML);panel.refresh()
        pump_until(lambda:panel.selected.number==second.number and panel.web_image is not None)
        panel.code_button.invoke();panel.editor.insert('end','\n<!-- Keep -->');ui.root.update()
        third=store.create('Third website','code',HTML);panel.refresh()
        assert panel.selected.number==second.number and panel.dirty
        # Invalidating a serial prevents late pixels from reappearing after Code.
        serial=panel.serial;panel.code_button.invoke()
        panel.web_mail.put((serial,image,None));panel.poll_web_preview()
        assert panel.view_mode=='code' and not panel.web_canvas.winfo_ismapped()
        # Actual Stop during a job must terminate owned descendants and discard results.
        panel.preview_button.invoke();ui.root.update();ui.stop_agent()
        pump_until(lambda:not _workers)
        assert panel.stop_event.is_set()
        ui.stop_event.clear()
        with patch('chat_window.messagebox.askyesno',return_value=True),patch('chat_window.free_vram'):
            ui.new_chat()
        ui.root.update();assert panel.web_image is None and panel.selected is None
        assert not errors,errors
        print('PASS real Tk Preview-first/buttons, unsaved/history, unsupported source, new selection, stale results, Stop and New chat',flush=True)
    finally:
        ui.stop_all();ui.root.destroy()


if __name__=='__main__': main()
