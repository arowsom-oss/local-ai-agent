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
    data = BytesIO()
    Image.new("RGB", (1200, 800), "navy").save(data, format="PNG")
    image = vision_input.prepare_image(data.getvalue())
    ui.root.geometry("1080x800")
    ui.root.update()
    ui.root.focus_force()  # Activate our own fixture, as when the person clicks its button.
    ui.root.update()
    errors = []

    def callback_error(kind, value, trace):
        errors.append(value)
        for child in ui.root.winfo_children():
            if isinstance(child, ui.tk.Toplevel):
                child.destroy()

    ui.root.report_callback_exception = callback_error
    for text in ("Screenshot", "Attach image", "Clear image", "Free VRAM"):
        button = next(b for b in buttons(ui.root) if b.cget("text") == text)
        assert button.winfo_ismapped() and button.winfo_width() > 10

    def act(action):
        win = next(w for w in ui.root.winfo_children() if isinstance(w, ui.tk.Toplevel))
        no = next(b for b in buttons(win) if b.cget("text") == "No")
        assert ui.root.focus_get() == no
        assert no.winfo_ismapped() and no.winfo_rooty() + no.winfo_height() < win.winfo_screenheight()
        if action == "yes":
            next(b for b in buttons(win) if b.cget("text") == "Use this image").invoke()
        else:
            win.event_generate(action)

    try:
        for action, expected in (("<Return>", False), ("<Escape>", False), ("yes", True)):
            ui.root.after(250, lambda value=action: act(value))
            assert ui.preview_image(image) is expected
            assert not errors, errors
        ui.pending_image = image
        ui.clear_image()
        assert ui.pending_image is None
        print("PASS real Tk: new buttons visible; synthetic image preview; No focused and visible;")
        print("     Enter/Escape deny, explicit Use approves, Clear removes pending bytes.")
    finally:
        ui.root.destroy()
