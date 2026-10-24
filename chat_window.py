import json
import queue
from collections import deque
import re
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
from popup_windows import decisions as messagebox
from urllib.parse import urlparse

import attach
from model_router import release_models
from vision_input import load_image
from desktop_tools import desktop_start, close_desktop, capture_practice, start_practice
from process_guard import stop_all
from media_input import prepare_media
from browser_tool import close_browser
from edge_tools import start_edge,close_edge
from edge_work_browser import start_work,work_current,PROFILE as EDGE_WORK_PROFILE
from agent_core import run_turn, MODEL_CHOICES, SAFE, AUDIT_LOG, forget_sites
from artifacts import store as artifact_store
from artifact_panel import ArtifactPanel
from ui_theme import PALETTES, configure_styles
from notepad_tools import start_notepad, close_notepad
from workspace_documents import reset_workspace, cancel_workspace, save_uncertain
from task_progress import TaskProgress
from progress_panel import ProgressPanel
from app_brand import set_app_identity,set_window_icon
from popup_windows import dismissible,place_popup,wait_modal,scrolling_frame

# ---- shared state -------------------------------------------------------
messages = []            # the conversation; lives as long as the window is open
stop_event = threading.Event()   # set by the Stop button, checked by the worker between steps
emergency_ui = threading.Event()  # Separate watcher also runs inside modal Tk wait loops.
events = queue.Queue()   # worker thread -> window: things to show or ask about
busy = False             # True while the model is working on a question
task_progress=TaskProgress()
last_answer = ""         # the newest agent reply, for the "Copy last answer" button
last_raw_answer = ""     # Preserve code fences when the person copies an answer to Artifacts.
pending_image = None     # immutable preview-approved bytes, for one turn only
pending_media = None
speak_replies = False    # Person-only opt-in, revoked by Stop and New chat.
recording_done = None
activity_lines=deque(maxlen=100)  # Routine tool/timing details stay out of the conversation.
activity_box=None
conversation_entries=[]  # Explicitly saved user/visible-assistant text; no tool protocol or reasoning.
saved_chat=None
current_project=None
restored_chat=False

# Reading settings. Change these and re-run if they don't feel right for you.
FONT_NAME = "Segoe UI"
font_size = 12
UI_FONT = "Segoe UI"
THEMES = PALETTES
theme_name = "dark"
buttons = []             # every button made by make_button, so apply_theme can repaint them
notepad_status=None
NOTEPAD_PHASES={"closed":"Notepad · closed","ready":"Notepad · ready to read",
    "observed":"Notepad · draft observed","review":"Notepad · awaiting approval",
    "applying":"Notepad · applying & verifying","verified":"Notepad · edit verified",
    "paused":"Notepad · paused — review draft"}


def set_notepad_phase(phase):
    if phase not in NOTEPAD_PHASES:return
    if stop_event.is_set() and phase!="closed":return
    if notepad_status is not None:notepad_status.set(NOTEPAD_PHASES[phase])


def T(key):
    """One color from the current mode, e.g. T("accent")."""
    return THEMES[theme_name][key]

# The spinner: one character that cycles while the agent works. Change it if you like.
SPINNER = "\u25d0\u25d3\u25d1\u25d2"   # four half-filled circles that look like a turning wheel
spin_frame = 0           # which character is showing
spin_job = None          # the scheduled root.after() call, so it can be cancelled

# What each risky tool does, in plain words, for the approval popup.
WHAT_IT_DOES = {
    "read_file": "READS A FILE from your sandbox folder",
    "fetch_page": "CONTACTS THE INTERNET",
    "new_site": "WANTS TO READ A NEW WEBSITE (read only, this chat only)",
    "download_file": "SAVES A FILE onto your computer from the internet",
    "browser_open": "OPENS A WEB PAGE in the read-only browser",
    "browser_click": "CLICKS A LINK in the read-only browser",
    "browser_search": "SUBMITS A SEARCH on a website",
    "browser_web_search": "SEARCHES THE WEB for a public topic",
    "outbound_request": "SENDS THIS EXACT ADDRESS TO A WEBSITE",
    "desktop_start": "OPENS AN OWNED PRACTICE WINDOW (RAM-only draft; no real applications)",
    "notepad_start": "OPENS A NEW CLASSIC NOTEPAD SCRATCH WINDOW",
}


# ---- the worker thread (never touches the window directly) ---------------
def ask_approval(name, args):
    """Runs on the worker thread. Hands the question to the window and waits."""
    answer_box = queue.Queue()
    events.put(("ask", name, args, answer_box))
    return answer_box.get() is True   # blocks until the window answers; only True means yes


def worker(text, model, image=None, observation=None, progress_serial=None, resume=False):
    try:
        answer, seconds = run_turn(
            messages, text, ask_approval,
            log=lambda line: events.put(("log", line)),
            model=model, stop_event=stop_event, image=image, observation_text=observation,
            on_progress=lambda **event:task_progress.event(progress_serial,**event),resume=resume)
        events.put(("answer", answer, seconds))
    except Exception as e:            # top of the thread: show the error instead of dying silently
        task_progress.event(progress_serial,'finish',status='Failed')
        events.put(("error", str(e)))


# ---- the window (everything below runs on the main thread) ---------------
def high_risk_confirm(title, lines):
    """Modal red approval dialog. No starts focused; Enter, Escape and close deny."""
    answer = False
    win = tk.Toplevel(root)
    win._approval_dialog = True
    win.title(title)
    win.transient(root)
    win.configure(bg=T("window"))
    place_popup(win,720,480)
    tk.Label(win, text="APPROVAL REQUIRED", bg=T('window'), fg=T('red'),anchor='w',
             font=(UI_FONT, 10, "bold"), padx=18, pady=14).pack(fill="x")
    # Reserve button space FIRST so the scrolling text cannot hide the controls.
    row = tk.Frame(win, bg=T("window"))
    row.pack(side="bottom", fill="x", padx=12, pady=(0, 12))
    holder, box = scroll_box(win, wrap="word", bg=T("card"), fg=T("text"),
                             font=(FONT_NAME, 12), padx=14, pady=12, relief="flat")
    holder.pack(fill="both", expand=True, padx=12, pady=12)
    box.insert("end", "\n".join(lines))
    box.configure(state="disabled")

    def finish(allow=False):
        nonlocal answer
        answer = allow is True
        win.destroy()

    tk.Button(row, text="Yes, allow this action", command=lambda: finish(True),
              bg="#B91C1C", fg="white", padx=12, pady=8).pack(side="left")
    no = tk.Button(row, text="No", command=finish, default="active", padx=24, pady=8,
                   bg=T('button'),fg=T('text'),activebackground=T('pressed'),activeforeground=T('text'),relief='flat')
    no.pack(side="right")
    dismissible(win,finish,button=False)
    win.bind("<Return>", lambda event: finish())
    wait_modal(root,win,no)
    return answer


def confirm(name, args):
    if name=='edge_operation':
        lines=['ONE BROWSER ACTION','',
               'Browser: '+str(args.get('mode')),'',
               'Action: '+str(args.get('action')),'Page: '+str(args.get('title')),
               'Full URL:',str(args.get('url')),'']
        if args.get('action')=='copy':
            lines+=['Open this exact address in the isolated browser and allow its host for this chat.',
                    'Cookies, passwords and login state are not copied.']
        elif args.get('action') in {'read','shared_read'}:lines+=['The agent will receive page text and numbered controls.']
        elif args.get('action')=='open_shared':
            lines+=['Open this exact address in the separate Edge work profile. Personal cookies and login state are not copied.']
        elif args.get('action')=='open':lines+=['Open this exact address in the separate Edge work profile.']
        elif args.get('action')=='scroll':lines+=['Scroll one bounded viewport step: '+str(args.get('direction'))]
        else:
            lines+=['Control: '+str(args.get('control')),'Kind: '+str(args.get('kind'))]
            if 'destination' in args:lines+=['Exact destination:',args['destination']]
            if 'text' in args:lines+=['Current field value:',str(args.get('before','')),'Exact replacement text:',args['text']]
            lines+=['Website scripts may send text immediately. A button may submit a form or change account data.',
                    'Downloads and file chooser inputs are blocked in the work browser. Server-side effects are not independently verified.']
        lines+=['','Allow this exact operation? No cancels and pauses the workflow.']
        return high_risk_confirm('Approve shared Edge operation',lines)
    """Pop up the approval question. Returns True only if the person clicks Yes."""
    if name == "workspace_access":
        return high_risk_confirm("Allow document workspace", [
            "ALLOW LOCAL AI TO READ SAVED WORKSPACE DOCUMENTS FOR THIS CHAT", "",
            "Fixed folder:",args.get("folder",""),"",
            "Only numbered, bounded plain-text documents in this folder are supported.",
            "Every save needs a separate exact preview. Saved documents remain after New chat.",
            "New chat forgets access approval. No existing file is overwritten or deleted. Allow?"])
    if name == "document_save_exact":
        from workspace_panel import comparison
        return high_risk_confirm("Approve exact document save",[
            "SAVE A NEW PLAIN TEXT VERSION ON DISK", "", "Folder:",args.get("folder",""),
            "New file:",args.get("file",""),"", "Text comparison:",comparison(args.get('before',''),args.get('after','')),"", "Before (JSON text):",
            json.dumps(args.get("before"),ensure_ascii=False),"", "After (exact JSON text):",
            json.dumps(args.get("after"),ensure_ascii=False),"",
            "Earlier files remain as recovery copies. Code verifies the complete saved bytes.",
            "Saved documents persist after New chat. This approval covers only the displayed text. Allow?"])
    if name == "notepad_start":
        return high_risk_confirm("Open scratch Notepad", [WHAT_IT_DOES[name], "",
            "This is a separate classic Notepad process, starting with an empty document.",
            "Existing windows and modern Notepad tabs are not connected.",
            "Edits are limited to 2000 characters and each needs its own exact preview.",
            "The agent cannot open, save, print, click menus or switch documents.", "",
            "Stop, New chat or closing Local Studio discards this owned scratch window.",
            "Keep personal work in your usual Notepad windows. Open this scratch session?"])
    if name == "notepad_action":
        return high_risk_confirm("Approve exact Notepad edit", [
            "REPLACE TEXT IN THE OWNED NOTEPAD SCRATCH DOCUMENT", "",
            f"Window: {args.get('window')}", "Before (JSON text):",
            json.dumps(args.get("before"), ensure_ascii=False), "", "After (exact JSON text):",
            json.dumps(args.get("after"), ensure_ascii=False), "",
            "No file will be opened or saved by this action. Code rechecks the target and reads the result back.",
            "This edit always needs its own approval. Allow?"])
    if name == "desktop_action":
        return high_risk_confirm("Approve exact practice change", [
            "PRACTICE APP ONLY - THIS CHANGE NEEDS ITS OWN APPROVAL", "",
            f"Control: {args.get('control')}", f"Action: {args.get('action')}", "",
            "Before:", json.dumps(args.get("before"), ensure_ascii=False, indent=2), "",
            "After (exact proposed values):", json.dumps(args.get("after"), ensure_ascii=False, indent=2), "",
            "Code rechecks the target and verifies the result. Allow this one action?"])
    if name == "generation":
        return high_risk_confirm("Approve local generation", [
            "GENERATES A NEW LOCAL FILE USING GPU/RAM", "", f"Kind: {args.get('kind')}",
            "Exact prompt:", args.get("prompt", ""), "", f"Limits: {args.get('limits')}",
            f"Output: {args.get('output')}", "", "No cloud inference or automatic weight download. Allow?"])
    if name == "desktop_start":
        return high_risk_confirm("Open practice app", [WHAT_IT_DOES[name], "",
            "Desktop actions are restricted to that owned window. F12 stops owned workers.",
            "This is a practice boundary, not an OS security sandbox. Open it?"])
    if name == "plan":
        lines = ["WANTS TO FOLLOW THIS PLAN (open approved sites and click links only)", "",
                 f"Goal: {args.get('goal')}", ""]
        lines += [f"{i}. {s}" for i, s in enumerate(args.get("steps", []), 1)]
        lines += ["", "Each open step sends exactly the address shown. Plans can't hold ? or #.",
                  "Other addresses, searches and new websites still need separate approval.",
                  "Approve the whole plan?"]
        return high_risk_confirm("Approve plan",lines)
    if name == "plan_changed":
        lines = ["THE AGENT WANTS TO LEAVE ITS PLAN", "",
                 f"Planned step:  {args.get('planned')}", f"Wants instead: {args.get('new')}", "",
                 "Yes = allow just this one action.   No = stop the plan."]
        return high_risk_confirm("Plan changed",lines)
    if name == "new_site":                       # the site name here was read by code, not the model
        lines = [WHAT_IT_DOES["new_site"], "", f"Site:  {args.get('host')}", "",
                 f"Full address: {args.get('url')}", "",
                 "Yes also sends this exact address. It can hold private data in its path.",
                 "Check the site name carefully. Allow reading it for this chat?"]
        return high_risk_confirm("New website", lines)
    if name == "browser_search":
        lines = [WHAT_IT_DOES["browser_search"], "", f"Box: {args.get('box')}", "",
                 "Exact search text:", args.get("text", ""), "",
                 f"Full URL: {args.get('url')}", "", "Allow this search?"]
        return high_risk_confirm("Approve search", lines)
    if name == "browser_web_search":
        lines = [WHAT_IT_DOES[name], "", f"Search provider: {args.get('provider')}", "",
                 "Exact search text:", args.get("query", ""), "",
                 "Full URL:", args.get("url", ""), "",
                 "This sends the search text to the provider. Do not include private information.",
                 "Allow this one search?"]
        return high_risk_confirm("Approve web search", lines)
    if name == "outbound_request":
        lines = [WHAT_IT_DOES[name], "", f"Tool: {args.get('tool')}", "",
                 "Full URL (exact address):", args.get("url", ""), "",
                 "An address can contain private data in its path or query, even on an approved site.",
                 "Site approval and plans do not approve sending this data.", "",
                 "Allow this one request?"]
        return high_risk_confirm("Approve outbound address", lines)
    lines = [WHAT_IT_DOES.get(name, "RUNS A TOOL"), "", f"Tool: {name}"]
    if name in ("fetch_page", "download_file", "browser_open", "browser_click"):
        try:
            lines.append(f"Site: {urlparse(str(args.get('url', ''))).hostname}")
        except ValueError:
            lines.append("Site: (could not read it)")
    lines += [f"Details: {args}", "", "Allow this?"]
    return high_risk_confirm("Approval needed",lines)


def apply_font():
    chat_box.configure(font=(FONT_NAME, font_size))
    chat_box.tag_configure("name", font=(UI_FONT, 9, "bold"), spacing1=12, spacing3=6)
    entry.configure(font=(FONT_NAME, font_size))


def change_size(step):
    global font_size
    font_size = max(10, min(28, font_size + step))
    apply_font()


def flash_copied():
    copy_button.configure(text="Copied!")
    root.after(1200, lambda: copy_button.configure(text="Copy last answer"))


def copy_text(text):
    if not text:
        return
    root.clipboard_clear()
    root.clipboard_append(text)
    flash_copied()


def selected_text(widget):
    """The highlighted text in a widget, or "" if nothing is highlighted."""
    try:
        if widget is entry:
            return entry.get()[entry.index("sel.first"):entry.index("sel.last")]
        return widget.get("sel.first", "sel.last")
    except tk.TclError:          # Tk raises this when nothing is selected
        return ""


def paste_into_entry():
    try:
        clip = root.clipboard_get()
    except tk.TclError:          # clipboard empty, or not text
        return
    if entry.selection_present():
        entry.delete("sel.first", "sel.last")
    entry.insert("insert", clip)
    entry.focus_set()


def select_all(widget):
    if widget is entry:
        entry.selection_range(0, "end")
    else:
        widget.tag_add("sel", "1.0", "end-1c")


def add_context_menu(widget, can_paste):
    """Right-click menu: Copy, (Paste), Select all."""
    menu = tk.Menu(widget, tearoff=0)
    menu.add_command(label="Copy", command=lambda: copy_text(selected_text(widget)))
    if can_paste:
        menu.add_command(label="Paste", command=paste_into_entry)
    menu.add_command(label="Select all", command=lambda: select_all(widget))

    def popup(event):
        widget.focus_set()
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    widget.bind("<Button-3>", popup)


def clean(text):
    """Remove **bold** markers and backticks. A lone * is left alone."""
    return re.sub(r"\*\*(.+?)\*\*", r"\1", str(text or "")).replace("`", "")


def show(who, text):
    global welcome_visible
    if who == "You" and welcome_visible:
        chat_box.configure(state="normal")
        ranges = chat_box.tag_ranges("welcome_block")
        if ranges:
            chat_box.delete(ranges[0],ranges[-1])
        welcome_visible=False
    kind = {"You": "you", "Agent": "agent", "Error": "error", "Blocked": "blocked"}.get(who, "note")
    chat_box.configure(state="normal")
    chat_box.insert("end", f"{who.upper()}\n", ("name", kind))       # a Tk tag list: both tags apply
    chat_box.insert("end", f"{text}\n\n", (kind + "_body",))
    chat_box.configure(state="disabled")
    chat_box.see("end")


def add_pending():
    """Put 'Agent: thinking...' at the bottom. The tag lets us find it again later."""
    chat_box.configure(state="normal")
    chat_box.insert("end", f"Agent: thinking {SPINNER[spin_frame]}\n\n", "pending")
    chat_box.configure(state="disabled")
    chat_box.see("end")


def remove_pending():
    """Delete the 'thinking...' line, if it is there."""
    ranges = chat_box.tag_ranges("pending")
    if ranges:
        chat_box.configure(state="normal")
        chat_box.delete(ranges[0], ranges[1])
        chat_box.configure(state="disabled")


def spin():
    """Every 150 ms while busy, swap the spinner character. root.after runs this
    on the main thread, so it is allowed to touch the chat box."""
    global spin_frame, spin_job
    if not busy:                 # the answer arrived: stop rescheduling
        spin_job = None
        return
    spin_frame = (spin_frame + 1) % len(SPINNER)
    ranges = chat_box.tag_ranges("pending")
    if ranges:
        chat_box.configure(state="normal")
        chat_box.delete(ranges[0], ranges[1])
        chat_box.insert(ranges[0], f"Agent: thinking {SPINNER[spin_frame]}\n\n", "pending")
        chat_box.configure(state="disabled")
    spin_job = root.after(150, spin)


def start_spin():
    """Start the spinner, cancelling any old one first so two never run at once."""
    global spin_job
    if spin_job is not None:
        root.after_cancel(spin_job)
    spin_job = root.after(150, spin)


def stop_agent():
    """Kill owned automation workers and revoke pending images/approvals."""
    global pending_image, pending_media
    stop_event.set()
    from portal_server import stop_jobs
    stop_jobs()
    close_edge()
    reset_voice()
    task_progress.stop()
    pending_image = pending_media = None
    stop_all()  # Kill owned process trees; does not wait for a blocked UIA call.
    close_desktop()
    close_notepad()
    cancel_workspace()
    set_notepad_phase("closed")
    artifact_panel.stop()
    for window in root.winfo_children():
        if getattr(window, "_approval_dialog", False):
            window.event_generate("<Escape>")
    if not busy:
        show("Stop", "owned workers stopped. Any owned scratch Notepad was closed and its draft discarded.")
        return
    stop_button.configure(state="disabled", text="Stopping...")
    remove_pending()
    show("Stop", "owned workers stopped; any owned scratch Notepad was closed. A browser or Ollama call may still be finishing; no new action is allowed.")
    add_pending()


def watch_emergency():
    if emergency_ui.is_set():
        emergency_ui.clear()
        stop_agent()
    root.after(50, watch_emergency)


def finish_turn():
    global busy, recording_done
    busy = False
    recording_done = None
    if 'mic_button' in globals():
        mic_button.configure(text="Talk", state="normal")
    send_button.configure(state="normal")
    model_box.configure(state="readonly")
    stop_button.configure(state="disabled", text="Stop")
    entry.focus_set()


def attach_file():
    """Let the PERSON pick a file. Code checks it and copies it into the sandbox."""
    if busy:
        show("Attach", "wait for the answer first, then attach")
        return
    path = filedialog.askopenfilename(
        parent=root,
        title="Choose a file to attach",
        filetypes=[("Text and code", "*.txt *.md *.csv *.py"), ("All files", "*.*")])
    if not path:                      # Cancel or closed the window
        return
    try:
        name = attach.copy_in(path, SAFE)
    except ValueError as e:
        show("Attach", f"not attached: {e}")
        return
    show("Attach", f"copied into the sandbox as {name}. Your original was not touched.")
    if not entry.get().strip():       # never wipe something you were typing
        entry.insert(0, f"Read the file {name} and explain what it says")
        entry.focus_set()


def preview_image(image, on_approve=None, purpose="analysis"):
    """The person approves the exact normalized pixels, not a model-supplied path."""
    from io import BytesIO
    from PIL import Image, ImageTk
    answer = False
    win = tk.Toplevel(root)
    win._approval_dialog = True
    win.title("Preview reference photo for local video" if purpose == "video" else "Preview image for local analysis")
    win.transient(root)
    width,height=place_popup(win,760,640)
    win.configure(bg=T('window'))
    row = tk.Frame(win,bg=T('window'))
    row.pack(side="bottom", fill="x", padx=12, pady=12)  # Keep No visible at display scaling.
    explanation = ("These exact edited pixels will condition one local video after a separate prompt approval.\n"
                   "This is generation only; the photo cannot request tools or computer actions.\n"
                   "Check for private information before proceeding." if purpose == "video" else
                   "This image will be sent only to the local model when you press Send.\n"
                       "Check for passwords, private chats and other sensitive information.\n"
                       "Analysis only: this image cannot trigger computer actions.")
    tk.Label(win, text=explanation,bg=T('window'),fg=T('text'),
             wraplength=width - 40, padx=12, pady=12).pack()
    original = image
    display_width, display_height = max(100, width - 40), max(100, height - 240)
    mode = tk.StringVar(value="hide")
    tools = tk.Frame(win,bg=T('window'))
    tools.pack()
    for title,value in [('Drag to hide area','hide'),('Drag to crop','crop')]:
        tk.Radiobutton(tools,text=title,variable=mode,value=value,bg=T('window'),fg=T('text'),
                       selectcolor=T('field'),activebackground=T('window'),activeforeground=T('text')).pack(side='left')
    with Image.open(BytesIO(image.png)) as source:
        source.thumbnail((display_width, display_height))
        photo = ImageTk.PhotoImage(source)
    canvas = tk.Canvas(win, width=photo.width(), height=photo.height(), highlightthickness=0)
    canvas.pack(padx=12, pady=8)
    canvas.create_image(0, 0, image=photo, anchor="nw")
    origin = None

    def render():
        nonlocal photo
        with Image.open(BytesIO(image.png)) as source:
            source.thumbnail((display_width, display_height))
            photo = ImageTk.PhotoImage(source)
        canvas.configure(width=photo.width(), height=photo.height())
        canvas.delete("all")
        canvas.create_image(0, 0, image=photo, anchor="nw")
        details.configure(text=f"Prepared image: {image.width} x {image.height}; {len(image.png):,} bytes")

    def begin(event):
        nonlocal origin
        origin = (event.x, event.y)

    def end(event):
        nonlocal image, origin
        if origin is None:
            return
        from image_privacy import edit_image
        x1, x2 = sorted((origin[0], event.x))
        y1, y2 = sorted((origin[1], event.y))
        rectangle = (max(0, int(x1 * image.width / photo.width())),
                     max(0, int(y1 * image.height / photo.height())),
                     min(image.width, int(x2 * image.width / photo.width())),
                     min(image.height, int(y2 * image.height / photo.height())))
        origin = None
        try:
            image = edit_image(image, rectangle, crop=mode.get() == "crop")
            render()
        except ValueError:
            pass  # An empty/outside drag changes nothing.

    def reset():
        nonlocal image
        image = original
        render()

    tk.Button(tools, text="Reset", command=reset).pack(side="left")
    canvas.bind("<ButtonPress-1>", begin)
    canvas.bind("<ButtonRelease-1>", end)
    details = tk.Label(win, text=f"Prepared image: {image.width} x {image.height}; {len(image.png):,} bytes")
    details.pack()

    def finish(allow=False):
        nonlocal answer
        answer = allow is True
        if answer and on_approve is not None:
            on_approve(image)  # Exact edited pixels, never the original behind them.
        win.destroy()

    tk.Button(row, text="Use this image", command=lambda: finish(True)).pack(side="left")
    no = tk.Button(row, text="No", command=finish, default="active",bg=T('button'),fg=T('text'),
                   activebackground=T('pressed'),activeforeground=T('text'),relief='flat',padx=24,pady=8)
    no.pack(side="right")
    win.bind("<Return>", lambda event: finish())
    dismissible(win,finish,button=False)
    wait_modal(root,win,no)
    return answer


def stage_image(image):
    global pending_image, pending_media
    prepared = []
    if (preview_image(image, on_approve=prepared.append) is not True or len(prepared) != 1
            or stop_event.is_set()):
        return
    pending_image = prepared[0]
    pending_media = None
    show("Image", "One preview-approved image is ready for the next message. It is not saved to disk.")
    if not entry.get().strip():
        entry.insert(0, "Describe what is visible in this image and mention anything uncertain.")


def attach_image():
    if busy:
        return
    stop_event.clear()
    path = filedialog.askopenfilename(parent=root,title="Choose an image or saved screenshot",
                                     filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")])
    if not path or stop_event.is_set():
        return
    try:
        stage_image(load_image(path))
    except Exception:
        show("Error", "Could not prepare that image within the image limits.")


def animate_photo():
    """A person selects reference pixels; no model path or expanded image-analysis tools."""
    if busy:
        return
    stop_event.clear()
    path = filedialog.askopenfilename(parent=root,title="Choose a reference photo for a short local video",
        filetypes=[("Reference photo", "*.png *.jpg *.jpeg *.webp")])
    if not path or stop_event.is_set():
        return
    try:
        image = load_image(path)
        prepared = []
        if preview_image(image, on_approve=prepared.append, purpose="video") is not True or len(prepared) != 1 or stop_event.is_set():
            return
        from tkinter import simpledialog
        prompt = simpledialog.askstring("Describe the motion", "Describe the desired motion (up to 500 characters):",
            parent=root, initialvalue="The subject moves gently while the camera stays steady.")
        if prompt is None or stop_event.is_set():
            return
        from generation_tools import prompt_problem, run_generation
        problem = prompt_problem(prompt)
        if problem:
            show("Error", problem)
            return
        if confirm("generation", {"kind":"video from the preview-approved photo", "prompt":prompt,
                "limits":"LTX 2B: 384x256, 65 frames, 30 steps; 128 prompt tokens; fit photo with padding; no audio",
                "output":"Artifacts preview plus a unique generated-folder backup"}) is not True or stop_event.is_set():
            return
        reference = prepared[0]
    except Exception:
        show("Error", "Could not prepare the reference photo within the image limits.")
        return

    def generate():
        try:
            response = run_generation("video", prompt, stop_event, reference=reference)
            if "error" in response:
                events.put(("error", "Reference video: " + str(response["error"])))
                return
            if stop_event.is_set():
                events.put(("error", "Stopped. A completed generated file may remain; no preview was added."))
                return
            from artifacts import record_generated
            artifact = record_generated(response["path"], "video")
            events.put(("media_job_ready", f"Reference video ready in Artifact {artifact.number}."))
        except Exception:
            events.put(("error", "Reference video failed or was stopped. Check local LTX weights, free RAM/VRAM and dependencies. A completed file may remain; no automatic retry."))
    start_background(generate, reset_stop=False)


def read_aloud(automatic=False):
    if busy:
        return
    from speech_tools import speak, text_problem
    text = last_raw_answer.strip()
    problem = text_problem(text)
    if problem:
        show("Speech", "Read aloud needs a reply of at most 2000 characters. " + problem)
        return
    if automatic and (not speak_replies or stop_event.is_set()):
        return
    if not automatic:
        stop_event.clear()
    if not automatic and high_risk_confirm("Read this exact reply aloud", [
            "PLAYS SPEECH THROUGH THIS LAPTOP'S SPEAKERS", "", text, "",
            "Local English voice, CPU only, at most 120 seconds. No file is saved. Allow?"]) is not True or stop_event.is_set():
        return
    start_background(lambda: events.put(("media_job_ready", speak(text, stop_event))), reset_stop=False)


def reset_voice():
    global speak_replies, recording_done
    speak_replies = False
    if 'voice_auto' in globals():
        voice_auto.set(False)
    if recording_done is not None:
        recording_done.set()
    recording_done = None


def toggle_spoken_replies():
    global speak_replies
    requested = voice_auto.get() is True
    if requested and high_risk_confirm("Enable spoken replies for this chat", [
            "READS FUTURE TEXT REPLIES THROUGH THIS LAPTOP'S SPEAKERS", "",
            "Replies still appear in text. The fixed English voice runs locally on CPU.",
            "Up to 2000 characters / 120 seconds per reply; longer replies remain text only.",
            "Other people nearby can hear them. Stop or New chat disables this setting.",
            "No background listening; recording always requires pressing Talk. Allow?"]) is not True:
        requested = False
    if stop_event.is_set():
        requested = False
    speak_replies = requested
    voice_auto.set(requested)


def voice_message():
    global recording_done
    if recording_done is not None:
        recording_done.set()
        mic_button.configure(text="Transcribing...", state="disabled")
        return
    if busy:
        return
    if entry.get().strip():
        show("Speech", "Your unsent message is preserved. Send or clear it before recording.")
        return
    stop_event.clear()
    # Pressing Talk is the person's recording gesture; no second consent dialog.
    import multiprocessing
    done = multiprocessing.get_context("spawn").Event()
    recording_done = done
    mic_button.configure(text="Finish recording", state="normal")
    def record():
        try:
            from speech_tools import capture_and_transcribe
            events.put(("dictation_ready", capture_and_transcribe(done, stop_event,
                on_recorded=lambda:events.put(("voice_transcribing", None)))))
        except Exception:
            events.put(("error", "Voice message stopped or unavailable. Check microphone permission, device and local audio weights."))
    start_background(record, reset_stop=False)


def transcribe_recording():
    if busy:
        return
    if entry.get().strip():
        show("Speech", "Your unsent message is preserved. Send or clear it before dictation.")
        return
    stop_event.clear()
    path = filedialog.askopenfilename(parent=root,title="Transcribe a local English WAV recording (no microphone capture)",
        filetypes=[("Up to 60 seconds of PCM WAV", "*.wav")])
    if not path or stop_event.is_set():
        return
    def transcribe():
        try:
            from speech_tools import transcribe_wav
            events.put(("dictation_ready", transcribe_wav(path, stop_event)))
        except Exception:
            events.put(("error", "Could not transcribe that English PCM WAV within the local audio limits."))
    start_background(transcribe, reset_stop=False)


def stage_dictation(text):
    if stop_event.is_set():
        return
    if not isinstance(text, str) or not 1 <= len(text) <= 6000 or any(not c.isprintable() and c not in "\n\t" for c in text):
        show("Speech", "Invalid transcript refused.")
        return
    if entry.get().strip():
        show("Speech", "A transcript is ready, but your unsent message is preserved. Transcribe again after sending or clearing it.")
        return
    entry.insert(0, text)
    entry.focus_set()
    show("Speech", "Transcript placed in the message box for your review. Nothing was sent.")


def screenshot():
    """One capture only; never a background watcher or model-callable tool."""
    if busy:
        return
    stop_event.clear()
    if messagebox.askyesno("Capture practice window?",
            "Capture only the owned practice window once?\n"
            "You will preview it before choosing whether to attach it.", parent=root,default="no") is not True or stop_event.is_set():
        return
    root.withdraw()

    def capture():
        try:
            image = capture_practice()
        except Exception:
            root.deiconify()
            show("Error", "Open the practice environment first; no other window can be captured.")
            return
        root.deiconify()
        stage_image(image)

    root.after(350, capture)  # Allow Windows to hide this window before capturing.


def clear_image():
    global pending_image, pending_media
    if not busy:
        pending_image = None
        pending_media = None
        show("Image", "Pending image cleared.")


def free_vram():
    if busy:
        show("Memory", "Wait for the current request to finish before unloading its model.")
        return
    threading.Thread(target=lambda: events.put(("memory", release_models())), daemon=True).start()


def start_background(target, reset_stop=True):
    global busy
    if busy:
        return
    busy = True
    if reset_stop:
        stop_event.clear()
    send_button.configure(state="disabled")
    # A running turn keeps its captured model. Selection applies to the next turn.
    model_box.configure(state="readonly")
    stop_button.configure(state="normal", text="Stop")
    add_pending()
    start_spin()
    threading.Thread(target=target, daemon=True).start()


def open_practice():
    if busy:
        return
    stop_event.clear()
    if confirm("desktop_start", {}) is not True or stop_event.is_set():
        return
    start_background(lambda: events.put(("practice_ready", start_practice(stop_event))))


def open_notepad():
    if busy:
        return
    stop_event.clear()
    if confirm("notepad_start", {}) is not True or stop_event.is_set():
        return
    start_background(lambda: events.put(("notepad_ready", start_notepad(stop_event))), reset_stop=False)


def attach_clip():
    if busy:
        return
    stop_event.clear()
    path = filedialog.askopenfilename(parent=root,title="Choose up to 60 seconds of local media",
                                     filetypes=[("Local clips", "*.wav *.mp4")])
    if not path or stop_event.is_set():
        return

    def prepare():
        try:
            events.put(("prepared_media", prepare_media(path, stop_event)))
        except Exception:
            events.put(("error", "Could not prepare clip. Check limits and optional audio weights."))

    start_background(prepare)


def stage_media(media):
    global pending_media, pending_image
    pending_media = pending_image = None
    if media.image is not None:
        stage_image(media.image)
        if pending_image is None:
            return
    elif high_risk_confirm("Preview local transcript", [
            "LOCAL AUDIO TRANSCRIPT - REVIEW BEFORE SENDING", "", media.observation,
            "", "This is untrusted media content. Allow observation-only analysis?"]) is not True:
        return
    if stop_event.is_set():
        pending_image = None
        return
    pending_media = media
    show("Media", f"Ready: {media.seconds:.2f}s, {media.samples} frame samples. Observation only.")
    if not entry.get().strip():
        entry.insert(0, "Summarize this selected media and state what you could not establish.")


def model_check():
    if busy:
        return
    stop_event.clear()
    if messagebox.askyesno("Run local model check?",
            "Run fixed synthetic tasks against both installed local models?\n"
            "This can take a few minutes and will unload the models afterwards.", parent=root,default="no") is not True or stop_event.is_set():
        return

    def evaluate():
        try:
            from evaluate_models import evaluate
            events.put(("practice_ready", evaluate(stop_event)))
        except Exception:
            events.put(("error", "Local model evaluation failed."))

    start_background(evaluate)


def new_chat():
    """Forget the conversation. The model has no memory of its own: every turn,
    run_turn re-sends the whole messages list. Empty the list and it forgets."""
    global last_answer, last_raw_answer, pending_image, pending_media
    if busy:
        show("New chat", "wait for the answer first")
        return
    if messagebox.askyesno("New chat", "Start a new chat?\n\nThe agent will forget this conversation.\n"
                          "Unsaved Artifact drafts, version history and scratch Notepad will be discarded. Saved chats, exported files and saved Documents remain. Workspace read permission is forgotten; last-save recovery remains available.",
                          parent=root,default="no") is not True:
        return
    if not clear_chat_state():return False
    show("New chat", "started. Saved chats remain in Chats & Projects; this conversation has fresh permissions.")
    free_vram()
    entry.focus_set()
    return True


def clear_chat_state():
    """Person-controlled session replacement; never restore approval/tool state."""
    global last_answer,last_raw_answer,pending_image,pending_media,saved_chat,current_project,restored_chat
    close_edge()
    closed = close_browser()    # close the browser BEFORE wiping anything: no half-reset chats
    if closed.startswith("Error"):
        show("New chat", f"not started: {closed}")
        return False
    close_desktop()
    close_notepad()
    set_notepad_phase("closed")
    stop_all()
    messages.clear()            # empty the SAME list (don't make a new one)
    conversation_entries.clear()
    saved_chat=None
    current_project=None
    restored_chat=False
    task_progress.reset()
    artifact_store.clear()
    artifact_panel.reset()
    hide_artifacts()            # back to just the chat
    stop_event.clear()          # No turn is active; this is a person-approved fresh chat.
    forget_sites()              # websites allowed in the old chat are forgotten too
    last_answer = ""
    last_raw_answer = ""
    reset_voice()
    pending_image = None
    pending_media = None
    activity_lines.clear()
    utility=getattr(root,'_utility_popup',None)
    if utility is not None and utility.winfo_exists():utility._dismiss_popup()
    from document_qa_panel import reset_sources
    reset_sources(root)
    chat_box.configure(state="normal")
    chat_box.delete("1.0", "end")
    chat_box.configure(state="disabled")
    entry.delete(0,'end')
    return True


def open_saved_chat(snapshot):
    """Restore validated pixels/text only, then wait for a new user request."""
    global saved_chat,current_project,restored_chat,last_answer,last_raw_answer,welcome_visible
    from chat_library import restored_context
    from artifacts import Store
    # Validate everything before closing or clearing the active conversation.
    verified=Store().replace_saved(snapshot['items'])
    context=restored_context(snapshot['messages'],snapshot['notes'])
    if not clear_chat_state():return False
    artifact_store.replace_saved(verified)
    conversation_entries.extend(dict(message) for message in snapshot['messages'])
    messages.extend(context)
    for message in conversation_entries:
        show('You' if message['role']=='user' else 'Agent',message['content'])
    welcome_visible=False
    saved_chat={key:snapshot[key] for key in ('id','version','title','project')}
    current_project=snapshot['project']
    restored_chat=True
    last_raw_answer=next((message['content'] for message in reversed(conversation_entries) if message['role']=='assistant'),'')
    last_answer=clean(last_raw_answer)
    artifact_panel.refresh()
    show('Chats','Reopened locally. Prior actions are historical; permissions and controls are fresh. '
         'Only a shortened reference archive is supplied to the model. Send a new request to continue.')
    return True


def start_project_chat(project):
    global current_project,restored_chat
    if new_chat() is not True:return False
    from chat_library import restored_context
    current_project=project['id']
    messages.extend(restored_context([],project['notes']))
    restored_chat=True
    show('Project',project['title']+' · Reference notes ready; no old approvals or actions restored.')
    return True


def show_chats():
    from chat_library_panel import show_library
    import sys
    return show_library(sys.modules[__name__])


def show_sources():
    from document_qa_panel import show_sources as open_sources
    import sys
    return open_sources(sys.modules[__name__])


def show_website():
    from portal_ui import show_portal
    import sys
    return show_portal(sys.modules[__name__])


LOG_LINES = 50   # how many of the newest log lines the viewer shows


def share_personal_edge_tab():
    global edge_code_window
    if busy:return
    if not high_risk_confirm('Connect an Edge tab',[
            'SHARE A TAB FROM YOUR EXISTING EDGE BROWSER','',
            'Install the local extension from edge_extension once using Edge > Extensions > Developer mode > Load unpacked.',
            'Select your website tab, click the Local Studio extension icon, then enter the fresh code shown next.',
            'Only that selected tab is shared, for reading or copying its address. Clicks/typing stay in the separate work profile.',
            'Each read or handoff needs its own approval. The isolated browser remains a separate mode.',
            'Stop, New chat and Disconnect revoke the connection. No begins selected.','',
            'Start a fresh local pairing session?']):return
    try:code=start_edge()
    except Exception:
        show('Edge','Error: could not start the local connector.');return
    old=globals().get('edge_code_window')
    if old is not None and old.winfo_exists():old.destroy()
    win=tk.Toplevel(root);win.title('Pair the selected Edge tab');win.transient(root)
    edge_code_window=win
    dismissible(win,label='Close code window',size=(650,260))
    ttk.Label(win,text='Enter this fresh code in the Local Studio Edge extension.\nKeep the Edge connector window open.',padding=(18,16)).pack()
    field=tk.Entry(win,width=64,bg=T('field'),fg=T('text'),insertbackground=T('text'),relief='flat');field.insert(0,code);field.pack(fill='x',padx=18,pady=8)
    ttk.Label(win,text='Keep this code private. It stays in RAM and is never sent to the model.',wraplength=560).pack(padx=18,pady=8)
    show('Edge','Pairing ready. Select your personal Edge tab and Share selected tab in the extension.\nAsk me to read the shared tab, copy it to the isolated browser, or open its address in the work profile.')


def connect_edge_tab():
    global edge_panel
    if busy:return
    if 'edge_panel' in globals() and edge_panel.winfo_exists():
        edge_panel.lift();return
    win=tk.Toplevel(root);win.title('Edge work browser');win.transient(root)
    edge_panel=win
    dismissible(win,size=(600,440))
    ttk.Label(win,text='Edge work browser',style='Title.TLabel',padding=(18,16)).pack(anchor='w')
    ttk.Label(win,text='A separate space for approved website actions.',style='Muted.TLabel',padding=(18,0)).pack(anchor='w',pady=(0,12))
    def launch():
        if high_risk_confirm('Start Edge work profile',[
            'OPEN THE AI WORK BROWSER','',
            'Your personal Edge tabs and logins stay separate.',
            'This work profile saves its own cookies and site logins on this laptop.',
            'Websites can run scripts. Approved clicks or typing can affect website data.',
            'Downloads and file selection are blocked. Each AI action needs your approval.',
            'Stop closes this work browser. Your personal Edge stays open.','',
            'Work profile folder:',str(EDGE_WORK_PROFILE),'',
            'Start it?']):
            show('Edge',start_work());win.destroy()
    def choose():
        win.destroy()
        def load():
            try:data=work_current().rpc('list')
            except Exception:data={'error':'Start the work browser first and wait for its window.'}
            events.put(('edge_work_tabs',data))
        threading.Thread(target=load,daemon=True).start()
    for text,callback in [('Start work Edge',launch),('Choose a work tab',choose),
                          ('Share a personal Edge tab (read/handoff)',lambda:(win.destroy(),share_personal_edge_tab())),
                          ('Disconnect / close work Edge',lambda:(close_edge(),win.destroy()))]:
        ttk.Button(win,text=text,command=callback).pack(fill='x',padx=18,pady=5)


def choose_edge_work_tab(data):
    global edge_tab_picker
    if data.get('error'):
        show('Edge',data['error']);return
    win=tk.Toplevel(root);win.title('Select Edge work tab');win.transient(root)
    old=globals().get('edge_tab_picker')
    if old is not None and old.winfo_exists():old.destroy()
    edge_tab_picker=win
    dismissible(win,label='Cancel',size=(700,520))
    ttk.Label(win,text='Choose a work tab',style='Title.TLabel',padding=(18,16)).pack(anchor='w')
    ttk.Label(win,text='Only tabs from the separate work profile appear here.',style='Muted.TLabel').pack(anchor='w',padx=18,pady=(0,12))
    body=scrolling_frame(win)
    if not data.get('tabs'):ttk.Label(body,text='No work tabs available. Close this window and start work Edge.').pack(padx=16,pady=16)
    def select(number):
        def apply():
            try:work_current().rpc('select',{'number':number});status='Work tab selected. Ask me to read Edge.'
            except Exception:status='Error: tab changed; choose it again.'
            events.put(('memory',status))
        threading.Thread(target=apply,daemon=True).start();win.destroy()
    for tab in data.get('tabs',[]):
        tk.Button(body,text=(tab['title']+'\n'+tab['url']),wraplength=560,justify='left',bg=T('button'),fg=T('text'),
                  activebackground=T('pressed'),activeforeground=T('text'),relief='flat',padx=10,pady=10,
                  command=lambda number=tab['number']:select(number)).pack(fill='x',padx=16,pady=5)
    body.bind('<Configure>',lambda event:[child.configure(wraplength=max(100,event.width-60))
              for child in body.winfo_children() if isinstance(child,tk.Button)],add='+')


def format_entry(line):
    """Turn one JSON log line into short readable text, plus its event name for coloring.
    A broken line is reported, never allowed to crash the viewer."""
    try:
        e = json.loads(line)
        when = str(e.get("time", "?")).replace("T", " ")
        event = str(e.get("event", "?"))
        text = f"{when}   {event.upper():<20} {e.get('tool', '?')}   {e.get('args', '')}"
        if "note" in e:
            text += f"\n        -> {e['note']}"
        return text, event
    except (ValueError, AttributeError):
        return "(a line in the log could not be read)", "bad"


def show_log():
    """Open a READ-ONLY window with the newest audit-log entries. The text is shown,
    never run: log lines contain whatever the model asked for, so they are untrusted."""
    global audit_window,activity_box
    old=globals().get('audit_window')
    if old is not None and old.winfo_exists():old.lift();return
    win = audit_window = tk.Toplevel(root)
    win.title("Activity")
    win.transient(root)
    dismissible(win,size=(850,540))
    win.configure(bg=T("window"))
    ttk.Label(win,text='Activity',style='Title.TLabel',padding=(18,16)).pack(anchor='w')
    tabs=ttk.Notebook(win);tabs.pack(fill='both',expand=True,padx=18,pady=(0,12))
    current=ttk.Frame(tabs);saved=ttk.Frame(tabs)
    tabs.add(current,text='This chat');tabs.add(saved,text='Saved audit')
    holder,activity_box=scroll_box(current,wrap='word',bg=T('card'),fg=T('text'),font=(FONT_NAME,11),relief='flat',padx=14,pady=12)
    holder.pack(fill='both',expand=True)
    activity_box.insert('end','\n\n'.join(activity_lines) or 'No tool activity yet.')
    activity_box.configure(state='disabled')
    holder, box = scroll_box(saved, wrap="word", width=90, height=24, bg=T("card"), fg=T("text"),
                             font=(FONT_NAME, max(10, font_size - 2)), spacing3=6,
                             relief="flat", bd=0, padx=14, pady=10, highlightthickness=1,
                             highlightbackground=T("border"), highlightcolor=T("border"))
    holder.configure(bg=T("window"))
    holder.pack(fill="both", expand=True, padx=12, pady=12)
    for kind in ("denied", "site_denied"):
        box.tag_configure(kind, foreground=T("red"))
    for kind in ("unknown_tool", "site_refused", "stopped"):
        box.tag_configure(kind, foreground=T("orange"))
    for kind in ("approved", "site_allowed"):
        box.tag_configure(kind, foreground=T("green"))
    try:
        with open(AUDIT_LOG, encoding="utf-8", errors="replace") as f:
            lines = list(deque(f, maxlen=LOG_LINES))   # keeps only the last LOG_LINES lines
    except FileNotFoundError:
        lines = []
    except OSError:
        lines = None
    if lines is None:
        box.insert("end", "Could not open the audit log.")
    elif not lines:
        box.insert("end", "The log is empty: no tools have been used yet.")
    for line in lines or []:
        text, kind = format_entry(line)
        box.insert("end", text + "\n", kind)
    box.configure(state="disabled")
    box.see("end")


def record_activity(line):
    activity_lines.append(str(line)[:2000])
    if activity_box is not None and activity_box.winfo_exists():
        activity_box.configure(state='normal');activity_box.delete('1.0','end')
        activity_box.insert('end','\n\n'.join(activity_lines));activity_box.configure(state='disabled');activity_box.see('end')


def resume_task():
    if busy or pending_image is not None or pending_media is not None:return
    if save_uncertain():
        show('Task','The last save is unconfirmed. Open Documents and choose Check last save before resuming.')
        return
    if entry.get().strip():
        show('Task','Your unsent message is preserved. Send or clear it before resuming the checkpoint.')
        return
    try:text=task_progress.resume_request()
    except ValueError:return
    entry.delete(0,'end');entry.insert(0,text)
    send(resume=True)


def send(event=None,resume=False):
    global busy, pending_image, pending_media
    text = entry.get().strip()
    if not text or busy:
        return
    entry.delete(0, "end")
    show("You", text)
    conversation_entries.append({'role':'user','content':text})
    require_fresh_read=resume or restored_chat
    add_pending()
    start_spin()
    model = model_var.get()                      # read it here, on the main thread
    image, pending_image = pending_image, None
    observation = pending_media.observation if pending_media is not None else None
    pending_media = None
    busy = True
    progress_serial=task_progress.begin('' if image is not None or observation is not None else text,resume=resume)
    send_button.configure(state="disabled")
    model_box.configure(state="readonly")  # Changes affect the next message only.
    stop_event.clear()                           # a fresh turn starts un-stopped
    stop_button.configure(state="normal", text="Stop")
    threading.Thread(target=worker, args=(text, model, image, observation,progress_serial,require_fresh_read), daemon=True).start()


def poll():
    """Every 100 ms, look for news from the worker thread."""
    global last_answer, last_raw_answer
    try:
        while True:
            item = events.get_nowait()
            kind = item[0]
            if kind == "log":
                line = item[1]
                record_activity(line)
                if line.startswith("[notepad] "):
                    set_notepad_phase(line[len("[notepad] "):])
                if line.startswith("[blocked] "):      # code refused something: say so in the chat
                    remove_pending()
                    show("Blocked", line[len("[blocked] "):])
                    if busy:add_pending()
            elif kind == "ask":
                _, name, args, answer_box = item
                answer_box.put(False if stop_event.is_set() else confirm(name, args))
            elif kind == "answer":
                remove_pending()
                last_raw_answer = str(item[1] or "")
                conversation_entries.append({'role':'assistant','content':last_raw_answer})
                last_answer = clean(item[1])
                show("Agent", f"{last_answer}\n[{item[2]:.2f}s]")
                finish_turn()
                if speak_replies and not stop_event.is_set():
                    read_aloud(automatic=True)
            elif kind == "error":
                conversation_entries.append({'role':'assistant','content':'Error: '+str(item[1])})
                remove_pending()
                show("Error", item[1])
                finish_turn()
            elif kind == "memory":
                show("Memory", item[1])
            elif kind == 'edge_work_tabs':
                choose_edge_work_tab(item[1])
            elif kind == "emergency_stop":
                stop_agent()
            elif kind == "prepared_media":
                remove_pending()
                finish_turn()
                if not stop_event.is_set():
                    stage_media(item[1])
            elif kind == "practice_ready":
                remove_pending()
                show("Practice", item[1])
                finish_turn()
            elif kind == "notepad_ready":
                remove_pending()
                set_notepad_phase("paused" if item[1].startswith("Error:") else "ready")
                show("Notepad",item[1])
                finish_turn()
            elif kind == "media_job_ready":
                remove_pending()
                finish_turn()
                show("Media", "Stopped." if stop_event.is_set() else item[1])
            elif kind == "dictation_ready":
                remove_pending()
                finish_turn()
                stage_dictation(item[1])
            elif kind == "voice_transcribing":
                mic_button.configure(text="Transcribing...", state="disabled")
                show("Speech", "Microphone recording ended. Transcribing locally...")
    except queue.Empty:
        pass
    sync_attachment_chip()
    root.after(100, poll)


def scroll_box(parent, **opts):
    """A Text box plus a ttk scrollbar. Tk's plain scrollbar ignores colors on Windows,
    the ttk one in the "clam" look does not. Returns (frame to pack, the text box)."""
    holder = tk.Frame(parent)
    box = tk.Text(holder, **opts)
    bar = ttk.Scrollbar(holder, orient="vertical", command=box.yview)
    box.configure(yscrollcommand=bar.set)      # the box and the bar keep each other in sync
    bar.pack(side="right", fill="y")
    box.pack(side="left", fill="both", expand=True)
    return holder, box


def make_button(parent, text, command, kind="plain", **extra):
    """A flat, padded button. kind picks its colors: plain, accent (blue) or danger (red text)."""
    b = tk.Button(parent, text=text, command=command, relief="flat", bd=0, highlightthickness=0, padx=14, pady=6,
                  cursor="hand2", font=(UI_FONT, 10), **extra)
    buttons.append((b, kind))
    return b


def apply_theme():
    """Apply the shared palette to both workspaces and existing safety dialogs."""
    palette = THEMES[theme_name]
    root.configure(bg=T("window"))
    configure_styles(style, palette)
    for widget, key in theme_surfaces:
        widget.configure(bg=T(key))
    for widget, foreground, background in theme_labels:
        widget.configure(fg=T(foreground), bg=T(background))
    chat_box.configure(bg=T("card"), fg=T("text"), insertbackground=T("text"),
                       selectbackground=T("select"), selectforeground=T("text"),
                       highlightbackground=T("card"), highlightcolor=T("card"))
    for role, color in (("you", "accent"), ("agent", "text"), ("note", "subtle"),
                        ("error", "red"), ("blocked", "orange"), ("pending", "subtle")):
        chat_box.tag_configure(role, foreground=T(color))
        chat_box.tag_configure(role + "_body", foreground=T(color if role in ("note","error","blocked") else "text"))
    chat_box.tag_configure("you_body", background=T("bubble"), lmargin1=12, lmargin2=12,
                           rmargin=12, spacing1=4, spacing3=8)
    chat_box.tag_configure("welcome_title", foreground=T("text"), font=(UI_FONT,23,"bold"),spacing3=14)
    chat_box.tag_configure("welcome_body",foreground=T("subtle"),font=(UI_FONT,12),spacing3=14)
    entry.configure(bg=T("field"),fg=T("text"),insertbackground=T("accent"),
                    selectbackground=T("select"),selectforeground=T("text"),
                    highlightbackground=T("border"),highlightcolor=T("accent"))
    for button, kind in buttons:
        accent = kind == "accent"
        button.configure(bg=T("accent" if accent else "button"),
                         fg=T("on_accent" if accent else "red" if kind=="danger" else "text"),
                         activebackground=T("accent" if accent else "pressed"),
                         activeforeground=T("on_accent" if accent else "text"),disabledforeground=T("subtle"))
    root.option_add("*TCombobox*Listbox.background",T("field"))
    root.option_add("*TCombobox*Listbox.foreground",T("text"))
    for menu in (more_menu, attach_menu):
        menu.configure(bg=T("card"), fg=T("text"), activebackground=T("select"),
                       activeforeground=T("text"), disabledforeground=T("subtle"), bd=0)
    more_menu.entryconfigure(theme_entry, label="Light appearance" if theme_name=="dark" else "Dark appearance")
    artifact_panel.apply_theme(palette)
    if 'progress_panel' in globals():progress_panel.render(task_progress.snapshot())


def toggle_theme():
    global theme_name
    theme_name = "dark" if theme_name == "light" else "light"
    apply_theme()



def popup_menu(menu, button):
    """Open a menu right under the button that was clicked."""
    menu.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height())


def artifacts_visible():
    return str(artifact_panel) in workspace.panes()


def show_artifacts():
    if not artifacts_visible():
        workspace.add(artifact_panel, weight=3)
        root.after(50, lambda: workspace.sashpos(0, int(workspace.winfo_width() * 0.50)))
    artifacts_button.configure(text="Hide artifacts")


def hide_artifacts():
    if artifacts_visible():
        workspace.forget(artifact_panel)
    artifacts_button.configure(text="Artifacts")


def toggle_artifacts():
    hide_artifacts() if artifacts_visible() else show_artifacts()


def sync_attachment_chip():
    """Show the remove-attachment chip only while an image or clip waits for the next message."""
    waiting = pending_image is not None or pending_media is not None
    clear_chip.configure(text="Clip attached  ✕" if pending_media is not None else "Image attached  ✕")
    if waiting and not clear_chip.winfo_ismapped():
        clear_chip.pack(side="left", padx=(0, 8), ipady=4, after=attach_button)
    elif not waiting and clear_chip.winfo_ismapped():
        clear_chip.pack_forget()


def make_sharp():
    """Tell Windows this app draws for the real screen resolution. Without it, Windows draws
    the window at 100% and stretches the picture to your scaling, which looks blurry."""
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)   # sharp on the main display
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()      # older Windows fallback
    except Exception:
        pass                                               # not Windows, or already set


def build_window():
    global notepad_status
    global root, style, bottom, chat_holder, chat_box, copy_button, attach_button, model_var, model_box, send_button, stop_button, entry, artifact_panel, theme_surfaces, theme_labels, welcome_visible
    global more_menu, attach_menu, theme_entry, workspace, artifacts_button, clear_chip
    global voice_auto, mic_button
    make_sharp()                 # must happen before the first window exists
    set_app_identity()
    root = tk.Tk()
    set_window_icon(root)
    root.title("Local Studio")
    scale = max(1.0, root.winfo_fpixels("1i") / 96)   # 1.5 on a 150% display
    root.minsize(int(1100 * scale), int(680 * scale))
    root.geometry(f"{int(1440 * scale)}x{int(900 * scale)}")
    style = ttk.Style(root)
    style.theme_use("clam")
    theme_surfaces, theme_labels = [], []

    def surface(parent, color="window", **options):
        frame = tk.Frame(parent, bd=0, **options)
        theme_surfaces.append((frame,color))
        return frame

    def label(parent, text, size=10, color="subtle", background="window", bold=False, **options):
        widget = tk.Label(parent,text=text,font=(UI_FONT,size,"bold" if bold else "normal"),anchor="w",**options)
        theme_labels.append((widget,color,background))
        return widget

    sidebar = surface(root,"sidebar",width=int(170*scale))
    sidebar.pack(side="left",fill="y")
    sidebar.pack_propagate(False)
    label(sidebar,"ON THIS DEVICE",9,"subtle","sidebar").pack(anchor="w",padx=22,pady=(30,2))
    label(sidebar,"Studio",24,"text","sidebar",True).pack(anchor="w",padx=20,pady=(0,24))
    make_button(sidebar,"+  New chat",new_chat,kind="accent").pack(fill="x",padx=16,pady=(0,24))
    make_button(sidebar,"Chats & Projects",show_chats).pack(fill='x',padx=16,pady=4)
    make_button(sidebar,'Sources Q&A',show_sources).pack(fill='x',padx=16,pady=4)
    from workspace_panel import show_documents
    make_button(sidebar,"Documents",lambda:(show_artifacts(),show_documents(artifact_panel,confirm))).pack(fill="x",padx=16,pady=4)
    artifacts_button=make_button(sidebar,"Artifacts",toggle_artifacts)
    artifacts_button.pack(fill="x",padx=16,pady=4)
    make_button(sidebar,'Edge tab',connect_edge_tab).pack(fill='x',padx=16,pady=4)
    notepad_status=tk.StringVar(value=NOTEPAD_PHASES["closed"])
    notepad_label=label(sidebar,"",9,background="sidebar",textvariable=notepad_status,wraplength=140)
    def notepad_label_sync(*_):     # only show Notepad's state while it is actually open
        if notepad_status.get()==NOTEPAD_PHASES["closed"]:notepad_label.pack_forget()
        else:notepad_label.pack(fill="x",padx=20,pady=(8,8))
    notepad_status.trace_add("write",notepad_label_sync)
    # One menu for everything you don't need every day.
    more_menu=tk.Menu(root,tearoff=0)
    more_menu.add_command(label="Practice",command=open_practice)
    more_menu.add_command(label="Notepad",command=open_notepad)
    more_menu.add_command(label="Activity",command=show_log)
    more_menu.add_command(label='Local website',command=show_website)
    more_menu.add_command(label='Disconnect Edge tab',command=close_edge)
    more_menu.add_separator()
    more_menu.add_command(label="Model check",command=model_check)
    more_menu.add_command(label="Free VRAM",command=free_vram)
    more_menu.add_command(label="Read reply aloud",command=read_aloud)
    more_menu.add_command(label="Transcribe WAV into message",command=transcribe_recording)
    voice_auto = tk.BooleanVar(value=False)
    more_menu.add_checkbutton(label="Speak replies for this chat",variable=voice_auto,command=toggle_spoken_replies)
    more_menu.add_separator()
    more_menu.add_command(label="Bigger text",command=lambda:change_size(2))
    more_menu.add_command(label="Smaller text",command=lambda:change_size(-2))
    more_menu.add_command(label="Light appearance",command=toggle_theme)
    theme_entry=more_menu.index("end")
    more_button=make_button(sidebar,"More  ...",lambda:popup_menu(more_menu,more_button))
    more_button.pack(side="bottom",fill="x",padx=16,pady=(8,22))

    main = surface(root)
    main.pack(side="left",fill="both",expand=True,padx=22,pady=20)
    header = surface(main)
    header.pack(fill="x",pady=(0,18))
    header_right=surface(header)
    header_right.pack(side="right")
    model_row=surface(header_right)
    model_row.pack(anchor="e")
    label(model_row,"Next message model",10).pack(side="left",padx=(0,8))
    model_var=tk.StringVar(value="auto")
    model_box=ttk.Combobox(model_row,textvariable=model_var,values=MODEL_CHOICES,state="readonly",width=18,font=(UI_FONT,10))
    model_box.pack(side="left",padx=(0,6))

    bottom=surface(main)
    bottom.pack(side="bottom",fill="x",pady=(12,0))
    compose=surface(bottom)
    compose.pack(fill="x")
    send_button=make_button(compose,"Send  →",send,kind="accent")
    send_button.pack(side="right",padx=(8,0),ipady=4)
    stop_button=make_button(compose,"Stop",stop_agent,kind="danger",state="disabled")
    stop_button.pack(side="right",padx=(8,0),ipady=4)
    attach_menu=tk.Menu(root,tearoff=0)
    attach_menu.add_command(label="File",command=attach_file)
    attach_menu.add_command(label="Image",command=attach_image)
    attach_menu.add_command(label="Photo to video",command=animate_photo)
    attach_menu.add_command(label="Clip",command=attach_clip)
    attach_menu.add_command(label="Screenshot of practice window",command=screenshot)
    attach_button=make_button(compose,"+  Attach",lambda:popup_menu(attach_menu,attach_button))
    attach_button.pack(side="left",padx=(0,8),ipady=4)
    mic_button=make_button(compose,"Talk",voice_message)
    mic_button.pack(side="left",padx=(0,8),ipady=4)
    clear_chip=make_button(compose,"Image attached  ✕",clear_image)
    entry=tk.Entry(compose,width=60,relief="flat",bd=0,highlightthickness=1)
    entry.pack(side="left",fill="x",expand=True,ipady=13)
    entry.bind("<Return>",send)
    label(bottom,"Enter to send  ·  F12 stops",9).pack(anchor="w",pady=(8,0))

    workspace=ttk.Panedwindow(main,orient="horizontal")
    workspace.pack(fill="both",expand=True)
    conversation=surface(workspace,"card")
    conversation_header=surface(conversation,"card")
    conversation_header.pack(fill="x",padx=20,pady=(16,5))
    label(conversation_header,"Conversation",12,"text","card",True).pack(side="left")
    copy_button=make_button(conversation_header,"Copy last answer",lambda:copy_text(last_raw_answer))
    copy_button.pack(side="right")
    global progress_panel
    progress_panel=ProgressPanel(conversation,task_progress,resume_task)
    chat_holder,chat_box=scroll_box(conversation,state="disabled",wrap="word",width=42,height=20,
        spacing1=0,spacing2=3,spacing3=8,relief="flat",bd=0,padx=22,pady=18,highlightthickness=0)
    chat_holder.pack(fill="both",expand=True)
    def progress_sync(idle):
        if idle:progress_panel.pack_forget()
        elif not progress_panel.winfo_ismapped():progress_panel.pack(fill='x',padx=20,pady=(0,6),before=chat_holder)
    progress_panel.on_idle=progress_sync
    workspace.add(conversation,weight=3)
    artifact_panel=ArtifactPanel(workspace,stop_event,answer=lambda:last_raw_answer,confirm=confirm)
    artifact_panel.model_busy=lambda:busy
    artifact_panel.document_busy=lambda active:stop_button.configure(
        state='normal' if active or busy else 'disabled',text='Stop')
    artifact_panel.on_change=show_artifacts
    from emergency_hotkey import start_hotkey
    start_hotkey(lambda:(stop_event.set(),close_edge(),stop_all(),emergency_ui.set()),lambda text:events.put(("memory",text)))
    root.after(50,watch_emergency)
    root.bind_all("<F12>",lambda event:stop_agent())
    root.bind("<Escape>",lambda event:stop_agent())
    apply_font()
    apply_theme()
    chat_box.configure(state="normal")
    chat_box.insert("end","\nWhat are we working on?\n",("welcome_title","welcome_block"))
    chat_box.insert("end","Ask a question, bring an idea, or create\nsomething in the Artifacts workspace.\n\nTry: ‘Create a study guide about cells.’\n\n",("welcome_body","welcome_block"))
    chat_box.configure(state="disabled")
    welcome_visible=True
    add_context_menu(chat_box,can_paste=False)
    add_context_menu(entry,can_paste=True)
    chat_box.bind("<Button-1>",lambda event:chat_box.focus_set())


if __name__ == "__main__":
    build_window()
    from chat_archive_service import start_maintenance
    import sys
    start_maintenance(sys.modules[__name__])
    entry.focus_set()
    poll()
    root.mainloop()
