"""One owned Edge work profile and sync Playwright owner thread. Never personal CDP/profile access."""
import atexit
from pathlib import Path
import queue
import threading
import time
from urllib.parse import urlsplit,urlunsplit
import httpx
import fetch

PROFILE=Path(__file__).resolve().parent/'edge_work_profile'
_lock=threading.RLock()
_worker=None


class WorkBrowser:
    def __init__(self,base):
        self.lock=threading.RLock();self.tickets={};self.counter_base=base
        self.closed=False;self.selected=None;self.error='';self.tab=None
        self.commands=0
        self.choice_serial=base
        self.request_count=0;self.response_bytes=0;self.allow_posts_until=0
        self.blocked_requests=0;self.post_origin=None
        self.queue=queue.Queue();self.halt=threading.Event()
        self.thread=threading.Thread(target=self.run,name='edge-work-owner',daemon=True);self.thread.start()

    def rpc(self,op,args=None,stop=None):
        if self.closed:raise ValueError('Edge work browser is closed')
        reply=queue.Queue(maxsize=1);deadline=time.time()+15
        self.queue.put((op,dict(args or {},_base=self.counter_base),reply,deadline))
        while time.time()<deadline:
            if stop is not None and stop.is_set():raise ValueError('stopped')
            try:
                result=reply.get(timeout=.05)
                if 'error' in result:raise ValueError(result['error'])
                return result
            except queue.Empty:pass
            if self.closed:raise ValueError(self.error or 'Edge work browser closed')
        self.halt.set();self.closed=True
        raise ValueError('Edge timed out; work browser is stopping')

    def run(self):
        context=None
        try:
            from playwright.sync_api import sync_playwright
            if PROFILE.is_symlink() or PROFILE.is_junction():raise ValueError('work profile cannot be a link')
            PROFILE.mkdir(exist_ok=True)
            source=(Path(__file__).resolve().parent/'edge_extension/page.js').read_text(encoding='utf-8')
            function=source.replace('export async function edgeDOM','async function edgeDOM',1)
            with sync_playwright() as playwright:
                context=playwright.chromium.launch_persistent_context(str(PROFILE),channel='msedge',headless=False,
                    accept_downloads=False,service_workers='block',permissions=[],
                    args=['--disable-save-password-bubble'])
                context.clear_permissions()
                context.route('**/*',self.route)
                context.route_web_socket('**/*',lambda route:route.close())
                context.on('page',lambda page:self.guard(page))
                for page in context.pages:self.guard(page)
                while not self.halt.is_set():
                    try:op,args,reply,deadline=self.queue.get(timeout=.03)
                    except queue.Empty:
                        if context.pages:context.pages[0].wait_for_timeout(20)
                        else:break
                        continue
                    try:
                        if time.time()>=deadline:raise ValueError('expired command')
                        self.commands+=1
                        if self.commands>3000:raise ValueError('work session command budget exhausted; restart it')
                        if op=='list':
                            self.choices={}
                            for page in context.pages[:20]:
                                self.choice_serial+=1;self.choices[self.choice_serial]=page
                            result={'tabs':[{'number':n,'title':page.title()[:200],'url':page.url} for n,page in self.choices.items()]}
                        elif op=='select':
                            page=getattr(self,'choices',{}).get(args.get('number'))
                            if page is None or page.is_closed():raise ValueError('list and select a current work tab')
                            self.selected=page;self.tab={'url':page.url};self.tickets.clear()
                            self.choices={}
                            result={'selected':True}
                        elif op=='navigate':
                            from edge_tools import url_problem
                            if url_problem(args.get('url')):raise ValueError('URL refused')
                            self.request_count=0;self.response_bytes=0;self.allow_posts_until=0
                            page=self.selected
                            if page is None or page.is_closed():
                                page=next((p for p in context.pages if p.url=='about:blank'),None) or context.new_page()
                                self.selected=page
                            try:page.goto(args['url'],wait_until='domcontentloaded',timeout=10000)
                            except Exception:
                                # Preserve the failed tab for human review, but do not race
                                # its pending error navigation with the next approved open.
                                self.selected=None
                                raise
                            self.tab={'url':page.url};result={'opened':True}
                        else:
                            if op not in {'prepare','commit'}:raise ValueError('unknown work command')
                            page=self.selected
                            if page is None or page.is_closed():raise ValueError('choose a work tab in the app first')
                            args['_base']=self.counter_base
                            if op=='commit' and args.get('_action') in {'click','type'}:
                                self.request_count=0;self.response_bytes=0
                                self.allow_posts_until=time.monotonic()+5
                                parts=urlsplit(page.url);self.post_origin=(parts.scheme,parts.netloc)
                            result=self.dom(page,function,{'op':op,'args':args,'expires':deadline*1000})
                            if result.get('error'):self.allow_posts_until=0
                            if 'next_counter' in result:
                                value=result['next_counter']
                                if type(value) is not int or not self.counter_base<=value<=self.counter_base+30:raise ValueError('invalid control counter')
                                self.counter_base=value
                        reply.put(result)
                    except Exception:
                        self.allow_posts_until=0
                        reply.put({'error':'work tab changed, refused or unavailable; select/read it again'})
                context.close();context=None
        except Exception as exc:self.error='Could not start or operate the dedicated Edge work profile: '+type(exc).__name__
        finally:
            self.closed=True;self.tickets.clear()
            if context:
                try:context.close()
                except Exception:pass

    def guard(self,page):
        # Prevent chooser UI and accepted downloads. No file path is ever supplied.
        page.on('filechooser',lambda chooser:None)
        page.on('download',lambda download:download.cancel())
        page.on('dialog',lambda dialog:dialog.dismiss())

    @staticmethod
    def dom(page,function,command):
        # An isolated CDP world prevents website JS from replacing our builtins,
        # reading approval tickets, or editing the recorded control map.
        session=page.context.new_cdp_session(page)
        try:
            frame=session.send('Page.getFrameTree')['frameTree']['frame']['id']
            world=session.send('Page.createIsolatedWorld',{'frameId':frame,'worldName':'LocalStudioGuardedDOM',
                                                           'grantUniveralAccess':False})['executionContextId']
            response=session.send('Runtime.callFunctionOn',{'functionDeclaration':function,
                'executionContextId':world,'arguments':[{'value':command}],
                'awaitPromise':True,'returnByValue':True,
                'userGesture':command.get('op')=='commit' and command.get('args',{}).get('_action') in {'click','type'}})
            if 'exceptionDetails' in response:raise ValueError('fixed DOM helper failed')
            return response['result'].get('value',{'error':'no result'})
        finally:session.detach()

    def route(self,route):
        from edge_tools import url_problem
        try:
            request=route.request;self.request_count+=1
            if self.request_count>250 or self.response_bytes>=20_000_000:raise ValueError('page budget exhausted')
            if url_problem(request.url):raise ValueError('URL refused')
            if request.method not in {'GET','POST'}:raise ValueError('method refused')
            if request.method=='POST' and time.monotonic()>self.allow_posts_until:raise ValueError('POST needs a recently approved click/type')
            parts=urlsplit(request.url)
            if request.method=='POST' and (parts.scheme,parts.netloc)!=self.post_origin:raise ValueError('cross-origin POST refused')
            body=request.post_data_buffer
            if body and len(body)>256_000:raise ValueError('request body too large')
            parts=urlsplit(request.url);host=parts.hostname;ip=fetch.safe_ip(host)
            net=f'[{ip}]' if ip.version==6 else str(ip)
            headers={key:value for key,value in request.all_headers().items()
                     if key.lower() not in {'host','connection','proxy-authorization','proxy-connection',
                         'accept-encoding','content-length','transfer-encoding','if-none-match','if-modified-since'}}
            content_type=next((value.lower() for key,value in headers.items() if key.lower()=='content-type'),'')
            if request.method=='POST' and ('multipart/' in content_type or 'application/octet-stream' in content_type):
                raise ValueError('file upload content type refused')
            headers.update({'Host':host,'Accept-Encoding':'identity'})
            with httpx.Client(timeout=10,follow_redirects=False,trust_env=False) as client:
                with client.stream(request.method,urlunsplit(parts._replace(netloc=net)),headers=headers,
                                   content=body,extensions={'sni_hostname':host}) as response:
                    if (300<=response.status_code<400 or response.status_code==101
                            or response.headers.get('content-encoding','identity').lower() not in {'identity',''}
                            or 'attachment' in response.headers.get('content-disposition','').lower()):
                        raise ValueError('redirect, compressed response or download refused')
                    if int(response.headers.get('content-length','0'))>5_000_000:raise ValueError('response too large')
                    data=bytearray()
                    for chunk in response.iter_raw(65536):
                        self.response_bytes+=len(chunk)
                        if len(data)+len(chunk)>5_000_000 or self.response_bytes>20_000_000:raise ValueError('response budget exhausted')
                        data.extend(chunk)
                    result_headers={}
                    for key,value in response.headers.multi_items():
                        if key.lower() in {'connection','transfer-encoding','content-length','content-encoding','alt-svc'}:continue
                        result_headers[key]=result_headers[key]+'\n'+value if key in result_headers else value
                    route.fulfill(status=response.status_code,headers=result_headers,body=bytes(data))
        except Exception:
            self.blocked_requests+=1
            route.abort('blockedbyclient')


def start_work():
    global _worker
    with _lock:
        if _worker and _worker.thread.is_alive():
            return 'Edge work browser is already running or stopping.'
        from edge_tools import next_number_base
        _worker=WorkBrowser(next_number_base())
        return 'Starting the separate Edge work profile. Open a website there, then choose its tab in the app.'


def work_current():
    with _lock:worker=_worker
    if worker is None or worker.closed:raise ValueError('start the Edge work browser first')
    return worker


def work_available():
    with _lock:return _worker is not None and not _worker.closed


def close_work():
    with _lock:worker=_worker
    if worker:
        worker.closed=True;worker.halt.set()
        with worker.lock:worker.tickets.clear()
    return 'Work browser access revoked; owned Edge is closing. Its separate profile stays on disk.'


atexit.register(close_work)
