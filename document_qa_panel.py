"""Person-only Sources Q&A window. No arbitrary agent dispatch or original-file opener."""
import queue
import threading
import tkinter as tk
from tkinter import ttk,filedialog

import document_qa as qa
from document_sources import import_source
from popup_windows import dismissible,scrolling_frame


class Cancellation:
    def __init__(self,*events):self.events=events
    def is_set(self):return any(event.is_set() for event in self.events)


def reset_sources(root):
    collection=getattr(root,'_source_collection',None)
    if collection is not None:collection.clear()


class SourcePanel:
    def __init__(self,ui):
        self.ui=ui;self.mail=queue.Queue();self.cancel=threading.Event();self.active=False;self.closed=False
        if not hasattr(ui.root,'_source_collection'):ui.root._source_collection=qa.Collection()
        self.collection=ui.root._source_collection;self.answer=None
        self.win=tk.Toplevel(ui.root);self.win.title('Sources · Document Q&A');self.win.transient(ui.root)
        dismissible(self.win,self.close,size=(1000,900))
        self.win.bind('<Destroy>',lambda event:self.close() if event.widget==self.win else None)
        self.status=tk.StringVar(value='Select sources, then ask a question. All listed sources are in scope.')
        ttk.Label(self.win,textvariable=self.status,style='Muted.TLabel',wraplength=700,padding=(18,8)).pack(side='bottom',fill='x')
        body=scrolling_frame(self.win);body.configure(padding=18);self.canvas=body.master
        ttk.Label(body,text='Ask your sources',style='Title.TLabel').pack(anchor='w')
        ttk.Label(body,text='Selected PDF and UTF-8 notes · local models · current chat only. No OCR for scans.',
                  style='Muted.TLabel',wraplength=850).pack(anchor='w',pady=(4,8))
        controls=ttk.Frame(body);controls.pack(fill='x')
        for label,callback in (('Add source',self.add),('Remove selected',self.remove),('Forget sources',self.forget)):
            ttk.Button(controls,text=label,command=callback).pack(side='left',padx=(0,6))
        self.tree=ttk.Treeview(body,columns=('name','pages','hash'),show='headings',selectmode='browse',height=3)
        for key,title,width in (('name','Selected snapshot',400),('pages','Pages',180),('hash','SHA-256 prefix',180)):
            self.tree.heading(key,text=title);self.tree.column(key,width=width,minwidth=80)
        self.tree.pack(fill='x',pady=8)
        ttk.Label(body,text='Question · uses all listed sources; Auto uses the small installed model',style='Muted.TLabel',wraplength=850).pack(anchor='w')
        self.question=self.textbox(body,3,editable=True)
        actions=ttk.Frame(body);actions.pack(fill='x',pady=8)
        ttk.Button(actions,text='Ask selected sources',command=self.ask,style='Accent.TButton').pack(side='left')
        ttk.Button(actions,text='Stop',command=ui.stop_agent).pack(side='left',padx=6)
        self.to_artifact=ttk.Button(actions,text='Keep answer in Artifacts',command=self.keep,state='disabled')
        self.to_artifact.pack(side='left')
        ttk.Label(body,text='Answer · quotes and citation IDs are checked; factual interpretation still needs your review.',
                  style='Muted.TLabel',wraplength=850).pack(anchor='w')
        self.output=self.textbox(body,8)
        evidence=ttk.Frame(body);evidence.pack(fill='x',pady=8)
        self.citations=ttk.Combobox(evidence,state='readonly',width=55)
        self.citations.pack(side='left',fill='x',expand=True)
        self.citations.bind('<<ComboboxSelected>>',lambda event:self.inspect())
        ttk.Button(evidence,text='Inspect citation',command=self.inspect).pack(side='left',padx=6)
        ttk.Label(body,text='Extracted source text · untrusted reference data; PDF numbers are physical pages, not printed labels.',
                  style='Muted.TLabel',wraplength=850).pack(anchor='w')
        self.page=self.textbox(body,8)
        self.refresh();ui.root.after(40,self.poll)

    def textbox(self,parent,height,editable=False):
        holder=ttk.Frame(parent);holder.pack(fill='both',expand=True,pady=4)
        text=tk.Text(holder,height=height,wrap='word',font=('Segoe UI',10),relief='flat',
            bg=self.ui.T('field'),fg=self.ui.T('text'),insertbackground=self.ui.T('text'),padx=10,pady=8)
        scrollbar=ttk.Scrollbar(holder,command=text.yview);scrollbar.pack(side='right',fill='y')
        text.configure(yscrollcommand=scrollbar.set);text.pack(side='left',fill='both',expand=True)
        if not editable:text.configure(state='disabled')
        return text

    def display(self,widget,text):
        widget.configure(state='normal');widget.delete('1.0','end');widget.insert('1.0',text);widget.configure(state='disabled')

    def close(self):self.closed=True;self.cancel.set()

    def invalidate(self):
        self.answer=None;self.to_artifact.configure(state='disabled')
        self.citations.configure(values=());self.citations.set('')
        self.display(self.output,'');self.display(self.page,'')

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for source in self.collection.sources:
            pages=f'{len(source.pages)} PDF pages' if source.kind=='pdf' else 'Unpaginated text'
            blank=sum(not p.strip() for p in source.pages)
            if blank:pages+=f' · {blank} empty'
            self.tree.insert('','end',iid=str(source.number),values=(source.name,pages,source.digest[:12]))

    def run(self,work,done):
        if self.ui.busy or self.active:return False
        self.ui.stop_event.clear();self.cancel.clear();token=Cancellation(self.cancel,self.ui.stop_event)
        self.active=True;self.ui.busy=True;self.ui.send_button.configure(state='disabled')
        self.ui.stop_button.configure(state='normal',text='Stop')
        self.status.set('Working locally. Stop discards late replies; an Ollama call may still be finishing.')
        def worker():
            try:result=work(token);error=None
            except Exception as exc:
                result=None;error=str(exc) if isinstance(exc,ValueError) else 'Local import or model request failed; no retry was made'
            self.mail.put((result,error,done))
        threading.Thread(target=worker,daemon=True).start();return True

    def poll(self):
        try:
            while True:
                result,error,done=self.mail.get_nowait();self.active=False
                self.ui.remove_pending();self.ui.finish_turn()
                if self.closed:continue
                if self.cancel.is_set() or self.ui.stop_event.is_set():self.status.set('Cancelled. Late results discarded.');continue
                if error:self.status.set('Error: '+error)
                else:
                    try:done(result)
                    except Exception as exc:self.status.set('Error: '+(str(exc) if isinstance(exc,ValueError) else 'Could not apply result'))
        except queue.Empty:pass
        if self.active or not self.closed:self.ui.root.after(40,self.poll)

    def add(self):
        if self.ui.busy:return
        if len(self.collection.sources)>=qa.MAX_SOURCES:self.status.set('Remove a source first; at most five can be selected.');return
        self.ui.stop_event.clear()
        path=filedialog.askopenfilename(parent=self.win,title='Choose a local source (8 MB maximum)',
            filetypes=[('PDF or UTF-8 notes','*.pdf *.txt *.md')])
        if not path or self.ui.stop_event.is_set():return
        number=self.collection.next_number
        def done(source):
            self.collection.add(source);self.invalidate();self.refresh()
            empty=sum(not p.strip() for p in source.pages)
            self.status.set('Selected snapshot: '+source.name+f'. {empty} pages have no extracted text; OCR is not available.'+
                            ' Closing keeps sources for this chat; New chat forgets them.')
        self.run(lambda token:import_source(path,number,token),done)

    def remove(self):
        if self.ui.busy:return
        selected=self.tree.selection()
        if not selected:self.status.set('Select a listed source to remove.');return
        self.collection.remove(int(selected[0]));self.invalidate();self.refresh();self.status.set('Snapshot forgotten. Original file unchanged.')

    def forget(self):
        if self.ui.busy:return
        self.collection.clear();self.invalidate();self.refresh();self.status.set('Sources forgotten from this chat. Original files unchanged.')

    def ask(self):
        if self.ui.busy:return
        try:question=qa.question_text(self.question.get('1.0','end-1c'))
        except ValueError as exc:self.status.set('Error: '+str(exc));return
        sources=tuple(self.collection.sources);model=self.ui.model_var.get()
        self.invalidate()
        def done(answer):
            self.answer=answer;self.display(self.output,answer.text)
            self.citations.configure(values=[f'{p.citation} · {p.source.location(p.page)}' for p in answer.passages])
            if answer.passages:self.citations.current(0);self.inspect()
            if answer.answerable:self.to_artifact.configure(state='normal')
            self.status.set(f'{len(answer.passages)} excerpts checked. Retrieval is keyword-based and may omit relevant pages; inspect quotes.')
        self.run(lambda token:qa.ask(sources,question,model,token,log=lambda line:self.ui.events.put(('log',line))),done)

    def inspect(self):
        index=self.citations.current()
        if self.answer is None or not 0<=index<len(self.answer.passages):return
        p=self.answer.passages[index]
        self.display(self.page,f'{p.citation} · {p.source.location(p.page)}\nSnapshot SHA-256: {p.source.digest}\n\n'
            f'Retrieved excerpt:\n{p.text}\n\nFull extracted page/text:\n{p.source.pages[p.page-1]}')

    def keep(self):
        if self.ui.busy or self.answer is None or not self.answer.answerable:return
        references='\n'.join(f'{p.citation}: {p.source.location(p.page)} · SHA-256 {p.source.digest}' for p in self.answer.passages)
        try:item=self.ui.artifact_store.create('Document Q&A','document',
            'Local model answer. Quotes match selected excerpts; review factual interpretation.\n\n'+self.answer.text+'\n\nSnapshot references:\n'+references)
        except ValueError as exc:self.status.set('Error: '+str(exc));return
        self.ui.artifact_panel.refresh()
        if not self.ui.artifact_panel.dirty:self.ui.show_artifacts();self.ui.artifact_panel.load(item.number)
        self.status.set(f'Kept as Artifact {item.number}. Use Chats & Projects to save it explicitly; source files are not stored there.')


def show_sources(ui):
    if ui.busy:
        ui.show('Sources','Wait for the current operation to finish.');return
    panel=getattr(ui.root,'_source_panel',None)
    if panel is not None and not panel.closed:panel.win.lift();return panel
    panel=SourcePanel(ui);ui.root._source_panel=panel;return panel
