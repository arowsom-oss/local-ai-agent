"""Real Windows/Tk and local codecs; synthetic fixtures, no Internet or inference."""
from io import BytesIO
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
from PIL import Image
import av
import chat_window as ui
from artifacts import store, create_artifact


def pump_until(test, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ui.root.update()
        if test(): return
        time.sleep(.03)
    raise AssertionError("UI fixture timed out")


if __name__ == "__main__":
    ui.build_window()
    ui.root.geometry("1280x800")
    panel = ui.artifact_panel
    errors = []
    ui.root.report_callback_exception = lambda kind,value,trace: errors.append(value)
    try:
        ui.root.update()
        assert panel.winfo_ismapped() and panel.winfo_width() > 350
        create_artifact("Study guide", "document", "# Cells\nA cell is a basic unit of life.")
        pump_until(lambda: panel.selected is not None)
        ident = panel.selected.number
        assert panel.editor.get("1.0", "end-1c").startswith("# Cells")
        panel.editor.insert("end", "\nHuman note.")
        ui.root.update()
        assert panel.dirty
        panel.save()
        assert store.get(ident).current.number == 2 and "Human note" in store.get(ident).current.content
        panel.history.set("1"); panel.choose_version(); panel.restore()
        assert store.get(ident).current.number == 3 and "Human note" not in store.get(ident).current.content
        panel.editor.insert("end", "\nUnsaved text")
        ui.root.update()
        store.revise(ident, 3, "New AI version")
        panel.refresh()
        assert "Unsaved text" in panel.editor.get("1.0", "end-1c")
        panel.save()
        assert store.get(ident).current.content == "New AI version"
        with patch("artifact_panel.messagebox.askyesno", return_value=True): panel.reload()
        source = "<script>fetch('https://must-not-run.invalid')</script>"
        code = store.create("HTML is source only", "code", source)
        panel.load(code.number)
        assert panel.editor.get("1.0", "end-1c") == source
        with tempfile.TemporaryDirectory() as folder:
            export = Path(folder) / "selected.txt"
            with patch("artifact_panel.filedialog.asksaveasfilename", return_value=str(export)):
                panel.export()
            assert export.read_text() == source
            data = BytesIO(); Image.new("RGB", (256,256), "navy").save(data,format="PNG")
            image = store.media("Synthetic image", "image", data.getvalue())
            panel.load(image.number)
            pump_until(lambda: len(panel.frames)==1)
            assert panel.photo is not None
            clip = Path(folder)/"fixture.mp4"
            with av.open(str(clip),"w") as container:
                stream=container.add_stream("libx264",rate=8)
                stream.width=stream.height=256;stream.pix_fmt="yuv420p"
                for index in range(16):
                    frame=av.VideoFrame.from_image(Image.new("RGB",(256,256),(index*12,0,100)))
                    for packet in stream.encode(frame):container.mux(packet)
                for packet in stream.encode():container.mux(packet)
            video = store.media("Synthetic video", "video", clip.read_bytes())
            panel.load(video.number)
            pump_until(lambda: len(panel.frames)==16)
            panel.toggle_play()
            pump_until(lambda: panel.timeline.get()>0)
            ui.stop_agent()
            assert not panel.playing
            assert ui.stop_event.is_set()
            ui.stop_event.clear()
            # Actual import normalizes JPEG bytes; subsequent PNG export uses PNG bytes.
            jpeg=Path(folder)/"sample.jpg";Image.new("RGB",(40,30),"green").save(jpeg)
            with patch("artifact_panel.filedialog.askopenfilename",return_value=str(jpeg)):
                panel.import_file()
            pump_until(lambda: panel.selected.title=="Imported image" and len(panel.frames)==1)
            assert panel.version.data.startswith(b"\x89PNG")
        ui.stop_event.set()
        with patch("chat_window.messagebox.askyesno", return_value=True), patch("chat_window.free_vram"):
            ui.new_chat()
        assert not store.items() and not ui.stop_event.is_set()
        assert panel.selected is None and not panel.frames and panel.editor.get("1.0","end-1c")==""
        assert not errors, errors
        print("PASS real Tk artifacts: split panel, edit/history/restore, stale human edits preserved,")
        print("     inert HTML, chosen-path export, isolated PNG/MP4 decode/playback, Stop and import normalization.")
    finally:
        ui.stop_all()
        ui.root.destroy()
