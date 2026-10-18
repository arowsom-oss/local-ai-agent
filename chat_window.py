import json
import queue
from collections import deque
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from urllib.parse import urlparse

import attach
from model_router import release_models
from vision_input import load_image
from desktop_tools import desktop_start, close_desktop, capture_practice, start_practice
from process_guard import stop_all
from media_input import prepare_media
from browser_tool import close_browser
from agent_core import run_turn, MODEL_CHOICES, SAFE, AUDIT_LOG, forget_sites
from artifacts import store as artifact_store
from artifact_panel import ArtifactPanel
from ui_theme import PALETTES, configure_styles
from notepad_tools import start_notepad, close_notepad
from workspace_documents import reset_workspace, cancel_workspace

# ---- shared state -------------------------------------------------------
messages = []            # the conversation; lives as long as the window is open
stop_event = threading.Event()   # set by the Stop button, checked by the worker between steps
emergency_ui = threading.Event()  # Separate watcher also runs inside modal Tk wait loops.
events = queue.Queue()   # worker thread -> window: things to show or ask about
busy = False             # True while the model is working on a question
last_answer = ""         # the newest agent reply, for the "Copy last answer" button
last_raw_answer = ""     # Preserve code fences when the person copies an answer to Artifacts.
pending_image = None     # immutable preview-approved bytes, for one turn only
pending_media = None

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


def worker(text, model, image=None, observation=None):
    try:
        answer, seconds = run_turn(
            messages, text, ask_approval,
            log=lambda line: events.put(("log", line)),
            model=model, stop_event=stop_event, image=image, observation_text=observation)
        events.put(("answer", answer, seconds))
    except Exception as e:            # top of the thread: show the error instead of dying silently
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
    width, height = min(720, win.winfo_screenwidth() - 80), min(480, win.winfo_screenheight() - 120)
    x, y = max(0, (win.winfo_screenwidth() - width) // 2), max(0, (win.winfo_screenheight() - height) // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")
    win.minsize(540, 360)
    tk.Label(win, text="HIGH RISK - EXPLICIT APPROVAL REQUIRED", bg="#B91C1C", fg="white",
             font=(UI_FONT, 12, "bold"), padx=16, pady=14).pack(fill="x")
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
    no = tk.Button(row, text="No", command=finish, default="active", padx=24, pady=8)
    no.pack(side="right")
    win.protocol("WM_DELETE_WINDOW", finish)
    win.bind("<Escape>", lambda event: finish())
    win.bind("<Return>", lambda event: finish())
    win.wait_visibility()
    win.grab_set()
    no.focus_set()
    root.wait_window(win)
    return answer


def confirm(name, args):
    """Pop up the approval question. Returns True only if the person clicks Yes."""
    if name == "workspace_access":
        return high_risk_confirm("Allow document workspace", [
            "ALLOW LOCAL AI TO READ SAVED WORKSPACE DOCUMENTS FOR THIS CHAT", "",
            "Fixed folder:",args.get("folder",""),"",
            "Only numbered, bounded plain-text documents in this folder are supported.",
            "Every save needs a separate exact preview. Saved documents remain after New chat.",
            "New chat forgets access approval. No existing file is overwritten or deleted. Allow?"])
    if name == "document_save_exact":
        return high_risk_confirm("Approve exact document save",[
            "SAVE A NEW PLAIN TEXT VERSION ON DISK", "", "Folder:",args.get("folder",""),
            "New file:",args.get("file",""),"", "Before (JSON text):",
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
        lines += ["", "Model-written addresses, searches and new websites still need separate approval.",
                  "Approve the whole plan?"]
        return messagebox.askyesno("Approve plan", "\n".join(lines), default="no", icon="warning") is True
    if name == "plan_changed":
        lines = ["THE AGENT WANTS TO LEAVE ITS PLAN", "",
                 f"Planned step:  {args.get('planned')}", f"Wants instead: {args.get('new')}", "",
                 "Yes = allow just this one action.   No = stop the plan."]
        return messagebox.askyesno("Plan changed", "\n".join(lines), default="no", icon="warning") is True
    if name == "new_site":                       # the site name here was read by code, not the model
        lines = [WHAT_IT_DOES["new_site"], "", f"Site:  {args.get('host')}", "",
                 f"Full address: {args.get('url')}", "",
                 "Check the site name carefully. Allow reading it for this chat?"]
        return high_risk_confirm("New website", lines)
    if name == "browser_search":
        lines = [WHAT_IT_DOES["browser_search"], "", f"Box: {args.get('box')}", "",
                 "Exact search text:", args.get("text", ""), "",
                 f"Full URL: {args.get('url')}", "", "Allow this search?"]
        return high_risk_confirm("Approve search", lines)
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
    return messagebox.askyesno("Approval needed", "\n".join(lines),
                               default="no", icon="warning") is True


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
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text).replace("`", "")


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
    global busy
    busy = False
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


def preview_image(image, on_approve=None):
    """The person approves the exact normalized pixels, not a model-supplied path."""
    from io import BytesIO
    from PIL import Image, ImageTk
    answer = False
    win = tk.Toplevel(root)
    win._approval_dialog = True
    win.title("Preview image for local analysis")
    win.transient(root)
    width = min(760, win.winfo_screenwidth() - 80)
    height = min(640, win.winfo_screenheight() - 100)
    win.geometry(f"{width}x{height}")
    row = tk.Frame(win)
    row.pack(side="bottom", fill="x", padx=12, pady=12)  # Keep No visible at display scaling.
    tk.Label(win, text="This image will be sent only to the local model when you press Send.\n"
                       "Check for passwords, private chats and other sensitive information.\n"
                       "Analysis only: this image cannot trigger computer actions.",
             wraplength=width - 40, padx=12, pady=12).pack()
    original = image
    display_width, display_height = max(100, width - 40), max(100, height - 240)
    mode = tk.StringVar(value="hide")
    tools = tk.Frame(win)
    tools.pack()
    tk.Radiobutton(tools, text="Drag to hide area", variable=mode, value="hide").pack(side="left")
    tk.Radiobutton(tools, text="Drag to crop", variable=mode, value="crop").pack(side="left")
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
    no = tk.Button(row, text="No", command=finish, default="active")
    no.pack(side="right")
    win.bind("<Return>", lambda event: finish())
    win.bind("<Escape>", lambda event: finish())
    win.protocol("WM_DELETE_WINDOW", finish)
    win.wait_visibility()
    win.grab_set()
    no.focus_set()
    root.wait_window(win)
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
    path = filedialog.askopenfilename(title="Choose an image or saved screenshot",
                                     filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")])
    if not path or stop_event.is_set():
        return
    try:
        stage_image(load_image(path))
    except Exception:
        show("Error", "Could not prepare that image within the image limits.")


def screenshot():
    """One capture only; never a background watcher or model-callable tool."""
    if busy:
        return
    stop_event.clear()
    if messagebox.askyesno("Capture practice window?",
            "Capture only the owned practice window once?\n"
            "You will preview it before choosing whether to attach it.", default="no") is not True or stop_event.is_set():
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
    model_box.configure(state="disabled")
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
    path = filedialog.askopenfilename(title="Choose up to 60 seconds of local media",
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
            "This can take a few minutes and will unload the models afterwards.", default="no") is not True or stop_event.is_set():
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
                          "Artifact drafts, version history and scratch Notepad will be discarded. Exported files and saved Documents remain. Workspace read permission is forgotten.",
                          default="no") is not True:
        return
    closed = close_browser()    # close the browser BEFORE wiping anything: no half-reset chats
    if closed.startswith("Error"):
        show("New chat", f"not started: {closed}")
        return
    close_desktop()
    close_notepad()
    set_notepad_phase("closed")
    stop_all()
    messages.clear()            # empty the SAME list (don't make a new one)
    artifact_store.clear()
    artifact_panel.reset()
    stop_event.clear()          # No turn is active; this is a person-approved fresh chat.
    forget_sites()              # websites allowed in the old chat are forgotten too
    last_answer = ""
    last_raw_answer = ""
    pending_image = None
    pending_media = None
    chat_box.configure(state="normal")
    chat_box.delete("1.0", "end")
    chat_box.configure(state="disabled")
    show("New chat", "started. The agent has forgotten everything before this.")
    free_vram()
    entry.focus_set()


LOG_LINES = 50   # how many of the newest log lines the viewer shows


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
    win = tk.Toplevel(root)
    win.title("Audit log (newest at the bottom)")
    win.configure(bg=T("window"))
    holder, box = scroll_box(win, wrap="word", width=90, height=24, bg=T("card"), fg=T("text"),
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


def send(event=None):
    global busy, pending_image, pending_media
    text = entry.get().strip()
    if not text or busy:
        return
    entry.delete(0, "end")
    show("You", text)
    add_pending()
    start_spin()
    model = model_var.get()                      # read it here, on the main thread
    image, pending_image = pending_image, None
    observation = pending_media.observation if pending_media is not None else None
    pending_media = None
    busy = True
    send_button.configure(state="disabled")
    model_box.configure(state="disabled")
    stop_event.clear()                           # a fresh turn starts un-stopped
    stop_button.configure(state="normal", text="Stop")
    threading.Thread(target=worker, args=(text, model, image, observation), daemon=True).start()


def poll():
    """Every 100 ms, look for news from the worker thread."""
    global last_answer, last_raw_answer
    try:
        while True:
            item = events.get_nowait()
            kind = item[0]
            if kind == "log":
                remove_pending()
                line = item[1]
                if line.startswith("[notepad] "):
                    set_notepad_phase(line[len("[notepad] "):])
                if line.startswith("[blocked] "):      # code refused something: say so in the chat
                    show("Blocked", line[len("[blocked] "):])
                else:
                    show("tool", line)
                add_pending()          # still working, so thinking... goes back underneath
            elif kind == "ask":
                _, name, args, answer_box = item
                answer_box.put(False if stop_event.is_set() else confirm(name, args))
            elif kind == "answer":
                remove_pending()
                last_raw_answer = str(item[1] or "")
                last_answer = clean(item[1])
                show("Agent", f"{last_answer}\n[{item[2]:.2f}s]")
                finish_turn()
            elif kind == "error":
                remove_pending()
                show("Error", item[1])
                finish_turn()
            elif kind == "memory":
                show("Memory", item[1])
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
    except queue.Empty:
        pass
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
    theme_button.configure(text="Light appearance" if theme_name=="dark" else "Dark appearance")
    artifact_panel.apply_theme(palette)


def toggle_theme():
    global theme_name
    theme_name = "dark" if theme_name == "light" else "light"
    apply_theme()



def build_window():
    global notepad_status
    global root, style, bottom, toolbar, vision_toolbar, chat_holder, chat_box, copy_button, attach_button, model_var, model_box, theme_button, send_button, stop_button, entry, artifact_panel, theme_surfaces, theme_labels, welcome_visible
    root = tk.Tk()
    root.title("Local Studio")
    root.minsize(1100, 680)
    root.geometry("1440x900")
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

    sidebar = surface(root,"sidebar",width=170)
    sidebar.pack(side="left",fill="y")
    sidebar.pack_propagate(False)
    label(sidebar,"LOCAL",10,"accent","sidebar",True).pack(anchor="w",padx=22,pady=(30,2))
    label(sidebar,"Studio",24,"text","sidebar",True).pack(anchor="w",padx=20,pady=(0,24))
    make_button(sidebar,"+  New chat",new_chat,kind="accent").pack(fill="x",padx=16,pady=(0,30))
    label(sidebar,"WORKSPACE",9,background="sidebar",bold=True).pack(anchor="w",padx=22,pady=(0,12))
    make_button(sidebar,"Practice",open_practice).pack(fill="x",padx=16,pady=4)
    make_button(sidebar,"Notepad",open_notepad).pack(fill="x",padx=16,pady=4)
    from workspace_panel import show_documents
    make_button(sidebar,"Documents",lambda:show_documents(artifact_panel,confirm)).pack(fill="x",padx=16,pady=4)
    notepad_status=tk.StringVar(value=NOTEPAD_PHASES["closed"])
    label(sidebar,"",9,background="sidebar",textvariable=notepad_status,wraplength=140).pack(fill="x",padx=20,pady=(2,8))
    make_button(sidebar,"Audit log",show_log).pack(fill="x",padx=16,pady=4)
    theme_button = make_button(sidebar,"Light appearance",toggle_theme)
    theme_button.pack(side="bottom",fill="x",padx=16,pady=(8,22))
    make_button(sidebar,"Free VRAM",free_vram).pack(side="bottom",fill="x",padx=16,pady=4)
    make_button(sidebar,"Model check",model_check).pack(side="bottom",fill="x",padx=16,pady=4)
    label(sidebar,"LOCAL UTILITIES",9,background="sidebar",bold=True).pack(side="bottom",anchor="w",padx=22,pady=(0,10))

    main = surface(root)
    main.pack(side="left",fill="both",expand=True,padx=22,pady=20)
    header = surface(main)
    header.pack(fill="x",pady=(0,18))
    header_left=surface(header)
    header_left.pack(side="left")
    label(header_left,"Your workspace",23,"text",bold=True).pack(anchor="w")
    label(header_left,"Think it through. Make something useful.",11).pack(anchor="w",pady=(5,0))
    header_right=surface(header)
    header_right.pack(side="right")
    label(header_right,"●  On this device",10,"green").pack(anchor="e",pady=(0,6))
    model_row=surface(header_right)
    model_row.pack(anchor="e")
    model_var=tk.StringVar(value="auto")
    model_box=ttk.Combobox(model_row,textvariable=model_var,values=MODEL_CHOICES,state="readonly",width=18,font=(UI_FONT,10))
    model_box.pack(side="left",padx=(0,6))

    bottom=surface(main)
    bottom.pack(side="bottom",fill="x",pady=(12,0))
    label(bottom,"MESSAGE",9,bold=True).pack(anchor="w",pady=(0,7))
    compose=surface(bottom)
    compose.pack(fill="x")
    send_button=make_button(compose,"Send  →",send,kind="accent")
    send_button.pack(side="right",padx=(8,0),ipady=4)
    stop_button=make_button(compose,"Stop",stop_agent,kind="danger",state="disabled")
    stop_button.pack(side="right",padx=(8,0),ipady=4)
    entry=tk.Entry(compose,width=60,relief="flat",bd=0,highlightthickness=1)
    entry.pack(side="left",fill="x",expand=True,ipady=13)
    entry.bind("<Return>",send)
    label(bottom,"Enter to send  ·  F12 or Ctrl+Alt+F9 to stop",9).pack(anchor="w",pady=(8,0))

    vision_toolbar=surface(main)
    vision_toolbar.pack(side="bottom",fill="x",pady=(10,0))
    attach_button=make_button(vision_toolbar,"Attach file",attach_file)
    attach_button.pack(side="left")
    for text,callback in (("Attach image",attach_image),("Attach clip",attach_clip),("Screenshot",screenshot),("Clear image",clear_image)):
        make_button(vision_toolbar,text,callback).pack(side="left",padx=(6,0))
    toolbar=surface(model_row)
    toolbar.pack(side="left")
    make_button(toolbar,"A-",lambda:change_size(-2)).pack(side="left",padx=3)
    make_button(toolbar,"A+",lambda:change_size(2)).pack(side="left")

    workspace=ttk.Panedwindow(main,orient="horizontal")
    workspace.pack(fill="both",expand=True)
    conversation=surface(workspace,"card")
    conversation_header=surface(conversation,"card")
    conversation_header.pack(fill="x",padx=20,pady=(16,5))
    label(conversation_header,"Conversation",12,"text","card",True).pack(side="left")
    copy_button=make_button(conversation_header,"Copy last answer",lambda:copy_text(last_answer))
    copy_button.pack(side="right")
    label(conversation,"A little space to explore your next idea.",10,background="card").pack(anchor="w",padx=22,pady=(0,12))
    chat_holder,chat_box=scroll_box(conversation,state="disabled",wrap="word",width=42,height=20,
        spacing1=0,spacing2=3,spacing3=8,relief="flat",bd=0,padx=22,pady=18,highlightthickness=0)
    chat_holder.pack(fill="both",expand=True)
    workspace.add(conversation,weight=3)
    artifact_panel=ArtifactPanel(workspace,stop_event,answer=lambda:last_raw_answer,confirm=confirm)
    workspace.add(artifact_panel,weight=3)
    root.after(100,lambda:workspace.sashpos(0,int(workspace.winfo_width()*0.50)))
    from emergency_hotkey import start_hotkey
    start_hotkey(lambda:(stop_event.set(),stop_all(),emergency_ui.set()),lambda text:events.put(("memory",text)))
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
    entry.focus_set()
    poll()
    root.mainloop()
