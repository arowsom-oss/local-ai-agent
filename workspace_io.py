"""Short-lived owned filesystem workers. No model accepts paths or worker commands."""
from contextlib import contextmanager, ExitStack
from pathlib import Path
import threading
import time
from process_guard import Worker

IO_TIMEOUT=10.0


def file_worker(connection,initial):
    from workspace_native import NativeFiles
    files=NativeFiles(initial['root'])
    with files.locked(),ExitStack() as stack:
        held=None
        connection.send({'ready':True})
        while True:
            command=connection.recv()
            try:
                kind=command.get('kind')
                if kind=='inventory':reply={'inventory':files.inventory()}
                elif kind=='read':
                    if held is not None:raise ValueError('reader already held')
                    held=stack.enter_context(ExitStack());data=held.enter_context(files.reader(command['key'],command['version']))
                    reply={'data':data}
                elif kind=='release':
                    if held is not None:held.close();held=None
                    reply={'released':True}
                elif kind=='publish':reply={'path':files.publish(command['key'],command['version'],command['data'],None)}
                elif kind=='titles':
                    titles={}
                    for key,version in files.inventory().items():
                        with files.reader(key,version) as data:
                            try:text=data.decode('utf-8')
                            except UnicodeError:text='Unreadable text'
                            first=next((line.strip() for line in text.splitlines() if line.strip()),'Untitled document')
                            titles[key]=''.join(c for c in first if c.isprintable())[:80]
                    reply={'titles':titles}
                else:raise ValueError('unknown filesystem command')
                connection.send(reply)
            except FileNotFoundError:connection.send({'error':'workspace file is not present','code':'missing'})
            except ValueError as exc:connection.send({'error':str(exc)})
            except Exception:connection.send({'error':'filesystem operation failed or unavailable'})


class RemoteFiles:
    def __init__(self,root,timeout=IO_TIMEOUT,worker_factory=Worker,target=file_worker):
        self.root=Path(root).absolute();self.timeout=timeout;self.factory=worker_factory;self.target=target
        self.local=threading.local();self.guard=threading.Lock();self.active=set();self.generation=0

    @contextmanager
    def locked(self):
        deadline=time.monotonic()+self.timeout
        with self.guard:generation=self.generation
        worker=self.factory(self.target,{'root':str(self.root)},memory_mb=256)
        with self.guard:
            self.active.add(worker);cancelled=generation!=self.generation
        self.local.transaction=(worker,deadline)
        try:
            if cancelled:raise ValueError('filesystem operation cancelled')
            ready=worker.receive(max(.001,deadline-time.monotonic()))
            if ready.get('ready') is not True:raise ValueError(ready.get('error','filesystem startup failed'))
            yield
        finally:
            self.local.transaction=None
            with self.guard:self.active.discard(worker)
            worker.stop()

    def request(self,payload,stop=None):
        transaction=getattr(self.local,'transaction',None)
        if transaction is None:raise ValueError('filesystem transaction required')
        worker,deadline=transaction;remaining=deadline-time.monotonic()
        if remaining<=0:worker.stop();raise ValueError('filesystem operation timed out')
        reply=worker.request(payload,timeout=remaining,stop_event=stop)
        if isinstance(reply,dict) and reply.get('code')=='missing':raise FileNotFoundError('workspace file is not present')
        if not isinstance(reply,dict) or 'error' in reply:raise ValueError(reply.get('error','filesystem failure') if isinstance(reply,dict) else 'filesystem failure')
        return reply

    def inventory(self):return self.request({'kind':'inventory'})['inventory']
    def titles(self):return self.request({'kind':'titles'})['titles']

    def filename(self,key,version):
        # Pure naming validation; no Win32/native initialization in the UI process.
        from workspace_native import FILE
        name=f'doc-{key}-v{version:03}.txt'
        if not FILE.fullmatch(name) or not 1<=version<=12:raise ValueError('invalid internal document identity')
        return name

    @contextmanager
    def reader(self,key,version):
        data=self.request({'kind':'read','key':key,'version':version})['data']
        try:yield data
        finally:
            try:self.request({'kind':'release'})
            except ValueError:pass

    def publish(self,key,version,data,stop):
        if stop is not None and stop.is_set():raise ValueError('stopped before document publication')
        return self.request({'kind':'publish','key':key,'version':version,'data':data},stop)['path']

    def cancel(self):
        with self.guard:
            self.generation+=1;workers=tuple(self.active)
        for worker in workers:worker.stop()
