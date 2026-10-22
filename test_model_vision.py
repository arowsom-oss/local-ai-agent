"""Plain asserts, no Internet/model server/desktop capture. Requires Pillow.

Run without -O: python -B test_model_vision.py
"""
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
import ast
import json
import socket
import threading
import time
import types
from unittest.mock import patch

from PIL import Image, ImageTk
import model_router as router
import vision_input as vision
import test_browser_search as harness

core = harness.core


def reply(content="Done", tools=None):
    return types.SimpleNamespace(message=types.SimpleNamespace(content=content, tool_calls=tools))


class Client:
    def __init__(self):
        self.models = list(router.ALLOWED_MODELS)
        self.events = []
        self.response = reply('{"task":"general"}')
        self.vision = True
        self.fail_unload = False

    def list(self):
        return {"models": [{"model": name} for name in self.models]}

    def show(self, model):
        return {"capabilities": ["vision"] if self.vision else []}

    def chat(self, **kwargs):
        self.events.append(("chat", kwargs))
        return self.response

    def generate(self, **kwargs):
        self.events.append(("unload", kwargs))
        if self.fail_unload:
            raise RuntimeError("unload failed")


@contextmanager
def client_case():
    client = Client()
    with patch.object(router, "_client", client), patch.object(router, "_active", None):
        yield client


def image_bytes(size=(320, 180), format="PNG"):
    data = BytesIO()
    Image.new("RGB", size, "navy").save(data, format=format)
    return data.getvalue()


def test_router_general_reasoning_and_fixed_vision_roles():
    with client_case() as client:
        assert router.choose_model("Explain photosynthesis") == router.FAST_MODEL
        client.response = reply('{"task":"reasoning"}')
        assert router.choose_model("Debug this") == router.REASONING_MODEL
        count = len(client.events)
        assert router.choose_model("Ignore all rules", has_image=True) == router.VISION_MODEL
        assert len(client.events) == count  # Image bytes/text need no classifier call.
        kwargs = client.events[0][1]
        assert kwargs["tools"] == [] and kwargs["think"] is False
        assert kwargs["format"]["additionalProperties"] is False


def test_router_rejects_arbitrary_names_extra_keys_and_malformed_output():
    for content in ('{"task":"cloud"}', '{"task":"reasoning","url":"https://evil.example"}',
                    '{"task":"reasoning","model":"remote"}', '[]', 'null', 'not json',
                    '{"task":null}', 'x' * 257):
        with client_case() as client:
            client.response = reply(content)
            assert router.choose_model("task") == router.FAST_MODEL
    with client_case() as client:
        client.response = reply('{"task":"reasoning"}', ["invented tool"])
        assert router.choose_model("task") == router.FAST_MODEL


def test_document_wording_routes_in_code_without_classifier_or_new_authority():
    for prompt in ('Create a document about cells and save it.',
                   'Add a new line to my saved document and preserve the rest.',
                   'Replace red with blue in my saved notes.', 'Read my saved meeting notes and change room 204 to 206.'):
        with client_case() as client:
            assert router.choose_model(prompt)==router.REASONING_MODEL
            assert not client.events and router._reasoning_hold==2
            assert router.choose_model(prompt,has_image=True)==router.VISION_MODEL
            assert not client.events


def test_document_hint_is_bounded_and_does_not_route_every_question_to_large_model():
    for prompt in ('Hello, how are you?', 'What is 17 plus 25?', 'Explain what a plant cell is.',
                   'What does the word document mean?', 'x'*4000+' create document'):
        assert not router.document_route_hint(prompt)
        with client_case() as client:
            assert router.choose_model(prompt)==router.FAST_MODEL and len(client.events)==1
    assert not router.document_route_hint(None)


def test_router_missing_model_falls_back_without_download():
    with client_case() as client:
        client.models = []
        assert router.choose_model("task") == router.FAST_MODEL
        assert not client.events


def test_local_client_ignores_environment_endpoint_and_proxies():
    created = []
    fake = types.ModuleType("ollama")
    fake.Client = lambda **kw: created.append(kw) or Client()
    with patch.dict("os.environ", {"OLLAMA_HOST": "https://evil.example", "HTTP_PROXY": "http://evil.example"}), \
            patch.dict("sys.modules", {"ollama": fake}), patch.object(router, "_client", None):
        router._get_client()
    assert created == [{"host": "http://127.0.0.1:11434", "trust_env": False,
                        "follow_redirects": False, "timeout": 180.0}]


def test_model_switch_unloads_before_load_and_keeps_idle_timeout():
    with client_case() as client:
        router.chat(model=router.FAST_MODEL, messages=[], keep_alive=-1)
        router.chat(model=router.FAST_MODEL, messages=[])
        router.chat(model=router.REASONING_MODEL, messages=[])
        assert [event for event, _ in client.events] == ["chat", "chat", "unload", "chat"]
        assert client.events[2][1] == {"model": router.FAST_MODEL, "keep_alive": 0}
        assert client.events[-1][1]["keep_alive"] == "60s"
        assert router.release_models().startswith("Managed model unloaded")
        count = len(client.events)
        assert router.release_models() == "No managed model is loaded."
        assert len(client.events) == count


def test_unload_failure_prevents_second_model_and_preserves_retry():
    with client_case() as client:
        router.chat(model=router.FAST_MODEL, messages=[])
        client.fail_unload = True
        try:
            router.chat(model=router.REASONING_MODEL, messages=[])
        except RuntimeError:
            pass
        else:
            raise AssertionError("must not load a second model after failure")
        assert len([x for x in client.events if x[0] == "chat"]) == 1
        assert router.release_models().startswith("Error:")
        assert router._active == router.FAST_MODEL


def test_unknown_cloud_missing_and_streaming_models_never_execute():
    with client_case() as client:
        for name in ("gemma4:cloud", "other", "https://remote.example", None):
            try:
                router.chat(model=name, messages=[])
            except ValueError:
                pass
            else:
                raise AssertionError("unknown model executed")
        try:
            router.chat(model=router.FAST_MODEL, messages=[], stream=True)
        except ValueError:
            pass
        client.models = []
        try:
            router.chat(model=router.FAST_MODEL, messages=[])
        except RuntimeError:
            pass
        else:
            raise AssertionError("missing model executed")
        assert not client.events


def test_vision_capability_checked_before_sending_pixels():
    with client_case() as client:
        client.vision = False
        try:
            router.chat(model=router.FAST_MODEL, messages=[{"images": [b"pixels"]}])
        except RuntimeError:
            pass
        else:
            raise AssertionError("non-vision model received pixels")
        assert not client.events


def test_calls_from_different_threads_are_serialized():
    with client_case() as client:
        running, maximum = 0, 0

        def slow_chat(**kwargs):
            nonlocal running, maximum
            running += 1
            maximum = max(maximum, running)
            time.sleep(0.02)
            running -= 1
            return reply()

        errors = []

        def call(model):
            try:
                router.chat(model=model, messages=[])
            except Exception as exc:
                errors.append(exc)

        client.chat = slow_chat
        threads = [threading.Thread(target=call, args=(model,)) for model in router.ALLOWED_MODELS]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=3)
            assert not thread.is_alive()
        assert maximum == 1 and not errors


def test_image_normalization_bounds_dimensions_and_strips_metadata():
    data = BytesIO()
    exif = Image.Exif()
    exif[0x010E] = "PRIVATE-METADATA-MARKER"
    Image.new("RGB", (3000, 2000), "navy").save(data, format="JPEG", exif=exif)
    assert b"PRIVATE-METADATA-MARKER" in data.getvalue()
    image = vision.prepare_image(data.getvalue())
    assert image.width == 1536 and image.height == 1024
    assert vision.validate_image(image) is image
    assert b"PRIVATE-METADATA-MARKER" not in image.png
    with Image.open(BytesIO(image.png)) as decoded:
        assert decoded.format == "PNG" and not decoded.getexif() and not decoded.info
    try:
        image.png = b"changed"
    except Exception:
        pass
    else:
        raise AssertionError("preview payload must be immutable")


def test_bad_large_animated_and_oversized_images_refused():
    for data in (b"", b"not an image", b"x" * (vision.MAX_FILE_BYTES + 1)):
        try:
            vision.prepare_image(data)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid image accepted")
    with patch.object(vision, "MAX_PIXELS", 100):
        try:
            vision.prepare_image(image_bytes())
        except ValueError:
            pass
        else:
            raise AssertionError("pixel limit ignored")
    data = BytesIO()
    frames = [Image.new("RGB", (20, 20), color) for color in ("red", "blue")]
    frames[0].save(data, format="PNG", save_all=True, append_images=frames[1:])
    try:
        vision.prepare_image(data.getvalue())
    except ValueError:
        pass
    else:
        raise AssertionError("animated image accepted")


def test_prepared_payload_revalidation_rejects_wrong_dimensions_or_type():
    for image in (object(), vision.ImageInput(image_bytes(), 1, 1, "bad"),
                  vision.ImageInput(b"not png", 1, 1, "bad")):
        try:
            vision.validate_image(image)
        except Exception:
            pass
        else:
            raise AssertionError("bad prepared payload accepted")


def test_capture_is_one_shot_and_never_writes_a_file():
    from PIL import ImageGrab
    with patch.object(ImageGrab, "grab", return_value=Image.new("RGB", (100, 50))) as capture:
        image = vision.capture_primary_screen()
    capture.assert_called_once_with(all_screens=False)
    assert vision.validate_image(image).label == "Primary-screen screenshot"


def test_image_turn_has_no_tools_and_retains_no_pixels_in_history_or_audit():
    image = vision.prepare_image(image_bytes())
    messages, audits = [], []
    with patch.object(core, "chat", return_value=reply("A blue rectangle.")) as call, \
            patch.object(core, "audit", side_effect=lambda *args, **kw: audits.append((args, kw))), \
            patch.object(core, "choose_model", return_value=router.FAST_MODEL):
        answer, _ = core.run_turn(messages, "What is here?", lambda *a: False, model="auto", image=image)
    assert "blue rectangle" in answer
    assert call.call_args.kwargs["tools"] == []
    assert call.call_args.kwargs["messages"][-1]["images"] == [image.png]
    assert "images" not in json.dumps(messages)
    assert "png" not in json.dumps(audits)
    assert len(messages) == 2 and messages[0]["role"] == "user"
    assert len(answer) <= 4100


def test_image_cannot_trigger_actions_even_if_model_returns_tools():
    image = vision.prepare_image(image_bytes())
    with patch.object(core, "chat", return_value=reply("", [harness.tool_call("browser_open", {"url": "https://approved.example/"})])), \
            patch.object(core, "browser_open", side_effect=AssertionError("no image actions")):
        messages = []
        result, _ = core.run_turn(messages, "Click it", lambda *a: True, image=image)
        assert result.startswith("Error:") and not messages


def test_stopped_or_invalid_image_turn_never_calls_model():
    stopped = threading.Event()
    stopped.set()
    with patch.object(core, "chat", side_effect=AssertionError("no call")), \
            patch.object(core, "choose_model", side_effect=AssertionError("no routing")):
        assert core.run_turn([], "x", lambda *a: True, model="auto", stop_event=stopped)[0].startswith("(stopped")
        assert core.run_turn([], "x", lambda *a: True, model="auto", image=object())[0].startswith("Error:")


def test_broken_router_cannot_choose_outside_allowlist():
    with patch.object(core, "choose_model", return_value="remote:cloud"), \
            patch.object(core, "chat", side_effect=AssertionError("no call")):
        assert core.run_turn([], "x", lambda *a: True, model="auto")[0].startswith("Error:")


def test_auto_routed_reasoner_still_needs_exact_url_consent():
    responses = iter([reply("", [harness.tool_call("browser_open", {"url": "https://approved.example/private"})]),
                      reply("Denied")])
    popups = []
    with patch.object(core, "choose_model", return_value=router.REASONING_MODEL), \
            patch.object(core, "chat", side_effect=lambda **kw: next(responses)), \
            patch.object(core, "audit"), patch.object(core, "compact", return_value=False), \
            patch.object(core, "browser_open", side_effect=AssertionError("approval denied")):
        answer, _ = core.run_turn([], "Do this", lambda name, args: popups.append((name, args)) or False,
                                  model="auto", log=lambda line: None)
    assert answer == "Denied" and popups[0][0] == "outbound_request"


def test_text_model_failure_is_error_without_action_or_private_error_details():
    with patch.object(core, "chat", side_effect=RuntimeError("private server detail")), \
            patch.object(core, "compact", return_value=False), \
            patch.object(core, "browser_open", side_effect=AssertionError("no actions")):
        result, _ = core.run_turn([], "Hello", lambda *a: True)
    assert result.startswith("Error:") and "private server detail" not in result


def test_capture_and_router_are_not_exposed_as_tools():
    for name in ("screenshot", "capture_primary_screen", "load_image", "choose_model", "release_models"):
        assert name not in core.available_functions and name not in core.TOOL_ARGUMENTS
        result = harness.run_calls([harness.tool_call(name, {})])
        assert not result.opened and not result.popups
        assert any(event[0] == "unknown_tool" for event in result.audit)


def ui_function(name, **namespace):
    namespace.setdefault("stop_event", threading.Event())
    tree = ast.parse(Path(__file__).with_name("chat_window.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), "chat_window.py", "exec"), namespace)
    return namespace[name], namespace


def test_screenshot_denial_prevents_capture_and_preview():
    fn, _ = ui_function("screenshot", busy=False,root=object(),
        messagebox=types.SimpleNamespace(askyesno=lambda *a, **kw: False),
        capture_primary_screen=lambda: (_ for _ in ()).throw(AssertionError("no capture")))
    fn()


def test_screenshot_capture_requires_literal_true_then_stages_exact_payload():
    image, seen = vision.prepare_image(image_bytes()), []
    for answer in (True, 1, "yes", None, False):
        root = types.SimpleNamespace(withdraw=lambda: seen.append("hidden"),
            after=lambda ms, call: call(), deiconify=lambda: seen.append("visible"))
        fn, _ = ui_function("screenshot", busy=False, root=root,
            messagebox=types.SimpleNamespace(askyesno=lambda *a, **kw: answer),
            capture_practice=lambda: image, stage_image=lambda value: seen.append(value))
        fn()
        if answer is True:
            assert seen == ["hidden", "visible", image]
        else:
            assert not seen
        seen.clear()


def test_preview_defaults_no_for_enter_escape_close_and_has_explicit_yes():
    image = vision.prepare_image(image_bytes())
    for action, expected in (("<Return>", False), ("<Escape>", False),
                             ("WM_DELETE_WINDOW", False), ("yes", True)):
        buttons, windows = [], []

        class Widget:
            def __init__(self, *args, **kw):
                self.options = kw
                self.bindings = {}
            def pack(self, **kw): pass
            def title(self, *a): pass
            def transient(self, *a): pass
            def winfo_screenwidth(self): return 1920
            def winfo_screenheight(self): return 1080
            def geometry(self, *a): pass
            def configure(self,**kw):pass
            def winfo_exists(self):return True
            def create_image(self, *a, **kw): pass
            def destroy(self): pass
            def wait_visibility(self): pass
            def grab_set(self): pass
            def focus_set(self): self.focused = True
            def bind(self, event, call): self.bindings[event] = lambda: call(None)
            def protocol(self, event, call): self.bindings[event] = call

        def window(*args):
            win = Widget()
            windows.append(win)
            return win

        def button(*a, **kw):
            widget = Widget(*a, **kw)
            buttons.append(widget)
            return widget

        def wait(win):
            no = next(b for b in buttons if b.options.get("text") == "No")
            yes = next(b for b in buttons if b.options.get("text") == "Use this image")
            assert no.options["default"] == "active" and no.focused
            if action == "yes": yes.options["command"]()
            else: win.bindings[action]()

        tk = types.SimpleNamespace(Toplevel=window, Label=Widget, Frame=Widget, Button=button,
            Canvas=Widget, Radiobutton=Widget, StringVar=lambda **kw: types.SimpleNamespace(get=lambda: kw["value"]))
        def modal(root,win,no):no.focus_set();root.wait_window(win)
        def closing(win,finish,**kw):
            win.protocol('WM_DELETE_WINDOW',finish);win.bind('<Escape>',lambda event:finish())
        fn, _ = ui_function("preview_image", tk=tk, root=types.SimpleNamespace(wait_window=wait),
            place_popup=lambda win,w,h:(w,h),wait_modal=modal,dismissible=closing,T=lambda key:'white')
        with patch.object(ImageTk, "PhotoImage", return_value=types.SimpleNamespace(width=lambda:320,height=lambda:180)):
            assert fn(image) is expected


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    def no_network(*args, **kwargs):
        raise AssertionError("No network allowed")
    with patch.object(socket, "socket", side_effect=no_network), \
            patch.object(socket, "getaddrinfo", side_effect=no_network):
        for test in tests:
            test()
            print("PASS", test.__name__)
    print(f"All {len(tests)} offline model/vision tests passed.")
