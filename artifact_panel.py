"""Tk workspace with inert source and isolated static HTML/CSS pixel previews."""
from io import BytesIO
from pathlib import Path
import queue
import re
import threading
import tkinter as tk
from tkinter import ttk, filedialog
from popup_windows import decisions as messagebox

from artifacts import store, MAX_TEXT, MAX_MEDIA, export_snapshot
from artifact_media import prepare_preview
from artifact_web_preview import html_source, prepare_web_preview


class _PreviewStop:
    """Per-selection cancellation without stopping unrelated app workers."""
    def __init__(self, shared):
        self.shared, self.local = shared, threading.Event()

    def is_set(self):
        return self.local.is_set() or self.shared.is_set()

    def set(self):
        self.local.set()


class ArtifactPanel(ttk.Frame):
    def __init__(self, parent, stop_event, answer=lambda: "", confirm=None):
        super().__init__(parent, padding=20)
        self.stop_event, self.answer = stop_event, answer
        self.confirm=confirm
        from workspace_panel import save_selected
        self.selected = self.version = None
        self.dirty = False
        self.signature = None
        self.frames, self.photo = [], None
        self.playing = False
        self.play_job = None
        self.preview_stop = None
        self.serial = 0
        self.mail = queue.Queue()
        self.web_mail = queue.Queue()
        self.web_image = None
        self.view_mode = 'code'
        self.web_width = None
        heading=ttk.Frame(self)
        heading.pack(fill="x",pady=(0,4))
        ttk.Label(heading,text="Artifacts",style="Title.TLabel").pack(side="left")
        self.kind_label=ttk.Label(heading,text="WORKSPACE",style="Muted.TLabel")
        self.kind_label.pack(side="right")
        self.subtitle=ttk.Label(self,text="Your ideas, with room to take shape.",style="Muted.TLabel")
        self.subtitle.pack(anchor="w",pady=(0,16))
        self.choice = ttk.Combobox(self,state="readonly",font=("Segoe UI",10))
        self.choice.pack(fill="x",pady=(0,10))
        self.choice.bind("<<ComboboxSelected>>", self.choose)
        actions=ttk.Frame(self)
        actions.pack(fill="x",pady=(0,14))
        # Less-used actions live in one menu so the pane stays calm.
        self.more_menu=tk.Menu(self,tearoff=0)
        for text,callback in (("New blank draft",self.new),("Draft from last answer",self.from_answer),
                              ("Open generated image or video",self.open_generated),
                              ("Import a file",self.import_file),("Reload saved version",self.reload)):
            self.more_menu.add_command(label=text,command=callback)
        more=ttk.Button(actions,text="More  ...",width=0)
        more.configure(command=lambda:self.more_menu.tk_popup(more.winfo_rootx(),more.winfo_rooty()+more.winfo_height()))
        more.pack(side="left")
        ttk.Button(actions,text="Export",command=self.export,style="Accent.TButton",width=0).pack(side="right")
        ttk.Button(actions,text="Save new",command=lambda:save_selected(self,self.confirm),width=0).pack(side="right",padx=(0,5))
        history=ttk.Frame(self)
        history.pack(fill="x",pady=(0,12))
        ttk.Label(history,text="VERSION",style="Muted.TLabel").pack(side="left")
        self.history=ttk.Combobox(history,state="readonly",width=4,font=("Segoe UI",10))
        self.history.pack(side="left",padx=8)
        self.history.bind("<<ComboboxSelected>>",self.choose_version)
        self.restore_button=ttk.Button(history,text="Restore",command=self.restore,width=8)
        self.restore_button.pack(side="left")
        self.save_button=ttk.Button(history,text="Save edit",command=self.save,width=9)
        self.save_button.pack(side="right")
        self.status=tk.StringVar(value="Ask for an artifact, or choose New to start a draft.")
        footer=ttk.Frame(self)
        footer.pack(side="bottom",fill="x",pady=(12,0))
        self.status_label=ttk.Label(footer,textvariable=self.status,style="Muted.TLabel",wraplength=420)
        self.status_label.pack(fill="x")
        self.privacy_label=ttk.Label(footer,text="Drafts shared with local AI · Previews are pictures; code never runs.",
                                     style="Muted.TLabel",wraplength=420)
        self.privacy_label.pack(fill="x",pady=(7,0))
        self.bind("<Configure>",self.resize)
        self.play_row=ttk.Frame(self)
        self.view_row=ttk.Frame(self)
        self.view_row.pack(fill='x',pady=(0,10))
        self.preview_button=ttk.Button(self.view_row,text='Preview',command=self.show_web_preview)
        self.preview_button.pack(side='left',padx=(0,6))
        self.code_button=ttk.Button(self.view_row,text='Code',command=self.show_code)
        self.code_button.pack(side='left')
        self.preview_button.configure(state='disabled')
        self.code_button.configure(state='disabled')
        self.body=ttk.Frame(self)
        self.body.pack(fill="both",expand=True)
        self.editor=tk.Text(self.body,width=36,wrap="word",undo=True,font=("Segoe UI",12),relief="flat",bd=0,
                            padx=20,pady=18,spacing1=0,spacing2=3,spacing3=3,insertwidth=2)
        self.gutter=tk.Text(self.body,width=4,wrap="none",font=("Consolas",11),relief="flat",bd=0,
                            padx=8,pady=18,state="disabled",takefocus=False)
        self.gutter.grid(row=0,column=0,sticky="ns")
        self.gutter.grid_remove()
        bar=ttk.Scrollbar(self.body,command=self.editor.yview)
        self.editor.configure(yscrollcommand=lambda first,last:(bar.set(first,last),self.gutter.yview_moveto(first)))
        self.editor.grid(row=0,column=1,sticky="nsew")
        bar.grid(row=0,column=2,sticky="ns")
        self.text_bar=bar
        self.horizontal=ttk.Scrollbar(self.body,orient="horizontal",command=self.editor.xview)
        self.horizontal.grid(row=1,column=1,sticky="ew")
        self.horizontal.grid_remove()
        self.editor.configure(xscrollcommand=self.scroll_horizontal)
        self.body.rowconfigure(0,weight=1)
        self.body.columnconfigure(1,weight=1)
        self.editor.bind("<<Modified>>",self.modified)
        self.image=ttk.Label(self.body,anchor="center")
        self.web_canvas=tk.Canvas(self.body,highlightthickness=0,bd=0)
        self.web_scroll=ttk.Scrollbar(self.body,command=self.web_canvas.yview)
        self.web_canvas.configure(yscrollcommand=self.web_scroll.set)
        self.web_canvas.bind('<Configure>',lambda event:self.draw_web_preview())
        self.web_canvas.bind('<MouseWheel>',lambda event:self.web_canvas.yview_scroll(-int(event.delta/120),'units'))
        self.play_button=ttk.Button(self.play_row,text="Play / pause",command=self.toggle_play)
        self.play_button.pack(side="left")
        self.timeline=tk.Scale(self.play_row,from_=0,to=0,orient="horizontal",showvalue=False,
                               command=self.seek,relief="flat",bd=0,highlightthickness=0)
        self.timeline.pack(side="left",fill="x",expand=True)
        self.editor.configure(state="disabled")
        self.save_button.configure(state="disabled")
        self.restore_button.configure(state="disabled")
        self.after(150,self.tick)

    def resize(self,event):
        self.status_label.configure(wraplength=max(180,event.width-40))
        self.privacy_label.configure(wraplength=max(180,event.width-40))
        if event.height < 430:
            self.subtitle.pack_forget()
        elif not self.subtitle.winfo_manager():
            self.subtitle.pack(anchor="w",pady=(0,16),before=self.choice)

    def scroll_horizontal(self,first,last):
        self.horizontal.set(first,last)
        if (self.view_mode == 'code' and self.selected is not None and self.selected.kind == "code"
                and (float(first) > 0 or float(last) < 1)):
            self.horizontal.grid()
        else:
            self.horizontal.grid_remove()

    def apply_theme(self,palette):
        self.editor.configure(bg=palette["field"],fg=palette["text"],insertbackground=palette["accent"],
                              selectbackground=palette["select"],selectforeground=palette["text"])
        self.gutter.configure(bg=palette["field"],fg=palette["subtle"])
        self.more_menu.configure(bg=palette["card"],fg=palette["text"],activebackground=palette["select"],
                                 activeforeground=palette["text"],bd=0)
        self.editor.tag_configure("keyword",foreground=palette["accent"])
        self.editor.tag_configure("string",foreground=palette["green"])
        self.editor.tag_configure("comment",foreground=palette["subtle"])
        self.timeline.configure(bg=palette["card"],fg=palette["subtle"],troughcolor=palette["field"],
                                activebackground=palette["accent"])
        self.web_canvas.configure(bg=palette['field'])
        self.editor.tag_configure("heading",font=("Segoe UI Semibold",17),foreground=palette["accent"],spacing1=12,spacing3=10)

    def format_editor(self):
        code=self.selected is not None and self.selected.kind=="code"
        self.editor.configure(font=("Consolas",11) if code else ("Segoe UI",12),
                              spacing1=0,spacing2=0 if code else 3,spacing3=0 if code else 3)
        self.gutter.configure(state="normal")
        self.gutter.delete("1.0","end")
        if code:
            lines=int(self.editor.index("end-1c").split(".")[0])
            self.gutter.insert("1.0","\n".join(str(i) for i in range(1,lines+1)))
            self.gutter.grid()
            self.kind_label.configure(text=f"CODE · {lines} LINES")
        else:
            self.gutter.grid_remove()
            self.horizontal.grid_remove()
        self.gutter.configure(state="disabled")
        for tag in ("heading","keyword","string","comment"):
            self.editor.tag_remove(tag,"1.0","end")
        text=self.editor.get("1.0","end-1c")[:32000]
        if code:
            patterns = {"keyword": r"\b(?:def|class|return|import|from|if|else|for|while|const|let|function|export|async|await|print|True|False|None)\b",
                        "string": r"\"[^\"\n]*\"|'[^'\n]*'", "comment": r"#[^\n]*"}
            for tag,pattern in patterns.items():
                for match in re.finditer(pattern,text):
                    self.editor.tag_add(tag,f"1.0+{match.start()}c",f"1.0+{match.end()}c")
        else:
            for number,line in enumerate(text.splitlines(),1):
                if line.startswith(("# ","## ","### ")):
                    self.editor.tag_add("heading",f"{number}.0",f"{number}.end")

    def modified(self, event=None):
        if self.editor.edit_modified():
            self.dirty = True
            self.format_editor()
            self.editor.edit_modified(False)
            self.status.set("Unsaved edit. Save creates a new version; no file is written.")

    def discard_ok(self):
        return not self.dirty or messagebox.askyesno("Discard unsaved artifact edit?",
            "Your unsaved editor changes will be discarded. Continue?", parent=self, default="no") is True

    def stop(self):
        self.cancel_preview()
        self.pause_playback()
        self.serial += 1  # Discard decoder replies already queued before Stop.
        self.status.set("Preview paused by Stop. Text drafts and saved versions remain in memory.")

    def reset(self):
        self.cancel_preview()
        self.pause_playback()
        self.serial += 1
        self.selected = self.version = None
        self.dirty, self.playing = False, False
        self.frames, self.photo = [], None
        self.web_image = None
        self.web_canvas.grid_remove()
        self.web_scroll.grid_remove()
        self.view_mode = 'code'
        self.preview_button.configure(state='disabled',style='TButton')
        self.code_button.configure(state='disabled',style='TButton')
        self.signature = None
        self.choice.set("")
        self.choice.configure(values=())
        self.history.set("")
        self.history.configure(values=())
        self.image.configure(image="", text="")
        self.image.grid_remove()
        self.gutter.grid_remove()
        self.horizontal.grid_remove()
        self.kind_label.configure(text="WORKSPACE")
        self.play_row.pack_forget()
        self.editor.grid()
        self.text_bar.grid()
        self.editor.configure(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.edit_modified(False)
        self.editor.edit_reset()
        self.editor.configure(state="disabled")
        self.save_button.configure(state="disabled")
        self.restore_button.configure(state="disabled")
        self.status.set("Artifacts cleared. Exports and previously generated files remain on disk.")

    def refresh(self):
        items = store.items()
        signature = tuple((a.number, a.current.number) for a in items)
        if signature == self.signature:
            return
        previous_ids = {number for number, _ in self.signature or ()}
        new_media = [a for a in items if a.number not in previous_ids and
                     (a.kind in ("image", "video") or (a.kind=='code' and html_source(a.current.content) is not None))]
        self.signature = signature
        if items and getattr(self, "on_change", None):
            self.on_change()                       # chat-first window: slide the pane in
        self.choice.configure(values=[f"{a.number}: {a.title} ({a.kind})" for a in items])
        if not items:
            self.reset()
            self.signature = ()
        elif self.selected is None:
            self.load(items[-1].number)
        elif new_media and not self.dirty:
            if self.selected.number != new_media[-1].number:
                self.load(new_media[-1].number)
        elif new_media:
            latest = new_media[-1]
            self.status.set(f"New {latest.kind} ready: Artifact {latest.number} in the list above. "
                            "Your unsaved text is preserved; save it before switching.")
        elif not any(a.number == self.selected.number for a in items):
            self.reset()
            self.load(items[-1].number)
        elif store.get(self.selected.number).current.number != self.selected.current.number:
            if self.dirty:
                self.status.set("A newer revision arrived. Your unsaved text is preserved; copy it before Reload.")
            else:
                self.load(self.selected.number)

    def choose(self, event=None):
        index = self.choice.current()
        items = store.items()
        if 0 <= index < len(items) and self.discard_ok():
            self.load(items[index].number)
        elif self.selected:
            self.choice.set(f"{self.selected.number}: {self.selected.title} ({self.selected.kind})")

    def choose_version(self, event=None):
        if self.selected and self.discard_ok():
            self.load(self.selected.number, int(self.history.get()))
        elif self.version:
            self.history.set(str(self.version.number))

    def reload(self):
        if self.selected and self.discard_ok():
            self.load(self.selected.number)

    def load(self, number, revision=None, *, preview=None):
        self.cancel_preview()
        self.pause_playback()
        self.serial += 1
        self.frames, self.photo = [], None
        self.web_image = None
        self.web_width = None
        self.web_canvas.grid_remove()
        self.web_scroll.grid_remove()
        self.view_mode = 'code'
        self.image.configure(image="", text="")
        self.selected = store.get(number)
        a = self.selected
        self.kind_label.configure(text=a.kind.upper())
        self.version = next(v for v in a.versions if v.number == (revision or a.current.number))
        self.choice.set(f"{a.number}: {a.title} ({a.kind})")
        self.history.configure(values=[str(v.number) for v in a.versions])
        self.history.set(str(self.version.number))
        self.editor.configure(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", self.version.content)
        self.editor.edit_modified(False)
        self.editor.edit_reset()
        self.format_editor()
        self.dirty = False
        editable = a.kind in ("document", "code") and self.version.number == a.current.number
        self.editor.configure(state="normal" if editable else "disabled", wrap="none" if a.kind == "code" else "word")
        self.save_button.configure(state="normal" if editable else "disabled")
        self.restore_button.configure(state="normal" if a.kind in ("document", "code") and not editable else "disabled")
        self.play_row.pack_forget()
        if a.kind in ("document", "code"):
            self.image.grid_remove()
            self.editor.grid()
            self.text_bar.grid()
            self.status.set(f"Artifact {a.number}, revision {self.version.number}. {'Editable draft' if editable else 'Historical version'}; text only.")
            self.code_button.configure(state='normal',text='Code' if a.kind=='code' else 'Text',style='Accent.TButton')
            self.preview_button.configure(state='normal' if a.kind=='code' else 'disabled',style='TButton')
            if a.kind=='code' and html_source(self.version.content) is not None:
                self.show_web_preview()
            elif a.kind=='code':
                self.status.set('Source view. Visual preview supports HTML/CSS; this code is not executed.')
        else:
            self.preview_button.configure(state='disabled',style='TButton')
            self.code_button.configure(state='disabled',style='TButton')
            self.editor.grid_remove()
            self.text_bar.grid_remove()
            self.gutter.grid_remove()
            self.horizontal.grid_remove()
            self.image.grid(row=0, column=0, columnspan=3, sticky="nsew")
            self.image.configure(text="Preparing bounded local preview...")
            self.status.set("Decoding local media; no audio, browser, scripts or external links.")
            if preview is None:
                self.decode(a.kind, self.version.data)
            else:
                self.display_preview(preview)

    def show_code(self):
        if self.selected is None or self.selected.kind not in ('document','code'):
            return
        self.cancel_preview()
        self.serial += 1
        self.view_mode = 'code'
        self.web_canvas.grid_remove()
        self.web_scroll.grid_remove()
        self.image.grid_remove()
        self.editor.grid()
        self.text_bar.grid()
        self.format_editor()
        self.code_button.configure(style='Accent.TButton')
        self.preview_button.configure(style='TButton')
        self.status.set('Edit source, then choose Preview to see the current draft. Preview does not save changes.')

    def show_web_preview(self):
        if self.selected is None or self.selected.kind!='code':
            return
        content = self.editor.get('1.0','end-1c')
        if html_source(content) is None:
            self.status.set('Visual preview supports HTML/CSS webpages. This code stays in source view and is never executed.')
            return
        if self.stop_event.is_set():
            self.status.set('Preview cancelled by Stop. Start a new turn or New chat before previewing.')
            return
        self.cancel_preview()
        self.serial += 1
        serial = self.serial
        cancelled = self.preview_stop = _PreviewStop(self.stop_event)
        self.view_mode = 'preview'
        self.web_image = None
        self.web_width = None
        self.editor.grid_remove()
        self.text_bar.grid_remove()
        self.gutter.grid_remove()
        self.horizontal.grid_remove()
        self.image.grid_remove()
        self.web_canvas.delete('all')
        self.web_canvas.grid(row=0,column=0,columnspan=2,sticky='nsew')
        self.web_scroll.grid(row=0,column=2,sticky='ns')
        self.web_canvas.yview_moveto(0)
        self.web_canvas.create_text(20,24,anchor='nw',text='Preparing visual preview…',tags='notice')
        self.preview_button.configure(style='Accent.TButton')
        self.code_button.configure(style='TButton')
        self.status.set('Rendering static HTML/CSS. Scripts and external resources are disabled.')
        def work():
            try:
                image = prepare_web_preview(content,cancelled)
                if not cancelled.is_set():
                    self.web_mail.put((serial,image,None))
            except Exception:
                if not cancelled.is_set():
                    self.web_mail.put((serial,None,'Preview unavailable, stopped or over its limits. Source is preserved; choose Code.'))
        threading.Thread(target=work,daemon=True).start()

    def poll_web_preview(self):
        try:
            while True:
                serial,image,error = self.web_mail.get_nowait()
                if serial!=self.serial or self.view_mode!='preview' or self.stop_event.is_set():
                    continue
                if error:
                    self.web_canvas.delete('all')
                    self.web_canvas.create_text(20,24,anchor='nw',text=error,width=300)
                    self.status.set(error)
                else:
                    self.web_image = image
                    self.web_width = None
                    self.draw_web_preview()
                    source = 'Unsaved draft' if self.dirty else f'Revision {self.version.number}'
                    self.status.set(source + ' · Static HTML/CSS preview. Scroll to see more. Buttons and links are pictures.')
        except queue.Empty:
            pass

    def draw_web_preview(self):
        if self.view_mode!='preview' or self.web_image is None:
            return
        width=min(self.web_image.width,max(100,self.web_canvas.winfo_width()))
        if width==self.web_width:
            return
        from PIL import Image,ImageTk
        with Image.open(BytesIO(self.web_image.png)) as image:
            size=(width,max(1,round(image.height*width/image.width)))
            image=image.resize(size,Image.Resampling.LANCZOS)
            self.photo=ImageTk.PhotoImage(image)
        self.web_width=width
        self.web_canvas.delete('all')
        self.web_canvas.create_image(0,0,anchor='nw',image=self.photo)
        self.web_canvas.configure(scrollregion=(0,0,*size))

    def cancel_preview(self):
        if self.preview_stop is not None:
            self.preview_stop.set()
            self.preview_stop = None

    def display_preview(self, frames):
        self.frames = frames
        self.timeline.configure(to=len(frames) - 1)
        self.timeline.set(0)
        self.show_frame(0)
        if len(frames) > 1:
            self.play_row.pack(fill="x", pady=5)

    def decode(self, kind, data, imported=None):
        self.cancel_preview()
        cancelled = self.preview_stop = _PreviewStop(self.stop_event)
        serial = self.serial
        def work():
            try:
                if cancelled.is_set():
                    return
                result = prepare_preview(kind, data, cancelled)
                if not cancelled.is_set():
                    self.mail.put((serial, result, imported, None))
            except Exception:
                if not cancelled.is_set():
                    self.mail.put((serial, None, None, "Preview refused, stopped or unavailable. Check media limits/dependencies."))
        threading.Thread(target=work, daemon=True).start()

    def save(self):
        if not self.selected or not self.version:
            return
        try:
            a = store.revise(self.selected.number, self.version.number, self.editor.get("1.0", "end-1c"))
            self.load(a.number)
        except ValueError as exc:
            self.status.set(str(exc) + ". Your editor text is preserved.")

    def restore(self):
        if not self.selected or not self.version or not self.discard_ok():
            return
        try:
            a = store.restore(self.selected.number, self.selected.current.number, self.version.number)
            self.load(a.number)
        except ValueError as exc:
            self.status.set(str(exc))

    def new(self):
        try:
            a = store.create("Untitled document", "document", "Start writing here.")
            self.refresh()
            if self.discard_ok():
                self.load(a.number)
        except ValueError as exc:
            self.status.set(str(exc))

    def from_answer(self):
        text = self.answer()
        try:
            a = store.create("From last answer", "code" if html_source(text) is not None else "document", text)
            self.refresh()
            if self.discard_ok():
                self.load(a.number)
        except ValueError as exc:
            self.status.set(str(exc))

    def export(self):
        if not self.selected or not self.version:
            return
        if self.dirty:
            self.status.set("Save your edit as a version before exporting.")
            return
        # Freeze selected bytes before the person's modal picker; model edits cannot change them.
        artifact, version = self.selected, self.version
        suffix = {"document": ".md", "code": ".txt", "image": ".png", "video": ".mp4"}[artifact.kind]
        destination = filedialog.asksaveasfilename(parent=self, title="Export this artifact version (new file only)",
            defaultextension=suffix, initialfile=f"artifact-{artifact.number}-v{version.number}{suffix}",
            filetypes=[("Artifact file", "*" + suffix)])
        if not destination:
            return
        if self.stop_event.is_set():
            self.status.set("Export cancelled by Stop.")
            return
        try:
            export_snapshot(artifact, version, destination)
            self.status.set("Selected version exported. Existing files are never overwritten.")
        except (ValueError, OSError):
            self.status.set("Export failed. Choose a new file with the displayed extension; existing files are never overwritten.")

    def import_file(self):
        if not self.discard_ok():
            return
        path = filedialog.askopenfilename(parent=self, title="Import text for local AI or media for preview (never run)",
            filetypes=[("Text, code or media", "*.txt *.md *.py *.js *.html *.css *.json *.svg *.png *.jpg *.jpeg *.webp *.mp4")])
        if not path:
            return
        source = Path(path)
        kind = "video" if source.suffix.lower() == ".mp4" else "image" if source.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") else "document" if source.suffix.lower() in (".md", ".txt") else "code"
        try:
            with source.open("rb") as file:
                data = file.read((MAX_MEDIA if kind in ("video", "image") else MAX_TEXT * 4) + 1)
            if kind in ("document", "code"):
                a = store.create("Imported " + kind, kind, data.decode("utf-8-sig"))
                self.refresh()
                self.load(a.number)
            else:
                if len(data) > MAX_MEDIA:
                    raise ValueError("media exceeds 20 MB")
                self.serial += 1
                self.pause_playback()
                self.status.set("Validating imported media before adding it...")
                self.decode(kind, data, (kind, data, self.editor.get("1.0", "end-1c")))
        except (OSError, ValueError):
            self.status.set("Import refused: invalid UTF-8 text, too large, or artifact limit reached.")

    def open_generated(self):
        """Person-only recovery from this installation's generated folder; no model paths."""
        from artifacts import record_generated
        from generation_tools import OUTPUT_DIR
        if self.stop_event.is_set():
            self.status.set("Open generated cancelled by Stop; start a new turn or New chat first.")
            return
        if not self.discard_ok():
            return
        path = filedialog.askopenfilename(parent=self, title="Open a previous generated image or video",
            initialdir=str(OUTPUT_DIR), filetypes=[("Generated media", "*.png *.mp4")])
        if not path or self.stop_event.is_set():
            return
        try:
            kind = "image" if Path(path).suffix == ".png" else "video"
            artifact = record_generated(path, kind)
            self.refresh()
            if self.selected is None or self.selected.number != artifact.number:
                self.load(artifact.number)
        except (OSError, ValueError, TypeError):
            self.status.set("Open refused: choose an original PNG/MP4 from this app's generated folder, "
                            "within the Artifact limits. Use Import a file for other folders.")

    def show_frame(self, index):
        if not self.frames:
            return
        from PIL import Image, ImageTk
        index = max(0, min(int(index), len(self.frames) - 1))
        stamp, prepared = self.frames[index]
        with Image.open(BytesIO(prepared.png)) as image:
            image.thumbnail((max(100, self.winfo_width() - 30), max(100, self.body.winfo_height() - 20)))
            self.photo = ImageTk.PhotoImage(image)
        self.image.configure(image=self.photo, text="")
        self.status.set(f"{self.selected.kind.title()} preview: {stamp:.2f}s. Local pixels only; audio is not played.")

    def seek(self, value):
        self.show_frame(int(float(value)))

    def toggle_play(self):
        if len(self.frames) > 1:
            if self.playing:
                self.pause_playback()
            else:
                self.playing = True
                self.advance(self.serial)

    def pause_playback(self):
        self.playing = False
        if self.play_job is not None:
            self.after_cancel(self.play_job)
            self.play_job = None

    def advance(self, serial):
        self.play_job = None
        if not self.playing or serial != self.serial or not self.frames or self.stop_event.is_set():
            self.playing = False
            return
        index = int(self.timeline.get())
        next_index = (index + 1) % len(self.frames)
        delay = self.frames[next_index][0] - self.frames[index][0] if next_index else .125
        self.timeline.set(next_index)
        self.play_job = self.after(max(30, min(1000, int(delay * 1000))), lambda: self.advance(serial))

    def tick(self):
        self.refresh()
        if getattr(self,'web_mail',None) is not None:
            self.poll_web_preview()
        try:
            while True:
                serial, frames, imported, error = self.mail.get_nowait()
                if serial != self.serial or self.stop_event.is_set():
                    continue
                if error:
                    self.image.configure(text=error)
                    self.status.set(error)
                elif imported:
                    kind, data, original_text = imported
                    # Normalize imported images; exported image bytes are always PNG.
                    a = store.media("Imported " + kind, kind, frames[0][1].png if kind == "image" else data)
                    if self.editor.get("1.0", "end-1c") != original_text:
                        self.dirty = True
                        self.refresh()
                        self.status.set(f"Imported {kind} ready: Artifact {a.number}. Your newer unsaved text is preserved.")
                    else:
                        self.load(a.number, preview=frames)
                        self.refresh()
                else:
                    self.display_preview(frames)
        except queue.Empty:
            pass
        except ValueError as exc:
            self.status.set(str(exc))
        self.after(150, self.tick)
