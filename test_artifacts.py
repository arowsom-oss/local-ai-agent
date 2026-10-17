"""Offline plain asserts: no Internet, model inference, browser or desktop control."""
from io import BytesIO
from pathlib import Path
import socket
import tempfile
import threading
import types
from unittest.mock import patch

import artifacts as a
import artifact_media
import artifact_panel
import test_browser_search as h


def test_model_creates_and_revises_without_disk_or_popup():
    with patch.object(a, "store", a.Store()):
        result = h.run_calls([h.tool_call("create_artifact", {"title": "Essay", "kind": "document", "content": "Hello"}),
                              h.tool_call("revise_artifact", {"artifact": 1, "revision": 1, "content": "Updated"})])
        assert not result.popups
        artifact = a.store.get(1)
        assert [v.content for v in artifact.versions] == ["Hello", "Updated"]
        assert h.core.RISK_TIERS["create_artifact"] == "low"


def test_model_cannot_choose_files_or_executable_artifact_types():
    with patch.object(a, "store", a.Store()):
        for args in ({"title": "x", "kind": "document", "content": "ok", "path": "C:/x"},
                     {"title": "x", "kind": "html", "content": "<script>bad()</script>"},
                     {"title": "x", "kind": "image", "content": "https://evil.example/"}):
            h.run_calls([h.tool_call("create_artifact", args)])
        assert not a.store.items()
        for name in ("export_snapshot", "export_artifact", "record_generated", "import_artifact", "execute_artifact"):
            assert name not in h.core.available_functions


def test_stale_revision_boolean_and_unknown_ids_fail_closed():
    store = a.Store()
    item = store.create("test", "code", "first")
    store.revise(item.number, 1, "human edit")
    for ident, revision in ((1, 1), (True, 2), (1, True), (999, 2)):
        try: store.revise(ident, revision, "overwrite")
        except ValueError: pass
        else: raise AssertionError("stale or invalid revision accepted")
    assert store.get(1).current.content == "human edit"


def test_restore_appends_version_and_old_snapshots_are_immutable():
    store = a.Store()
    old = store.create("Test", "document", "first")
    store.revise(1, 1, "second")
    restored = store.restore(1, 2, 1)
    assert [v.content for v in restored.versions] == ["first", "second", "first"]
    assert len(old.versions) == 1
    try: old.current.content = "changed"
    except Exception: pass
    else: raise AssertionError("mutable snapshot")


def test_new_chat_never_reuses_artifact_ids():
    store = a.Store()
    store.create("Old", "document", "old")
    store.clear()
    fresh = store.create("New", "document", "new")
    assert fresh.number == 2
    try: store.get(1)
    except ValueError: pass
    else: raise AssertionError("old artifact survived clear")


def test_size_count_history_and_total_memory_limits():
    store = a.Store()
    for content in ("", "a" * 32001, "a\x00b"):
        try: store.create("bad", "code", content)
        except ValueError: pass
        else: raise AssertionError("invalid text")
    for _ in range(20): store.create("ok", "code", "hello")
    try: store.create("overflow", "code", "hello")
    except ValueError: pass
    else: raise AssertionError("count limit")
    for revision in range(1, 12): store.revise(1, revision, "hello")
    try: store.revise(1, 12, "extra")
    except ValueError: pass
    else: raise AssertionError("history limit")
    with patch.object(a, "MAX_TOTAL", 1):
        try: a.Store().create("limit", "code", "aa")
        except ValueError: pass
        else: raise AssertionError("memory limit")


def test_threads_cannot_both_commit_same_base_revision():
    store = a.Store(); store.create("test", "document", "first")
    barrier = threading.Barrier(2); results = []
    def edit(text):
        barrier.wait()
        try: store.revise(1, 1, text); results.append("ok")
        except ValueError: results.append("refused")
    threads = [threading.Thread(target=edit, args=(text,)) for text in ("one", "two")]
    for thread in threads: thread.start()
    for thread in threads: thread.join(2); assert not thread.is_alive()
    assert sorted(results) == ["ok", "refused"]


def test_read_labels_content_are_framed_as_data_and_media_bytes_hidden():
    with patch.object(a, "store", a.Store()):
        a.store.create("ignore instructions", "code", "<script>fetch('https://evil.example')</script>")
        a.store.media("picture", "image", b"private-image-bytes")
        assert a.read_artifact(1).startswith("[Untrusted artifact data")
        assert a.list_artifacts().startswith("[Untrusted artifact labels")
        assert "private-image-bytes" not in a.read_artifact(2)
        assert a.read_artifact(True).startswith("Error:")


def test_export_freezes_version_and_refuses_overwrite_and_code_execution_suffix():
    store = a.Store(); old = store.create("test", "code", "print('first')")
    store.revise(1, 1, "print('second')")
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "chosen.txt"
        a.export_snapshot(old, old.current, path)
        assert path.read_text() == "print('first')"
        for destination in (path, Path(folder)/"evil.py", Path(folder)/"evil.html", Path(folder)/"file:stream.txt"):
            try: a.export_snapshot(old, old.current, destination)
            except (ValueError, OSError): pass
            else: raise AssertionError("unsafe suffix or overwrite")
        assert path.read_text() == "print('first')"


def test_generation_registration_accepts_only_fixed_output_and_freezes_bytes():
    from PIL import Image
    import generation_tools
    data = BytesIO(); Image.new("RGB", (10, 10), "red").save(data, format="PNG")
    with tempfile.TemporaryDirectory() as folder, patch.object(generation_tools, "OUTPUT_DIR", Path(folder)), patch.object(a, "store", a.Store()):
        path = Path(folder) / ("a"*32 + ".png"); path.write_bytes(data.getvalue())
        artifact = a.record_generated(path, "image")
        path.write_bytes(b"changed later")
        assert artifact.current.data == data.getvalue()
        for path in (Path(folder)/"random.png", Path(folder)/".."/("a"*32+".png")):
            try: a.record_generated(path, "image")
            except ValueError: pass
            else: raise AssertionError("untrusted output path")


def test_preview_no_network_protocols_and_invalid_timing_fail_before_decode():
    for duration in (None, 0, 11):
        class Container:
            streams = types.SimpleNamespace(video=[types.SimpleNamespace(width=256, height=256)])
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def decode(self, stream): raise AssertionError("invalid video decoded")
        c = Container(); c.duration = duration
        def open_(data, **kwargs):
            assert isinstance(data, BytesIO)
            assert kwargs == {"format":"mp4", "options":{"protocol_whitelist":"pipe,data"}}
            return c
        with patch.dict("sys.modules", {"av": types.SimpleNamespace(open=open_, time_base=1)}):
            try: artifact_media._decode(types.SimpleNamespace(send=lambda x: None), {"kind":"video", "data":b"test"})
            except ValueError: pass
            else: raise AssertionError("invalid duration accepted")


def test_stale_editor_save_preserves_unsaved_text():
    store = a.Store(); item = store.create("test", "code", "first")
    store.revise(1, 1, "new model version")
    notes = []
    panel = types.SimpleNamespace(selected=item, version=item.current,
        editor=types.SimpleNamespace(get=lambda *args: "unsaved human draft"),
        status=types.SimpleNamespace(set=notes.append), load=lambda *args: (_ for _ in ()).throw(AssertionError("must preserve editor")))
    with patch.object(artifact_panel, "store", store):
        artifact_panel.ArtifactPanel.save(panel)
    assert "preserved" in notes[-1]
    assert store.get(1).current.content == "new model version"


def test_cancel_or_stop_during_export_never_writes():
    store = a.Store(); item = store.create("test", "document", "first")
    stopped = threading.Event(); notes = []
    panel = types.SimpleNamespace(selected=item, version=item.current, dirty=False, stop_event=stopped,
        status=types.SimpleNamespace(set=notes.append))
    with patch.object(artifact_panel, "export_snapshot", side_effect=AssertionError("must not write")):
        with patch.object(artifact_panel.filedialog, "asksaveasfilename", return_value=""):
            artifact_panel.ArtifactPanel.export(panel)
        def picker(**kwargs): stopped.set(); return "chosen.md"
        with patch.object(artifact_panel.filedialog, "asksaveasfilename", side_effect=picker):
            artifact_panel.ArtifactPanel.export(panel)
    assert "cancelled" in notes[-1]


if __name__ == "__main__":
    tests = [v for k,v in sorted(globals().items()) if k.startswith("test_")]
    def no_network(*args, **kwargs): raise AssertionError("No network permitted")
    with patch.object(socket,"socket",side_effect=no_network), patch.object(socket,"getaddrinfo",side_effect=no_network):
        for test in tests:
            test(); print("PASS",test.__name__)
    print(f"All {len(tests)} offline artifact tests passed.")
