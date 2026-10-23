"""Person-only saved chat/Project utility. Background DB jobs never touch Tk."""
from copy import deepcopy
from datetime import datetime
import queue
import threading
import tkinter as tk
from tkinter import ttk,filedialog

from popup_windows import dismissible,decisions,scrolling_frame
import chat_library as saved


class LibraryPanel:
    def __init__(self,ui):
        self.ui=ui;self.mail=queue.Queue();self.active=False;self.rows=[];self.projects=[]
        self.closed=False
        self.win=tk.Toplevel(ui.root);self.win.title('Chats & Projects');self.win.transient(ui.root)
        self.win.bind('<Destroy>',lambda event:setattr(self,'closed',True) if event.widget==self.win else None)
        dismissible(self.win,size=(980,850))
        self.status=tk.StringVar(value='Search titles or choose a saved chat. Saving is explicit.')
        ttk.Label(self.win,textvariable=self.status,wraplength=500,style='Muted.TLabel',padding=(18,8)).pack(side='bottom',fill='x')
        frame=scrolling_frame(self.win);frame.configure(padding=18)
        self.scroll_canvas=frame.master
        ttk.Label(frame,text='Chats & Projects',style='Title.TLabel').pack(anchor='w')
        ttk.Label(frame,text='Save only when you choose. Stored locally without encryption; never uploaded.',
                  style='Muted.TLabel',wraplength=500).pack(anchor='w',pady=(4,12))
        row=ttk.Frame(frame);row.pack(fill='x')
        self.query=tk.StringVar();self.query_entry=ttk.Entry(row,textvariable=self.query)
        self.query_entry.pack(side='left',fill='x',expand=True)
        self.query_entry.bind('<Return>',lambda event:self.refresh())
        ttk.Button(row,text='Search titles',command=self.refresh).pack(side='left',padx=6)
        self.project=ttk.Combobox(row,state='readonly',width=22)
        self.project.pack(side='left');self.project.bind('<<ComboboxSelected>>',lambda event:self.refresh())
        projects=ttk.Frame(frame);projects.pack(fill='x',pady=8)
        for index,(text,callback) in enumerate((('New Project',lambda:self.project_editor()),('Edit Project',self.edit_project),
                ('Remove Project',self.delete_project),('New chat in Project',self.new_project_chat))):
            ttk.Button(projects,text=text,command=callback).grid(row=index//2,column=index%2,sticky='ew',padx=(0,6),pady=3)
        holder=ttk.Frame(frame);holder.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(holder,columns=('title','project','updated'),show='headings',selectmode='browse',height=5)
        for name,width in (('title',300),('project',130),('updated',130)):
            self.tree.heading(name,text=name.title());self.tree.column(name,width=width,minwidth=80)
        self.tree.pack(side='left',fill='both',expand=True)
        scrollbar=ttk.Scrollbar(holder,command=self.tree.yview);scrollbar.pack(side='right',fill='y')
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind('<<TreeviewSelect>>',self.selected)
        actions=ttk.Frame(frame);actions.pack(fill='x',pady=10)
        for text,callback in (('Open selected',self.open_selected),('Export transcript',self.export_selected),('Delete saved',self.delete_selected)):
            ttk.Button(actions,text=text,command=callback).pack(side='left',padx=(0,6))
        ttk.Separator(frame).pack(fill='x',pady=6)
        ttk.Label(frame,text='Save the current conversation',style='Muted.TLabel').pack(anchor='w')
        self.save_target=ttk.Label(frame,text=('Opened saved chat: '+ui.saved_chat['title']) if ui.saved_chat else 'Current chat has no opened saved copy.',
                                   style='Muted.TLabel',wraplength=500)
        self.save_target.pack(anchor='w',pady=(3,0))
        self.title=tk.StringVar(value=ui.saved_chat.get('title','') if ui.saved_chat else 'Untitled chat')
        self.title_entry=ttk.Entry(frame,textvariable=self.title);self.title_entry.pack(fill='x',pady=6)
        save_row=ttk.Frame(frame);save_row.pack(fill='x')
        ttk.Button(save_row,text='Save new copy',command=lambda:self.save_current(False),style='Accent.TButton').pack(side='left')
        ttk.Button(save_row,text='Update opened chat',command=lambda:self.save_current(True)).pack(side='left',padx=6)
        ui.root.after(40,self.poll)
        self.refresh()

    def run(self,work,done,settle=None):
        if self.active or self.ui.busy:
            self.status.set('Wait for the current operation to finish.');return
        self.active=True;self.ui.busy=True
        self.ui.send_button.configure(state='disabled')
        self.status.set('Working on the local library…')
        def background():
            try: result=work();error=None
            except Exception as exc:
                result=None
                error=str(exc) if isinstance(exc,ValueError) else 'Local library unavailable, locked or invalid; nothing was opened.'
            self.mail.put((result,error,done,settle))
        threading.Thread(target=background,daemon=True).start()

    def poll(self):
        try:
            while True:
                result,error,done,settle=self.mail.get_nowait()
                self.active=False;self.ui.remove_pending();self.ui.finish_turn()
                if not error and settle is not None:settle(result)
                if self.closed:continue
                if error:self.status.set('Error: '+error)
                else:
                    try:done(result)
                    except Exception:self.status.set('Error: operation could not finish; refresh before retrying.')
        except queue.Empty:pass
        if not self.closed or self.active:self.ui.root.after(40,self.poll)

    def project_id(self):
        index=self.project.current()
        return self.projects[index-1]['id'] if 0<index<=len(self.projects) else None

    def refresh(self,notice=None):
        selected=self.project_id() if self.project.current()>=0 else self.ui.current_project
        query=self.query.get()
        def read():
            projects=saved.library.projects()
            current=selected if any(p['id']==selected for p in projects) else None
            return projects,saved.library.list_chats(query,current)
        def done(result):
            self.projects,self.rows=result
            self.project.configure(values=['All / Unfiled']+[p['title'] for p in self.projects])
            self.project.current(next((i+1 for i,p in enumerate(self.projects) if p['id']==selected),0))
            self.tree.delete(*self.tree.get_children())
            names={p['id']:p['title'] for p in self.projects}
            for row in self.rows:
                self.tree.insert('', 'end',iid=str(row['id']),values=(row['title'],names.get(row['project'],'Unfiled'),
                    datetime.fromtimestamp(row['updated']).strftime('%b %d %H:%M')))
            self.status.set(notice or f'{len(self.rows)} saved chats. Saving is explicit; closing this panel changes no chat.')
        self.run(read,done)

    def chosen(self):
        selection=self.tree.selection()
        if not selection:raise ValueError('Select a saved chat first')
        return next(row for row in self.rows if str(row['id'])==selection[0])

    def selected(self,event=None):
        # Selection targets Open/Export/Delete. It must not rename or retarget the
        # independently opened conversation's Save/Update controls.
        pass

    def save_current(self,update):
        if self.ui.busy:return
        if self.ui.artifact_panel.dirty:
            self.status.set('Save edit in Artifacts first. Your unsaved editor buffer is not silently discarded.');return
        current=dict(self.ui.saved_chat) if self.ui.saved_chat else None
        if update and current is None:
            self.status.set('Open a saved chat first, or choose Save new copy.');return
        title=self.title.get();project=self.project_id()
        messages=deepcopy(self.ui.conversation_entries);items=self.ui.artifact_store.items()
        def settle(result):
            self.ui.saved_chat=result
            self.ui.current_project=result['project']
        def done(result):
            self.save_target.configure(text='Opened saved chat: '+result['title'])
            self.refresh('Saved locally with Artifact versions and media. Approvals and tool sessions were not saved.')
        self.run(lambda:saved.library.save(title,project,messages,items,
            chat=current['id'] if update else None,expected_version=current['version'] if update else 0),done,settle)

    def open_selected(self):
        if self.ui.busy:return
        try:row=self.chosen()
        except ValueError as exc:self.status.set(str(exc));return
        if decisions.askyesno('Open saved chat',
            'Replace this in-memory conversation and its drafts? Save it first if needed.\n\n'
            'Saved chats remain on disk. Old browser controls and permissions will be reset. Nothing runs automatically.',
            parent=self.win,default='no') is not True:return
        self.ui.stop_event.clear()  # Explicit idle person action, like opening Documents.
        def done(result):
            if self.ui.stop_event.is_set():
                self.status.set('Open cancelled by Stop. Saved chat remains on disk.');return
            if self.ui.open_saved_chat(result):
                self.win._dismiss_popup()
        self.run(lambda:saved.library.load(row['id']),done)

    def delete_selected(self):
        if self.ui.busy:return
        try:row=self.chosen()
        except ValueError as exc:self.status.set(str(exc));return
        if decisions.askyesno('Delete saved chat','Delete this saved copy and its stored Artifact snapshots?\n\n'
                +row['title']+'\n\nThe current open conversation and generated/exported files remain. This is not secure erasure.',
                parent=self.win,default='no') is not True:return
        def settle(result):
            if self.ui.saved_chat and self.ui.saved_chat['id']==row['id']:self.ui.saved_chat=None
        def done(result):
            self.refresh('Saved copy deleted. Current open work and exported files remain.')
        self.run(lambda:saved.library.delete_chat(row['id'],row['version']),done,settle)

    def export_selected(self):
        if self.ui.busy:return
        try:row=self.chosen()
        except ValueError as exc:self.status.set(str(exc));return
        destination=filedialog.asksaveasfilename(parent=self.win,title='Export saved transcript (new .txt only)',
            defaultextension='.txt',initialfile=f'chat-{row["id"]}.txt',filetypes=[('Transcript','*.txt')])
        if not destination:return
        from pathlib import Path
        def work():
            path=Path(destination)
            if path.suffix.lower()!='.txt' or ':' in path.name:raise ValueError('Choose a new .txt file')
            chat=saved.library.load(row['id'])
            body=chat['title']+'\n\n'+'\n\n'.join(m['role'].upper()+'\n'+m['content'] for m in chat['messages'])
            with path.open('x',encoding='utf-8',newline='\n') as file:file.write(body)
        self.run(work,lambda result:self.status.set('Transcript exported. Existing files are never overwritten; Artifacts stay in the library.'))

    def project_editor(self,project=None):
        if self.ui.busy:return
        current=next((p for p in self.projects if p['id']==project),None)
        win=tk.Toplevel(self.win);win.title('Project');win.transient(self.win)
        dismissible(win,size=(650,440))
        body=ttk.Frame(win,padding=18);body.pack(fill='both',expand=True)
        ttk.Label(body,text='Project name').pack(anchor='w')
        title=ttk.Entry(body);title.pack(fill='x',pady=6);title.insert(0,current['title'] if current else '')
        ttk.Label(body,text='Reference notes · 2000 characters · never permission to act',style='Muted.TLabel',wraplength=500).pack(anchor='w')
        notes=tk.Text(body,height=7,wrap='word',font=('Segoe UI',11),bg=self.ui.T('field'),fg=self.ui.T('text'),
                      insertbackground=self.ui.T('text'),relief='flat');notes.pack(fill='both',expand=True,pady=8)
        notes.insert('1.0',current['notes'] if current else '')
        def save():
            if self.ui.busy:
                self.status.set('Wait for the current operation; your Project editor stays open.');return
            values=title.get(),notes.get('1.0','end-1c')
            self.run(lambda:saved.library.save_project(*values,project=project),lambda result:self.refresh('Project saved. Notes apply as reference when a saved chat is reopened.'))
            win._dismiss_popup()
        ttk.Button(body,text='Save Project',command=save,style='Accent.TButton').pack(anchor='e')

    def edit_project(self):
        project=self.project_id()
        if project is None:self.status.set('Select a Project first.');return
        self.project_editor(project)

    def new_project_chat(self):
        if self.ui.busy:return
        project=next((p for p in self.projects if p['id']==self.project_id()),None)
        if project is None:self.status.set('Select a Project first.');return
        # new_chat can close this utility panel; capture the validated Project first.
        self.ui.start_project_chat(dict(project))

    def delete_project(self):
        if self.ui.busy:return
        project=self.project_id()
        if project is None:self.status.set('Select a Project first.');return
        if decisions.askyesno('Remove Project','Remove this Project and its notes? Its saved chats move to Unfiled; they are not deleted.',
                parent=self.win,default='no') is not True:return
        self.run(lambda:saved.library.delete_project(project),lambda result:self.refresh('Project removed; saved chats kept.'))


def show_library(ui):
    if ui.busy:
        ui.show('Chats','Wait for the current operation to finish.');return
    existing=getattr(ui.root,'_chat_library_panel',None)
    if existing is not None and not existing.closed:
        existing.win.lift();return existing
    panel=LibraryPanel(ui);ui.root._chat_library_panel=panel
    return panel
