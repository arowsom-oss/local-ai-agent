"""Real Windows/Tk fixture with synthetic pixels: no screen capture or inference.

Run: python -B test_vision_ui.py (requires the application's dependencies/display).
"""
from io import BytesIO

from PIL import Image
import chat_window as ui
import vision_input


def buttons(parent):
    for child in parent.winfo_children():
        if isinstance(child, ui.tk.Button):
            yield child
        yield from buttons(child)


if __name__ == "__main__":
    ui.build_window()
    data = BytesIO()
    Image.new("RGB", (1200, 800), "navy").save(data, format="PNG")
    image = vision_input.prepare_image(data.getvalue())
    ui.root.geometry("1080x800")
    ui.root.update()
    ui.root.focus_force()  # Activate our own fixture, as when the person clicks its button.
    ui.root.update()
    errors = []
    ui.set_notepad_phase('observed')
    assert 'observed' in ui.notepad_status.get()
    ui.set_notepad_phase('unknown model-written state')
    assert 'observed' in ui.notepad_status.get()
    ui.stop_event.set();ui.set_notepad_phase('closed');ui.set_notepad_phase('verified')
    assert ui.notepad_status.get()==ui.NOTEPAD_PHASES['closed']
    ui.stop_event.clear()

    def callback_error(kind, value, trace):
        errors.append(value)
        for child in ui.root.winfo_children():
            if isinstance(child, ui.tk.Toplevel):
                child.destroy()

    ui.root.report_callback_exception = callback_error
    # Chat-first layout: two visible buttons, everything else in their menus.
    for text in ("+  Attach", "More  ..."):
        button = next(b for b in buttons(ui.root) if b.cget("text") == text)
        assert button.winfo_ismapped() and button.winfo_width() > 10
    labels = lambda menu: [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)
                           if menu.type(i) == "command"]
    assert labels(ui.attach_menu) == ["File", "Image", "Photo to video", "Clip", "Screenshot of practice window"]
    for text in ("Practice", "Notepad", "Audit log", "Model check", "Free VRAM"):
        assert text in labels(ui.more_menu)
    assert not ui.clear_chip.winfo_ismapped()          # nothing attached yet

    def act(action, yes_label="Use this image"):
        win = next(w for w in ui.root.winfo_children() if isinstance(w, ui.tk.Toplevel))
        no = next(b for b in buttons(win) if b.cget("text") == "No")
        assert ui.root.focus_get() == no
        assert no.winfo_ismapped() and no.winfo_rooty() + no.winfo_height() < win.winfo_screenheight()
        if action == "yes":
            next(b for b in buttons(win) if b.cget("text") == yes_label).invoke()
        else:
            win.event_generate(action)

    try:
        for action, expected in (("<Return>", False), ("<Escape>", False), ("yes", True)):
            ui.root.after(250, lambda value=action: act(value))
            assert ui.preview_image(image) is expected
            assert not errors, errors
        for name, args in (("notepad_start", {}), ("notepad_action", {
                "window": "Untitled - Notepad", "before": "First draft", "after": "Revised draft"})):
            for action, expected in (("<Return>", False), ("<Escape>", False), ("yes", True)):
                ui.root.after(250, lambda value=action: act(value, "Yes, allow this action"))
                assert ui.confirm(name, args) is expected
                assert not errors, errors
        # Redaction/crop changes the payload delivered by approval, not merely
        # an overlay painted on top of the original image.
        accepted = []

        def edit_and_accept():
            win = next(w for w in ui.root.winfo_children() if isinstance(w, ui.tk.Toplevel))
            canvas = next(w for w in win.winfo_children() if isinstance(w, ui.tk.Canvas))
            canvas.event_generate("<ButtonPress-1>", x=10, y=10)
            canvas.event_generate("<ButtonRelease-1>", x=30, y=30)
            next(b for b in buttons(win) if b.cget("text") == "Use this image").invoke()

        ui.root.after(250, edit_and_accept)
        assert ui.preview_image(image, on_approve=accepted.append) is True
        assert accepted and accepted[0].png != image.png
        with Image.open(BytesIO(accepted[0].png)) as redacted:
            assert redacted.getpixel((40, 40)) == (0, 0, 0)
        # The independent emergency watcher must close a modal wait loop even
        # when the ordinary event poll is waiting for approval.
        ui.pending_image = image
        ui.root.after(250, lambda: (ui.stop_event.set(), ui.emergency_ui.set()))
        assert ui.preview_image(image) is False
        assert ui.pending_image is None
        ui.stop_event.clear()
        ui.pending_image = image
        ui.clear_image()
        assert ui.pending_image is None
        print("PASS real Tk: new buttons visible; synthetic image preview; No focused and visible;")
        print("     Enter/Escape deny, explicit Use approves, Clear removes pending bytes.")
    finally:
        ui.root.destroy()
