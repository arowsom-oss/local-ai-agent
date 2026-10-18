"""Person-controlled workspace browser and exact-save previews; no shell or file picker."""
import re
import tkinter as tk
from tkinter import ttk
from artifacts import store
import workspace_documents as documents


def access(panel,confirm):
    if panel.stop_event.is_set():
        panel.status.set('Stopped. Send a new request before opening Documents.');return False
    if not documents.workspace_allowed():
        if confirm is None or confirm('workspace_access',{'folder':str(documents.ROOT)}) is not True:return False
        if panel.stop_event.is_set():return False
        documents.grant_workspace()
    return True


def save_selected(panel,confirm,document=0,version=0):
    if panel.dirty:
        panel.status.set('Save edit as an Artifact version before saving to Documents.');return
    if panel.selected is None or panel.version is None or panel.selected.kind!='document':
        panel.status.set('Select a document Artifact first.');return
    if not access(panel,confirm):return
    proposal=documents.prepare_save(artifact=panel.selected.number,revision=panel.version.number,document=document,version=version)
    if 'error' in proposal:panel.status.set('Error: '+proposal['error']);return
    if confirm('document_save_exact',proposal['preview']) is not True or panel.stop_event.is_set():
        documents.cancel_workspace();panel.status.set('Document save cancelled.');return
    result=documents.commit_save(proposal['token'],panel.stop_event)
    if result.startswith('Error:'):documents.cancel_workspace()
    panel.status.set(result)


def show_documents(panel,confirm):
    if not panel.discard_ok() or not access(panel,confirm):return
    win=tk.Toplevel(panel);win.title('Saved Documents');win.geometry('780x500');win.minsize(620,420)
    win.transient(panel.winfo_toplevel())
    colors=ttk.Style(panel)
    background=colors.lookup('TFrame','background') or '#f5f5f5'
    foreground=colors.lookup('TLabel','foreground') or '#111111'
    win.configure(bg=background)
    ttk.Label(win,text='Saved Documents',style='Title.TLabel').pack(anchor='w',padx=20,pady=(18,6))
    ttk.Label(win,text=str(documents.ROOT),wraplength=720).pack(anchor='w',padx=20)
    ttk.Label(win,text='Each save creates a new text file. Earlier versions remain available for recovery.',wraplength=720).pack(anchor='w',padx=20,pady=(5,12))
    choices=tk.Listbox(win,font=('Segoe UI',11),height=10,exportselection=False,bg=background,fg=foreground,
        selectbackground='#2563eb',selectforeground='white',relief='flat',highlightthickness=1)
    choices.pack(fill='both',expand=True,padx=20)
    status=tk.StringVar();ttk.Label(win,textvariable=status,wraplength=720).pack(fill='x',padx=20,pady=8)
    row=ttk.Frame(win);row.pack(fill='x',padx=20,pady=(0,18))
    ttk.Label(row,text='Version 0 means latest').pack(side='left')
    version=tk.StringVar(value='0');ttk.Spinbox(row,from_=0,to=12,width=4,textvariable=version).pack(side='left',padx=6)
    records=[]
    def refresh():
        listing=documents.document_list();choices.delete(0,'end');records.clear()
        for line in listing.splitlines():
            match=re.match(r'Document (\d+): .*; (\d+) saved versions$',line)
            if match:
                records.append((int(match[1]),int(match[2])))
                choices.insert('end',f'Document {match[1]} · latest version {match[2]}')
        status.set(listing if not records else 'Select a document to load or revise. Loading shares its text with local AI.')
    def selection():
        selected=choices.curselection()
        if not selected:raise ValueError('Select a saved document.')
        return records[selected[0]]
    def load():
        try:
            number,_=selection();wanted=int(version.get())
            if not panel.discard_ok():return
            before={a.number for a in store.items()};result=documents.document_read(number,wanted)
            if result.startswith('Error:'):status.set(result);return
            added=[a for a in store.items() if a.number not in before]
            if added:panel.refresh();panel.load(added[-1].number)
            status.set('Loaded into Artifacts. Older versions can be saved as a new latest version after review.')
        except (ValueError,IndexError):status.set('Select a document and a version from 0 to 12.')
    def revise():
        try:
            number,current=selection()
            # A fresh read is required before this approval; it must not replace the selected draft.
            workspace=documents.workspace()
            with workspace.access():
                inventory=workspace.catalog();key=workspace.numbers.get(number)
                if inventory.get(key)!=current:raise ValueError('Saved history changed. Reload the list.')
                with workspace.files.reader(key,current) as data:
                    workspace.observed[number]=(key,current,documents.digest(data))
            save_selected(panel,confirm,number,current);refresh()
        except (ValueError,OSError):status.set('Document changed or unavailable. Refresh and read it again.')
    ttk.Button(row,text='Load version',command=load).pack(side='left',padx=6)
    ttk.Button(row,text='Save Artifact here',command=revise).pack(side='left',padx=6)
    ttk.Button(row,text='Refresh',command=refresh).pack(side='right')
    refresh()
