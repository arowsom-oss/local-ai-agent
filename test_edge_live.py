"""Real owned Edge profile + fake HTTPS. No Internet, personal tabs, account or model."""
import ipaddress
import json
from pathlib import Path
import re
import shutil
import threading
import time
import uuid
import httpx
from unittest.mock import patch
import edge_tools as edge
import edge_work_browser as work

HTML=b'''<!doctype html><meta charset="utf-8"><title>Edge fixture</title>
<h1>Owned work fixture</h1><div id="result">No change</div><div id="cookies"></div>
<input aria-label="Draft" id="draft"><button onclick="result.textContent=draft.value">Save in RAM</button>
<input type="password" aria-label="Secret password" value="DO_NOT_READ">
<input type="file" id="file" aria-label="Upload file">
<button onclick="file.click()">Choose file</button>
<button onclick="location.href='/download'">Export file</button>
<button onclick="setTimeout(()=>result.textContent='Page changed independently',100)">Schedule change</button>
<button onclick="result.textContent=window.__localStudioEdge.marker">Check isolation</button>
<a href="/next">Next page</a><a href="/download" download>Direct download</a>
<script>window.__localStudioEdge={marker:'PAGE WORLD ONLY'};cookies.textContent=document.cookie;</script>
<div style="height:1800px">Tall page</div><button>Below viewport</button>'''


def number(text,label):
    match=re.search(r'\[(\d+)\] (?:text box|button|link) '+re.escape(json.dumps(label)),text)
    assert match,(label,text)
    return int(match[1])


def operation(action,element=None,text=''):
    proposal=edge.prepare_edge(action,element,text)
    assert 'token' in proposal,proposal
    result=edge.commit_edge(proposal['token'])
    assert not result.startswith('Error:'),result
    return result


def main():
    assert __debug__
    parent=Path(__file__).resolve().parents[1]
    profile=parent/('edge_fixture_profile_'+uuid.uuid4().hex)
    assert profile.parent==parent and not profile.exists()
    downloads=[];choosers=[];seen=[]
    class Stream(httpx.SyncByteStream):
        def __init__(self,data):self.data=data
        def __iter__(self):yield self.data
    def network(request):
        from urllib.parse import urlsplit
        parts=urlsplit(str(request.url))
        assert parts.hostname=='93.184.216.34' and request.headers['Host']=='fixture.example'
        assert request.extensions['sni_hostname']=='fixture.example'
        seen.append(parts.path)
        if parts.path=='/download':return httpx.Response(200,headers={'content-type':'application/octet-stream',
            'content-disposition':'attachment; filename=blocked.txt'},stream=Stream(b'SYNTHETIC TEST FILE'))
        return httpx.Response(200,headers=[('content-type','text/html; charset=utf-8'),
            ('set-cookie','fixture_one=one; Secure; Path=/'),('set-cookie','fixture_two=two; Secure; Path=/')],
            stream=Stream(HTML if parts.path=='/' else b'<h1>Next fixture page</h1><input aria-label="Other field">'))
    real_client=httpx.Client
    def client(**options):return real_client(transport=httpx.MockTransport(network),**options)
    original=work.WorkBrowser.guard
    def guard(self,page):
        original(self,page)
        page.on('download',lambda download:downloads.append(download.failure()))
        page.on('filechooser',lambda chooser:choosers.append(True))
    try:
        with patch.object(work,'PROFILE',profile),patch.object(work.httpx,'Client',side_effect=client), \
             patch.object(work.WorkBrowser,'guard',guard),patch.object(edge.fetch,'safe_ip',return_value=ipaddress.ip_address('93.184.216.34')):
            work.start_work();worker=work.work_current()
            assert worker.rpc('navigate',{'url':'https://fixture.example/'})=={'opened':True}
            text=operation('read')
            assert 'fixture_one=one' in text and 'fixture_two=two' in text,'Work response cookies were not preserved'
            assert 'DO_NOT_READ' not in text and 'Secret password"' not in text and 'text box "Upload file"' not in text
            assert 'Direct download"' not in text and 'button "Below viewport"' not in text
            old=number(text,'Draft')
            operation('type',old,'Reviewed synthetic draft')
            text=operation('read');assert '= "Reviewed synthetic draft"' in text
            operation('click',number(text,'Save in RAM'))
            assert 'Reviewed synthetic draft' in operation('read')
            assert edge.prepare_edge('type',old,'stale').get('error')
            text=operation('read');operation('click',number(text,'Check isolation'))
            assert 'PAGE WORLD ONLY' in operation('read'),'Website world could access/replace control state'
            text=operation('read');operation('click',number(text,'Schedule change'))
            text=operation('read')
            proposal=edge.prepare_edge('click',number(text,'Save in RAM'))
            assert 'token' in proposal
            time.sleep(.3)
            assert edge.commit_edge(proposal['token']).startswith('Error:'),'Changed page used a stale approval'
            text=operation('read');operation('click',number(text,'Choose file'))
            text=operation('read');assert len(choosers)==1
            before_blocked=worker.blocked_requests
            proposal=edge.prepare_edge('click',number(text,'Export file'))
            assert 'token' in proposal
            edge.commit_edge(proposal['token']) # Navigation may be refused before an action result arrives.
            time.sleep(.2)
            worker.rpc('navigate',{'url':'https://fixture.example/'})
            text=operation('read')
            assert worker.blocked_requests>before_blocked,'Attachment request was not blocked'
            assert not list(profile.rglob('blocked.txt')),'Download unexpectedly saved'
            operation('scroll',text='down')
            assert 'button "Below viewport"' not in text
            result=[]
            for _ in range(2):
                caller=threading.Thread(target=lambda:result.append(operation('read')))
                caller.start();caller.join(10);assert not caller.is_alive()
            assert len(result)==2 and all(value.startswith(edge.PREFIX) for value in result)
            worker.rpc('navigate',{'url':'https://fixture.example/next'})
            assert 'Next fixture page' in operation('read')
            refused=edge.prepare_edge('type',old,'cannot reuse')
            assert 'error' in refused
            try:worker.rpc('navigate',{'url':'https://fixture.example/download'})
            except ValueError:pass
            else:raise AssertionError('Attachment response was not blocked')
            worker.rpc('navigate',{'url':'https://fixture.example/next'})
            tabs=worker.rpc('list');assert tabs['tabs']
            worker.rpc('select',{'number':tabs['tabs'][-1]['number']})
            work.close_work();worker.thread.join(10);assert not worker.thread.is_alive()
            print('PASS real Edge: separate profile, pinned HTTPX/Host/SNI, cookies, isolated DOM, approval snapshots, typing and buttons')
            print('PASS real Edge: stale/replayed numbers, blocked downloads, file chooser interception, scrolling, caller threads and tab selection')
    finally:
        edge.close_edge()
        if work._worker:work._worker.thread.join(10)
        # Only this fixture's resolved, randomly named directory may be removed.
        if profile.exists():
            target=profile.resolve()
            assert target.parent==parent.resolve() and target.name.startswith('edge_fixture_profile_')
            shutil.rmtree(target)


def extension_main():
    from playwright.sync_api import sync_playwright
    parent=Path(__file__).resolve().parents[1]
    temp=parent/('edge_extension_fixture_'+uuid.uuid4().hex);temp.mkdir()
    extension=temp/'extension';extension.mkdir()
    source=Path(__file__).parent/'edge_extension'
    for file in source.iterdir():shutil.copy2(file,extension/file.name)
    manifest=json.loads((extension/'manifest.json').read_text())
    # This fixture-only grant substitutes for a human toolbar activeTab gesture.
    # Production manifest has no website host permission.
    manifest['host_permissions'].append('https://fixture.example/*')
    (extension/'manifest.json').write_text(json.dumps(manifest))
    code=edge.start_edge()
    try:
        with patch.object(edge.fetch,'safe_ip',return_value=ipaddress.ip_address('93.184.216.34')),sync_playwright() as playwright:
            context=playwright.chromium.launch_persistent_context(str(temp/'profile'),headless=False,channel='chromium',
                accept_downloads=False,args=[f'--disable-extensions-except={extension}',f'--load-extension={extension}'])
            def network(route):
                from urllib.parse import urlsplit
                parts=urlsplit(route.request.url);host=parts.hostname
                if host=='fixture.example':route.fulfill(content_type='text/html',body=b'<h1>Personal-tab fixture</h1><button>Do not control</button>')
                elif host=='127.0.0.1' or parts.scheme=='chrome-extension':route.continue_()
                else:route.abort()
            context.route('**/*',network)
            page=context.new_page();page.goto('https://fixture.example/')
            worker=context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
            tab=worker.evaluate("async()=> (await chrome.tabs.query({})).find(t=>t.url==='https://fixture.example/').id")
            panel=context.new_page();panel.on('pageerror',lambda error:print('Extension fixture script error:',str(error)[:200],flush=True))
            panel.goto('chrome-extension://'+worker.url.split('/')[2]+'/panel.html?tab='+str(tab))
            panel.locator('#pair').fill(code);panel.locator('#share').click()
            for _ in range(100):
                panel.wait_for_timeout(30)
                if edge.edge_available():break
            assert edge.edge_available(),panel.locator('#status').inner_text()
            def call(function):
                values=[];errors=[]
                def invoke():
                    try:values.append(function())
                    except Exception as exc:errors.append(type(exc).__name__)
                thread=threading.Thread(target=invoke);thread.start()
                for _ in range(500):
                    if not thread.is_alive():break
                    panel.wait_for_timeout(30)
                thread.join(.1);assert not thread.is_alive() and not errors,errors
                return values[0]
            proposal=call(lambda:edge.prepare_edge('shared_read'))
            assert 'token' in proposal,proposal
            result=call(lambda:edge.commit_edge(proposal['token']))
            assert result.startswith(edge.PREFIX) and 'Personal-tab fixture' in result,result
            proposal=call(lambda:edge.prepare_edge('copy'))
            assert call(lambda:edge.commit_edge(proposal['token']))=='URL https://fixture.example/'
            proposal=call(lambda:edge.prepare_edge('copy'))
            page.locator('h1').evaluate("el=>el.textContent='Changed fixture'")
            assert call(lambda:edge.commit_edge(proposal['token'])).startswith('Error:')
            panel.locator('#stop').click()
            for _ in range(100):
                panel.wait_for_timeout(20)
                if not edge.edge_available():break
            assert not edge.edge_available()
            context.close()
            print('PASS real Chromium extension: loopback authentication, personal read/copy, changed-page refusal and disconnect')
            print('NOTE fixture host grant simulates activeTab; actual Edge installation/toolbar consent is a manual check.')
    finally:
        edge.close_edge()
        target=temp.resolve()
        assert target.parent==parent.resolve() and target.name.startswith('edge_extension_fixture_')
        shutil.rmtree(target)


def ui_main():
    import tkinter as tk
    import chat_window as ui
    ui.build_window();ui.root.update()
    seen=[]
    def visit(widget):
        yield widget
        for child in widget.winfo_children():yield from visit(child)
    def deny():
        windows=[w for w in ui.root.winfo_children() if getattr(w,'_approval_dialog',False)]
        if not windows:ui.root.after(20,deny);return
        win=windows[0];widgets=list(visit(win))
        text='\n'.join(w.get('1.0','end') for w in widgets if isinstance(w,tk.Text))
        no=[w for w in widgets if isinstance(w,tk.Button) and w.cget('text')=='No']
        seen.append((text,len(no)==1 and no[0].cget('default')=='active'))
        win.event_generate('<Return>')
    try:
        assert any(isinstance(w,tk.Button) and w.cget('text')=='Edge tab' for w in visit(ui.root))
        ui.root.after(100,deny)
        url='https://fixture.example/'+'x'*900+'?q=exact'
        assert ui.confirm('edge_operation',{'action':'type','mode':'work profile','url':url,
                          'control':'Draft','before':'old','text':'Exact replacement'}) is False
        assert seen[0][1] and url in seen[0][0] and '\nExact replacement\n' in seen[0][0]
        ui.connect_edge_tab();ui.root.update()
        assert any(isinstance(w,tk.Button) and w.cget('text')=='Start work Edge' for w in visit(ui.root))
        print('PASS native Tk: Edge controls, full exact URL/text preview and Return defaults to No')
    finally:
        edge.close_edge();ui.artifact_panel.stop();ui.root.destroy()


if __name__=='__main__':main();extension_main();ui_main()
