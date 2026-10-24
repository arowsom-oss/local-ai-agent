"""Owned Tk and genuine loopback HTTP checks; synthetic model and temporary records."""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

import httpx
import chat_window as ui
import portal_ui
import portal_server as web
from portal_store import Store
from test_portal import Client,key
import model_router as models


def pump(fn):
    end=time.monotonic()+10
    while time.monotonic()<end:
        ui.root.update()
        if fn():return
        time.sleep(.01)
    raise AssertionError('Portal native fixture timeout')


def main():
    with tempfile.TemporaryDirectory() as folder,ExitStack() as stack:
        original=web.Portal
        stack.enter_context(patch('emergency_hotkey.start_hotkey'))
        stack.enter_context(patch.object(web,'Portal',side_effect=lambda:original(Store(folder),port=0)))
        client=Client();stack.enter_context(patch.object(models,'_client',client));stack.enter_context(patch.object(models,'_active',None))
        ui.build_window();errors=[];ui.root.report_callback_exception=lambda k,v,t:errors.append(v)
        try:
            panel=ui.show_website();ui.root.update()
            assert web.current is None and not panel.link.get()
            panel.start();pump(lambda:not panel.active)
            assert web.current and web.current.http.server_address[0]=='127.0.0.1',panel.status.get()
            portal=web.current
            with httpx.Client(base_url=portal.origin,headers={'Origin':portal.origin},trust_env=False) as browser:
                assert browser.get('/').status_code==200
                assert browser.get('/api/state').status_code==401
                assert browser.post('/api/session',json={'key':portal.api.launch_key}).status_code==200
                cookie=browser.cookies.get('studio_session');assert cookie
                csrf=browser.get('/api/state').json()['csrf'];browser.headers['X-CSRF-Token']=csrf
                chat=browser.post('/api/chats',json={'title':'Loopback test'}).json()['chat']
                request={'chat':chat,'request':key(),'message':'Synthetic HTTP request','model':models.FAST_MODEL}
                job=browser.post('/api/jobs',json=request).json()['job']
                pump(lambda:portal.controller.store.job(job)['status']=='completed')
                assert browser.post('/api/jobs',json=request).json()['job']==job and len(client.calls)==1
                artifact=browser.post('/api/keep',json={'job':job,'kind':'code'}).json()['artifact']
                assert browser.get('/api/artifacts/'+artifact).json()['body']=='Synthetic local reply.'
                assert browser.post('/api/jobs',json={**request,'tool':'desktop_start'}).status_code==400
                assert browser.get('/api/state',headers={'Host':'evil.invalid'}).status_code==403
                assert browser.post('/api/logout',json={}).status_code==200
                browser.cookies.set('studio_session',cookie)
                assert browser.get('/api/artifacts/'+artifact).status_code==401
            # Close leaves a started site running; Stop website actually closes it.
            panel.win._dismiss_popup();ui.root.update();assert web.current is portal
            panel=ui.show_website();ui.root.update();panel.win.focus_force();ui.root.update()
            panel.win.event_generate('<Escape>');ui.root.update();assert panel.closed
            panel=ui.show_website();ui.root.update();panel.win.tk.call(panel.win.protocol('WM_DELETE_WINDOW'));ui.root.update();assert panel.closed
            panel=ui.show_website();ui.root.update();panel.stop();pump(lambda:not panel.active)
            assert web.current is None and portal.controller.closed.is_set()
            assert not errors,errors
            print('PASS genuine loopback login/CSRF/cookies, queued chat, idempotent retry, Artifact ownership and logout')
            print('PASS actual desktop website Start/Stop, fixed loopback bind, Close/Escape/X and session revocation')
        finally:web.shutdown();ui.stop_all();ui.root.destroy()


if __name__=='__main__':main()
