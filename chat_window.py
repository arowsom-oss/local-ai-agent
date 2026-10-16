import json
import queue
from collections import deque
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from urllib.parse import urlparse

from ollama import generate

import attach
from agent_core import run_turn, ALLOWED_MODELS, MODEL, SAFE, AUDIT_LOG, forget_sites

# ---- shared state -------------------------------------------------------
messages = []            # the conversation; lives as long as the window is open
stop_event = threading.Event()   # set by the Stop button, checked by the worker between steps
events = queue.Queue()   # worker thread -> window: things to show or ask about
busy = False             # True while the model is working on a question
last_answer = ""         # the newest agent reply, for the "Copy last answer" button
last_model = None        # the model used for the previous message

# Reading settings. Change these and re-run if they don't feel right for you.
FONT_NAME = "Verdana"    # wide letters, ships with Windows
font_size = 14
UI_FONT = "Segoe UI"     # buttons and labels; the chat itself stays in FONT_NAME

# Apple-style colors. Every widget reads its colors from here, so switching modes
# is just "pick the other dictionary, then repaint everything".
THEMES = {
    "light": dict(window="#F5F5F7", card="#FFFFFF", text="#1D1D1F", subtle="#6E6E73",
                  border="#D2D2D7", button="#E8E8ED", pressed="#D2D2D7",
                  accent="#007AFF", on_accent="#FFFFFF", select="#B3D7FF",
                  red="#D70015", green="#248A3D", orange="#C93400"),
    "dark": dict(window="#1C1C1E", card="#2C2C2E", text="#F5F5F7", subtle="#98989D",
                 border="#3A3A3C", button="#3A3A3C", pressed="#48484A",
                 accent="#0A84FF", on_accent="#FFFFFF", select="#3F638B",
                 red="#FF6961", green="#30DB5B", orange="#FFB340"),
}
theme_name = "light"
buttons = []             # every button made by make_button, so apply_theme can repaint them


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
}


# ---- the worker thread (never touches the window directly) ---------------
def ask_approval(name, args):
    """Runs on the worker thread. Hands the question to the window and waits."""
    answer_box = queue.Queue()
    events.put(("ask", name, args, answer_box))
    return answer_box.get() is True   # blocks until the window answers; only True means yes


def unload(model):
    """Ask Ollama to free the VRAM a model is using. Best effort: a failure is shown, not hidden."""
    try:
        generate(model=model, keep_alive=0)
    except Exception as e:
        events.put(("log", f"could not unload {model}: {e}"))


def worker(text, model, old_model):
    try:
        if old_model and old_model != model:
            unload(old_model)
        answer, seconds = run_turn(
            messages, text, ask_approval,
            log=lambda line: events.put(("log", line)),
            model=model, stop_event=stop_event)
        events.put(("answer", answer, seconds))
    except Exception as e:            # top of the thread: show the error instead of dying silently
        events.put(("error", str(e)))


# ---- the window (everything below runs on the main thread) ---------------
def confirm(name, args):
    """Pop up the approval question. Returns True only if the person clicks Yes."""
    if name == "new_site":                       # the site name here was read by code, not the model
        lines = [WHAT_IT_DOES["new_site"], "", f"Site:  {args.get('host')}", "",
                 f"Full address: {args.get('url')}", "",
                 "Check the site name carefully. Allow reading it for this chat?"]
        return messagebox.askyesno("New website", "\n".join(lines),
                                   default="no", icon="warning") is True
    lines = [WHAT_IT_DOES.get(name, "RUNS A TOOL"), "", f"Tool: {name}"]
    if name in ("fetch_page", "download_file"):
        try:
            lines.append(f"Site: {urlparse(str(args.get('url', ''))).hostname}")
        except ValueError:
            lines.append("Site: (could not read it)")
    lines += [f"Details: {args}", "", "Allow this?"]
    return messagebox.askyesno("Approval needed", "\n".join(lines),
                               default="no", icon="warning") is True


def apply_font():
    chat_box.configure(font=(FONT_NAME, font_size))
    chat_box.tag_configure("name", font=(FONT_NAME, font_size, "bold"))
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
    kind = {"You": "you", "Agent": "agent", "Error": "error", "Blocked": "blocked"}.get(who, "note")
    chat_box.configure(state="normal")
    chat_box.insert("end", f"{who}: ", ("name", kind))       # a Tk tag list: both tags apply
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
    """Stop button (or Esc): the step already running finishes, then nothing new runs."""
    if not busy or stop_event.is_set():
        return
    stop_event.set()
    stop_button.configure(state="disabled", text="Stopping...")
    remove_pending()
    show("Stop", "stopping after the current step. Nothing new will run.")
    add_pending()


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


def new_chat():
    """Forget the conversation. The model has no memory of its own: every turn,
    run_turn re-sends the whole messages list. Empty the list and it forgets."""
    global last_answer
    if busy:
        show("New chat", "wait for the answer first")
        return
    if not messagebox.askyesno("New chat", "Start a new chat?\n\nThe agent will forget this conversation.",
                               default="no"):
        return
    messages.clear()            # empty the SAME list (don't make a new one)
    forget_sites()              # websites allowed in the old chat are forgotten too
    last_answer = ""
    chat_box.configure(state="normal")
    chat_box.delete("1.0", "end")
    chat_box.configure(state="disabled")
    show("New chat", "started. The agent has forgotten everything before this.")
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
    global busy, last_model
    text = entry.get().strip()
    if not text or busy:
        return
    entry.delete(0, "end")
    show("You", text)
    add_pending()
    start_spin()
    model = model_var.get()                      # read it here, on the main thread
    old_model, last_model = last_model, model
    busy = True
    send_button.configure(state="disabled")
    model_box.configure(state="disabled")
    stop_event.clear()                           # a fresh turn starts un-stopped
    stop_button.configure(state="normal", text="Stop")
    threading.Thread(target=worker, args=(text, model, old_model), daemon=True).start()


def poll():
    """Every 100 ms, look for news from the worker thread."""
    global last_answer
    try:
        while True:
            item = events.get_nowait()
            kind = item[0]
            if kind == "log":
                remove_pending()
                line = item[1]
                if line.startswith("[blocked] "):      # code refused something: say so in the chat
                    show("Blocked", line[len("[blocked] "):])
                else:
                    show("tool", line)
                add_pending()          # still working, so thinking... goes back underneath
            elif kind == "ask":
                _, name, args, answer_box = item
                answer_box.put(confirm(name, args))
            elif kind == "answer":
                remove_pending()
                last_answer = clean(item[1])
                show("Agent", f"{last_answer}\n[{item[2]:.2f}s]")
                finish_turn()
            elif kind == "error":
                remove_pending()
                show("Error", item[1])
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
    """Repaint every widget with the current mode's colors. Purely visual: no logic lives here."""
    root.configure(bg=T("window"))
    for frame in (toolbar, bottom, chat_holder):
        frame.configure(bg=T("window"))
    chat_box.configure(bg=T("card"), fg=T("text"), insertbackground=T("text"),
                       selectbackground=T("select"), selectforeground=T("text"),
                       highlightbackground=T("border"), highlightcolor=T("border"))
    chat_box.tag_configure("you", foreground=T("accent"))
    chat_box.tag_configure("agent", foreground=T("text"))
    chat_box.tag_configure("note", foreground=T("subtle"))
    chat_box.tag_configure("note_body", foreground=T("subtle"))
    chat_box.tag_configure("error", foreground=T("red"))
    chat_box.tag_configure("error_body", foreground=T("red"))
    chat_box.tag_configure("blocked", foreground=T("orange"))
    chat_box.tag_configure("blocked_body", foreground=T("orange"))
    chat_box.tag_configure("pending", foreground=T("subtle"))
    entry.configure(bg=T("card"), fg=T("text"), insertbackground=T("text"),
                    selectbackground=T("select"), selectforeground=T("text"),
                    highlightbackground=T("border"), highlightcolor=T("accent"))
    for b, kind in buttons:
        if kind == "accent":
            b.configure(bg=T("accent"), fg=T("on_accent"), activebackground=T("accent"),
                        activeforeground=T("on_accent"), disabledforeground=T("select"))
        else:
            b.configure(bg=T("button"), fg=T("red") if kind == "danger" else T("text"),
                        activebackground=T("pressed"), activeforeground=T("text"),
                        disabledforeground=T("subtle"))
    style.configure("TCombobox", fieldbackground=T("card"), background=T("button"),
                    foreground=T("text"), arrowcolor=T("text"), bordercolor=T("border"),
                    lightcolor=T("card"), darkcolor=T("card"))
    style.map("TCombobox", fieldbackground=[("readonly", T("card"))],
              foreground=[("readonly", T("text"))], selectbackground=[("readonly", T("card"))],
              selectforeground=[("readonly", T("text"))])
    style.configure("Vertical.TScrollbar", background=T("button"), troughcolor=T("card"),
                    bordercolor=T("card"), arrowcolor=T("subtle"),
                    lightcolor=T("button"), darkcolor=T("button"))
    style.map("Vertical.TScrollbar", background=[("active", T("pressed"))])
    root.option_add("*TCombobox*Listbox.background", T("card"))   # the drop-down list
    root.option_add("*TCombobox*Listbox.foreground", T("text"))
    theme_button.configure(text="Light mode" if theme_name == "dark" else "Dark mode")


def toggle_theme():
    global theme_name
    theme_name = "dark" if theme_name == "light" else "light"
    apply_theme()


root = tk.Tk()
root.title("Local agent")
root.minsize(860, 420)       # narrower than this and the toolbar gets cut off
style = ttk.Style(root)
style.theme_use("clam")      # the only built-in ttk look that accepts custom colors

# Pack order matters: the bottom rows go in FIRST, so when the window is short
# the chat area shrinks instead of the buttons getting pushed off the screen.
bottom = tk.Frame(root)
bottom.pack(side="bottom", fill="x", padx=12, pady=12)
toolbar = tk.Frame(root)
toolbar.pack(side="bottom", fill="x", padx=12)
chat_holder, chat_box = scroll_box(
    root, state="disabled", wrap="word", width=70, height=22,
    spacing2=6, spacing3=10,             # extra space between lines and between messages
    relief="flat", bd=0, padx=16, pady=12, highlightthickness=1)
chat_holder.pack(padx=12, pady=(12, 6), fill="both", expand=True)

copy_button = make_button(toolbar, "Copy last answer", lambda: copy_text(last_answer))
copy_button.pack(side="left")
attach_button = make_button(toolbar, "Attach file", attach_file)
attach_button.pack(side="left", padx=(6, 0))
make_button(toolbar, "New chat", new_chat).pack(side="left", padx=(6, 0))
make_button(toolbar, "Audit log", show_log).pack(side="left", padx=(6, 0))
model_var = tk.StringVar(value=MODEL)
model_box = ttk.Combobox(toolbar, textvariable=model_var, values=ALLOWED_MODELS,
                         state="readonly", width=14, font=(UI_FONT, 10))
model_box.pack(side="left", padx=8)
make_button(toolbar, "A+", lambda: change_size(2)).pack(side="right")
make_button(toolbar, "A-", lambda: change_size(-2)).pack(side="right", padx=(0, 6))
theme_button = make_button(toolbar, "Dark mode", toggle_theme)
theme_button.pack(side="right", padx=(0, 6))

# Same idea: buttons packed before the stretchy entry, so the entry can't squeeze them.
send_button = make_button(bottom, "Send", send, kind="accent")
send_button.pack(side="right", padx=(8, 0))
stop_button = make_button(bottom, "Stop", stop_agent, kind="danger", state="disabled")
stop_button.pack(side="right", padx=(8, 0))
entry = tk.Entry(bottom, width=60, relief="flat", bd=0, highlightthickness=1)
entry.pack(side="left", fill="x", expand=True, ipady=7)       # ipady = taller box, room to breathe
entry.bind("<Return>", send)
root.bind("<Escape>", lambda e: stop_agent())   # Esc works too, for fast reaction time

apply_font()
apply_theme()
add_context_menu(chat_box, can_paste=False)
add_context_menu(entry, can_paste=True)
chat_box.bind("<Button-1>", lambda e: chat_box.focus_set())   # so Ctrl+C reaches the chat box

if __name__ == "__main__":
    entry.focus_set()
    poll()
    root.mainloop()
