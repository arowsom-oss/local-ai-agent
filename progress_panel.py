"""Compact native task progress with a RAM-only evidence detail panel."""
import tkinter as tk
from tkinter import ttk
from popup_windows import dismissible


class ProgressPanel(ttk.Frame):
    def __init__(self,parent,tracker,resume):
        super().__init__(parent,padding=(0,4));self.tracker=tracker;self.resume=resume;self.window=None;self.last=None
        self.title=ttk.Label(self,text='Task progress · Ready',style='Muted.TLabel')
        self.title.pack(anchor='w')
        row=ttk.Frame(self);row.pack(fill='x',pady=(3,0))
        self.summary=ttk.Label(row,text='Verified results appear here.',style='Muted.TLabel')
        self.summary.pack(side='left',fill='x',expand=True)
        ttk.Button(row,text='Details',width=0,command=self.details).pack(side='right')
        self.resume_button=ttk.Button(row,text='Resume',width=0,command=resume,state='disabled')
        self.resume_button.pack(side='right',padx=(4,5))
        self.after(100,self.refresh)

    def details(self):
        if self.window is not None and self.window.winfo_exists():self.window.lift();return
        win=self.window=tk.Toplevel(self);win.title('Task progress and checkpoints');win.geometry('820x600');win.minsize(600,420)
        win.transient(self.winfo_toplevel())
        dismissible(win,size=(820,600))
        frame=ttk.Frame(win,padding=20);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='Task progress',style='Title.TLabel').pack(anchor='w')
        ttk.Label(frame,text='Proposed steps grant no permission. Only code can report a verified result.',wraplength=740).pack(anchor='w',pady=(6,12))
        self.detail_resume=ttk.Button(frame,text='Resume with fresh checks',command=self.resume)
        self.detail_resume.pack(side='bottom',anchor='e',pady=(12,0))
        holder=ttk.Frame(frame);holder.pack(fill='both',expand=True)
        self.text=tk.Text(holder,wrap='word',font=('Segoe UI',11),padx=14,pady=12,state='disabled',relief='flat')
        self.text.pack(side='left',fill='both',expand=True)
        bar=ttk.Scrollbar(holder,command=self.text.yview);bar.pack(side='right',fill='y');self.text.configure(yscrollcommand=bar.set)
        self.render(self.tracker.snapshot())

    def render(self,s):
        self.title.configure(text='Task progress · '+s.phase)
        idle=(s.phase in ('Ready','Reply ready') and not s.verified and not s.observations
              and not s.resumable and not s.proposed)
        if getattr(self,'on_idle',None):self.on_idle(idle)
        self.summary.configure(text=f'Verified: {s.verified} · Reads: {s.observations}')
        state='normal' if s.resumable else 'disabled'
        self.resume_button.configure(state=state)
        if self.window is not None and self.window.winfo_exists():
            style=ttk.Style(self);background=style.lookup('TFrame','background') or '#ffffff';foreground=style.lookup('TLabel','foreground') or '#111111'
            self.text.configure(state='normal',bg=background,fg=foreground);self.text.delete('1.0','end')
            self.text.insert('end',f'Status: {s.phase}\nVerified tool results: {s.verified} · Completed reads: {s.observations}\n')
            self.text.insert('end','A model reply is not proof that the whole task is complete.\nCheckpoints stay in memory; New chat clears them.\n\n')
            self.text.insert('end','PROPOSED STEPS · MODEL TEXT · UNVERIFIED\n')
            if s.proposed:
                for number,step in enumerate(s.proposed,1):self.text.insert('end',f'{number}. {step}\n')
            else:self.text.insert('end','No outline supplied. Actual tool evidence still appears below.\n')
            self.text.insert('end','\nCODE REPORTED ACTION HISTORY · MOST RECENT 100 EVENTS\n')
            for row in s.rows:self.text.insert('end',f'{row.state} · {row.label}\n')
            if not s.rows:self.text.insert('end','No actions recorded.\n')
            self.text.configure(state='disabled');self.detail_resume.configure(state=state)

    def refresh(self):
        s=self.tracker.snapshot()
        if s!=self.last:self.render(s);self.last=s
        self.after(100,self.refresh)
