"""Asynchronous person-controlled Documents UI. Worker threads never touch Tk."""
import difflib
import queue
import re
import threading
import tkinter as tk
from tkinter import ttk
import workspace_documents as documents


class Jobs:
    def __init__(self,panel):
        self.panel=panel;self.mail=queue.Queue();self.active=False;self.serial=0
        panel.after(40,self.poll)

    def run(self,work,done):
        if self.active:
            self.panel.status.set('A Documents operation is running. Stop can cancel it.');return False
        self.active=True;self.serial+=1;serial=self.serial;workspace=documents.workspace();generation=workspace.generation
        getattr(self.panel,'document_busy',lambda active:None)(True)
        self.panel.status.set('Working on Documents... Stop remains available.')
        def background():
            try:result=work()
            except Exception:result={'error':'document operation failed or cancelled'}
            self.mail.put((serial,generation,result,done))
        threading.Thread(target=background,daemon=True).start();return True

    def poll(self):
        try:
            while True:
                serial,generation,result,done=self.mail.get_nowait()
                if serial!=self.serial:continue
                self.active=False
                getattr(self.panel,'document_busy',lambda active:None)(False)
                if self.panel.stop_event.is_set() or generation!=documents.workspace().generation:continue
                done(result)
        except queue.Empty:pass
        self.panel.after(40,self.poll)


def jobs(panel):
    if not hasattr(panel,'document_jobs'):panel.document_jobs=Jobs(panel)
    return panel.document_jobs


def access(panel,confirm):
    if panel.stop_event.is_set():
        if getattr(panel,'model_busy',lambda:False)() or jobs(panel).active:
            panel.status.set('Wait for the stopped operation to finish cancelling.');return False
        # An explicit person click starts a new manual operation, like opening Notepad.
        panel.stop_event.clear()
    if not documents.workspace_allowed():
        if confirm is None or confirm('workspace_access',{'folder':str(documents.ROOT)}) is not True:return False
        if panel.stop_event.is_set():return False
        documents.grant_workspace()
    return True


def comparison(before,after):
    def formatting(label,text):
        trailing=sum(line.endswith((' ','\t')) for line in text.split('\n'))
        return (f'{label}: characters: {len(text)}; line breaks: {text.count(chr(10))}; '
                f'tabs: {text.count(chr(9))}; final newline: {"yes" if text.endswith(chr(10)) else "no"}; '
                f'lines ending in spaces/tabs: {trailing}.')
    diff='\n'.join(difflib.unified_diff(before.splitlines(),after.splitlines(),fromfile='Current saved text',tofile='Proposed text',lineterm=''))
    if not diff:
        diff=('No text changes. This still creates a new version.' if before==after else
              'Only line ending or trailing newline differences. Compare the exact JSON below.')
    return (formatting('Current',before)+'\n'+formatting('Proposed',after)+'\n\n'+
            diff[:12000]+('\n[Comparison shortened; complete approved text is shown below.]' if len(diff)>12000 else ''))


def save_selected(panel,confirm,document=0,version=0):
    if panel.dirty:
        panel.status.set('Save edit as an Artifact version before saving to Documents.');return
    if panel.selected is None or panel.version is None or panel.selected.kind!='document':
        panel.status.set('Select a document Artifact first.');return
    if not access(panel,confirm):return
    args={'artifact':panel.selected.number,'revision':panel.version.number,'document':document,'version':version}
    def prepare():
        if document:documents.workspace().observe_current(document,version)
        return documents.prepare_save(**args)
    def proposed(proposal):
        if 'error' in proposal:panel.status.set('Error: '+proposal['error']);return
        if confirm('document_save_exact',proposal['preview']) is not True or panel.stop_event.is_set():
            documents.cancel_workspace();panel.status.set('Document save cancelled.');return
        def saved(result):
            if isinstance(result,dict):result='Error: save unconfirmed; choose Check last save.'
            if result.startswith('Error:'):documents.cancel_workspace()
            panel.status.set(result)
        jobs(panel).run(lambda:documents.commit_save(proposal['token'],panel.stop_event),saved)
    jobs(panel).run(prepare,proposed)


def check_save(panel,confirm):
    if not access(panel,confirm):return
    jobs(panel).run(documents.check_last_save,lambda result:panel.status.set(str(result)))


def show_documents(panel,confirm):
    if not access(panel,confirm):return
    win=tk.Toplevel(panel);win.title('Saved Documents');win.geometry('820x540');win.minsize(700,460)
    win.transient(panel.winfo_toplevel())
    colors=ttk.Style(panel);background=colors.lookup('TFrame','background') or '#f5f5f5';foreground=colors.lookup('TLabel','foreground') or '#111111'
    win.configure(bg=background)
    ttk.Label(win,text='Saved Documents',style='Title.TLabel').pack(anchor='w',padx=20,pady=(18,6))
    ttk.Label(win,text=str(documents.ROOT),wraplength=760).pack(anchor='w',padx=20)
    ttk.Label(win,text='New version files preserve history. Disk work runs separately; Stop can cancel it.',wraplength=760).pack(anchor='w',padx=20,pady=(5,12))
    # Reserve controls before the expanding list so small windows keep them visible.
    row=ttk.Frame(win);row.pack(side='bottom',fill='x',padx=20,pady=(8,18))
    recovery=ttk.Frame(win);recovery.pack(side='bottom',fill='x',padx=20)
    ttk.Button(recovery,text='Check last save',command=lambda:check_save(panel,confirm)).pack(side='left')
    status=tk.StringVar();ttk.Label(win,textvariable=status,wraplength=760).pack(side='bottom',fill='x',padx=20,pady=8)
    choices=tk.Listbox(win,font=('Segoe UI',11),height=10,exportselection=False,bg=background,fg=foreground,selectbackground='#2563eb',selectforeground='white',relief='flat',highlightthickness=1)
    choices.pack(fill='both',expand=True,padx=20)
    ttk.Label(row,text='Version 0 = latest').pack(side='left')
    version=tk.StringVar(value='0');ttk.Spinbox(row,from_=0,to=12,width=4,textvariable=version).pack(side='left',padx=6)
    records=[]
    def refresh():
        def fetch():return {'records':documents.workspace().list_records()}
        def ready(result):
            if not win.winfo_exists():return
            choices.delete(0,'end');records.clear()
            if 'error' in result:status.set('Documents unavailable or cancelled.');return
            for record in result['records']:
                number,current=record['document'],record['version'];records.append((number,current))
                choices.insert('end',f"{record['title']}  ·  Document {number}  ·  v{current}")
            status.set('Choose a document. Titles are untrusted text from the first nonempty line.' if records else 'No saved documents. Save a document Artifact first.')
        jobs(panel).run(fetch,ready)
    def selection():
        selected=choices.curselection()
        if not selected:raise ValueError('Select a saved document.')
        return records[selected[0]]
    def load():
        try:
            number,_=selection();wanted=int(version.get())
            if not panel.discard_ok():return
            original=panel.editor.get('1.0','end-1c')
            def loaded(result):
                if isinstance(result,dict) or result.startswith('Error:'):
                    panel.status.set(str(result));return
                match=re.search(r'^Document \d+, saved version \d+; latest is \d+\. Artifact (\d+), revision 1 contains',result,re.M)
                panel.refresh()
                if match and panel.editor.get('1.0','end-1c')==original:panel.load(int(match[1]))
                else:panel.status.set('Loaded as a new Artifact. Your newer editor changes were preserved.')
            jobs(panel).run(lambda:documents.document_read(number,wanted),loaded)
        except (ValueError,IndexError):status.set('Select a document and a version from 0 to 12.')
    def revise():
        try:number,current=selection();save_selected(panel,confirm,number,current)
        except (ValueError,IndexError):status.set('Select a saved document first.')
    ttk.Button(row,text='Load version',command=load).pack(side='left',padx=6)
    ttk.Button(row,text='Save Artifact here',command=revise).pack(side='left',padx=6)
    ttk.Button(row,text='Refresh',command=refresh).pack(side='right')
    refresh()
