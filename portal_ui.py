"""Explicit desktop-only control of the local website; launch keys never enter logs."""
import queue
import threading
import tkinter as tk
from tkinter import ttk
import webbrowser

import portal_server as server
from popup_windows import dismissible


class PortalPanel:
    def __init__(self,ui):
        self.ui=ui;self.closed=False;self.active=False;self.mail=queue.Queue()
        self.win=tk.Toplevel(ui.root);self.win.title('Local website');self.win.transient(ui.root)
        dismissible(self.win,lambda:setattr(self,'closed',True),size=(760,480))
        self.win.bind('<Destroy>',lambda event:setattr(self,'closed',True) if event.widget==self.win else None)
        body=ttk.Frame(self.win,padding=22);body.pack(fill='both',expand=True)
        ttk.Label(body,text='Local Studio · Website',style='Title.TLabel').pack(anchor='w')
        ttk.Label(body,text='Stage 1 · This laptop only. School access is not enabled.',style='Muted.TLabel',wraplength=680).pack(anchor='w',pady=10)
        ttk.Label(body,text='Chat and text/code Artifacts use a separate local library. Desktop and web requests share the model lock. '
                  'This temporary access link is private; it is not a production password or MFA login.',wraplength=680).pack(anchor='w',pady=6)
        self.link=tk.StringVar();ttk.Entry(body,textvariable=self.link,state='readonly').pack(fill='x',pady=15)
        row=ttk.Frame(body);row.pack(fill='x')
        for label,command in (('Start preview',self.start),('Open preview',self.open),('Copy access link',self.copy),('Stop website',self.stop)):
            ttk.Button(row,text=label,command=command).pack(side='left',padx=(0,5))
        self.status=tk.StringVar()
        ttk.Label(body,textvariable=self.status,style='Muted.TLabel',wraplength=680).pack(anchor='w',pady=15)
        self.refresh();ui.root.after(50,self.poll)

    def refresh(self):
        portal=server.current
        self.link.set(portal.origin+'/#'+portal.api.launch_key if portal else '')
        self.status.set('Running on this laptop. Close keeps it running; Stop website revokes sessions and cancels web jobs.' if portal
                        else 'Stopped. Start is explicit; nothing listens automatically when Local Studio opens.')

    def start(self):
        if self.active or server.current is not None:self.refresh();return
        self.active=True;self.status.set('Starting local preview…')
        def work():
            try:self.mail.put(('start',server.Portal(),None))
            except Exception:self.mail.put(('start',None,'Could not start. Port 8765 may be in use or local storage unavailable.'))
        threading.Thread(target=work,daemon=True).start()

    def poll(self):
        try:
            while True:
                kind,result,error=self.mail.get_nowait();self.active=False
                if self.closed:
                    if kind=='start' and result:threading.Thread(target=result.close,daemon=True).start()
                    continue
                if error:self.status.set('Error: '+error);continue
                if kind=='start':server.current=result
                self.refresh()
        except queue.Empty:pass
        if self.active or not self.closed:self.ui.root.after(50,self.poll)

    def open(self):
        if server.current:webbrowser.open(self.link.get())
        else:self.status.set('Start the local preview first.')

    def copy(self):
        if server.current:
            self.ui.root.clipboard_clear();self.ui.root.clipboard_append(self.link.get())
            self.status.set('Private local access link copied. Do not share it; it works only on this laptop.')

    def stop(self):
        if self.active:return
        portal,server.current=server.current,None
        if portal is None:self.refresh();return
        self.active=True;self.link.set('');self.status.set('Stopping website and cancelling its jobs…')
        def work():
            try:portal.close();self.mail.put(('stop',None,None))
            except Exception:self.mail.put(('stop',None,'Stop was not confirmed; close Local Studio before retrying.'))
        threading.Thread(target=work,daemon=True).start()


def show_portal(ui):
    old=getattr(ui.root,'_portal_panel',None)
    if old is not None and not old.closed:old.win.lift();old.refresh();return old
    panel=PortalPanel(ui);ui.root._portal_panel=panel;return panel
