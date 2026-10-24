"""Bounded pinned HTTP work. This thread never receives Playwright objects."""
import queue
import threading
import time
from urllib.parse import urlsplit,urlunsplit
import httpx
import fetch

WINDOW_SECONDS=8.0


def fetch_resource(method,url,headers,body,deadline,byte_limit,cancel):
    if cancel.is_set() or time.monotonic()>=deadline:raise ValueError('network window expired')
    parts=urlsplit(url);host=parts.hostname;ip=fetch.safe_ip(host)
    if cancel.is_set() or time.monotonic()>=deadline:raise ValueError('DNS exceeded network window')
    net=f'[{ip}]' if ip.version==6 else str(ip)
    headers=dict(headers,Host=host)
    headers['Accept-Encoding']='identity'
    with httpx.Client(timeout=min(10,max(.001,deadline-time.monotonic())),
                      follow_redirects=False,trust_env=False) as client:
        with client.stream(method,urlunsplit(parts._replace(netloc=net)),headers=headers,
                           content=body,extensions={'sni_hostname':host}) as response:
            if (300<=response.status_code<400 or response.status_code==101
                    or response.headers.get('content-encoding','identity').lower() not in {'identity',''}
                    or 'attachment' in response.headers.get('content-disposition','').lower()):
                raise ValueError('redirect, compressed response or download refused')
            length=int(response.headers.get('content-length','0'))
            if not 0<=length<=byte_limit:raise ValueError('response too large')
            data=bytearray()
            for chunk in response.iter_raw(65536):
                if cancel.is_set() or time.monotonic()>=deadline or len(data)+len(chunk)>byte_limit:
                    raise ValueError('response time or byte budget exhausted')
                data.extend(chunk)
            if cancel.is_set() or time.monotonic()>=deadline:raise ValueError('response deadline exceeded')
            result_headers={}
            for key,value in response.headers.multi_items():
                if key.lower() in {'connection','transfer-encoding','content-length','content-encoding','alt-svc'}:continue
                result_headers[key]=result_headers[key]+'\n'+value if key in result_headers else value
            return dict(status=response.status_code,headers=result_headers,body=bytes(data))


class PinnedFetcher:
    def __init__(self):
        self.jobs=queue.Queue(maxsize=1);self.halt=threading.Event()
        self.thread=threading.Thread(target=self.run,name='edge-pinned-http',daemon=True)
        self.thread.start()

    def run(self):
        while not self.halt.is_set():
            try:args,reply=self.jobs.get(timeout=.05)
            except queue.Empty:continue
            try:result=fetch_resource(*args,cancel=self.halt)
            except Exception:result={'error':'pinned request refused or timed out'}
            reply.put(result)

    def request(self,args,halt):
        deadline=args[-2];reply=queue.Queue(maxsize=1)
        if self.halt.is_set():raise ValueError('network worker is stopping')
        self.jobs.put_nowait((args,reply))
        while time.monotonic()<deadline and not halt.is_set():
            try:
                result=reply.get(timeout=min(.05,max(.001,deadline-time.monotonic())))
                if 'error' in result:raise ValueError(result['error'])
                return result
            except queue.Empty:pass
        # DNS cannot be forcibly cancelled in Python. Retire this one worker;
        # don't create more workers against a stuck resolver.
        self.halt.set()
        raise ValueError('network window expired or stopped')
