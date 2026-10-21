"""Plain-assert offline tests for step 4; run with Python 3.12, without -O.

Only the standard library is needed. Network, Ollama, HTTPX, browser pages and
popups are faked. The real fetch.py is never imported. The UI's actual confirm
function is loaded through AST so importing it cannot create a Tk window.
"""

import ast
import copy
import importlib.util
import inspect
from pathlib import Path
import socket
import sys
import threading
import types
from unittest.mock import patch
from urllib.parse import urlsplit


HERE = Path(__file__).resolve().parent
fake_fetch = types.ModuleType("fetch")
fake_fetch.ALLOWED_HOSTS = {"approved.example"}
fake_fetch.session_hosts = set()
fake_fetch.USER_AGENT = "offline-tests"


def check_site(url):
    try:
        parts = urlsplit(url)
        if (parts.scheme != "https" or not parts.hostname or parts.port not in (None, 443)
                or parts.hostname in {"localhost", "192.168.1.1"}):
            return None, "URL refused"
        return parts.hostname, None
    except Exception:
        return None, "URL refused"


def is_allowed(url):
    host, problem = check_site(url)
    return problem is None and (host in fake_fetch.ALLOWED_HOSTS or host in fake_fetch.session_hosts)


def no_external_call(*args, **kwargs):
    raise AssertionError("Offline test attempted an external call")


fake_fetch.check_new_site = check_site
fake_fetch.is_allowed = is_allowed
fake_fetch.safe_ip = no_external_call
fake_fetch.fetch_page = no_external_call
fake_httpx = types.ModuleType("httpx")
fake_httpx.Client = no_external_call
fake_ollama = types.ModuleType("ollama")
fake_ollama.chat = no_external_call
fake_download = types.ModuleType("download")
fake_download.download_file = no_external_call


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[name]
    return module


with patch.dict(sys.modules, {"fetch": fake_fetch, "httpx": fake_httpx}):
    browser = load_module("step4_browser_test_target", "browser_tool.py")
with patch.dict(sys.modules, {
    "fetch": fake_fetch, "browser_tool": browser,
    "ollama": fake_ollama, "download": fake_download,
}):
    core = load_module("step4_core_test_target", "agent_core.py")

real_search_url_for = browser.search_url_for


def box(**changes):
    item = {
        "tag": "input", "type": "search", "shown": True,
        "href": "", "text": "Search the library", "name": "q",
        "inside_form": True, "form_action": "https://approved.example/search",
        "form_method": "GET",
    }
    item.update(changes)
    return item


class FakePage:
    def __init__(self, elements):
        self.url = "https://approved.example/"
        self.elements = elements
        self.owner = threading.get_ident()
        self.lookups = []
        self.opened = []

    def assert_owner(self):
        assert threading.get_ident() == self.owner, "Page crossed threads"

    def locator(self, selector):
        self.assert_owner()
        if selector == "body":
            return types.SimpleNamespace(inner_text=lambda **kwargs: "A library search page")
        assert selector == browser._ELEMENT_SELECTOR
        return self

    def evaluate_all(self, script):
        self.assert_owner()
        assert script == browser._LIST_ELEMENTS_JS
        self.lookups.append(script)
        return copy.deepcopy(self.elements)

    def goto(self, url, **kwargs):
        self.assert_owner()
        self.opened.append(url)
        self.url = url

    def wait_for_timeout(self, milliseconds):
        self.assert_owner()


def session_with(*items):
    session = browser._Session()
    session.page = FakePage(list(items or (box(),)))
    session.list_elements()
    return session


def resolved(session, element=1, text="hello"):
    """Exercise the public tuple parser as well as the recorded-element lookup."""
    with patch.object(browser, "_worker", object()), \
            patch.object(browser, "_send", side_effect=lambda command, payload: (
                session.search_url(*payload) if command == "search_url" else "Error: wrong command"
            )):
        return real_search_url_for(element, text)


def test_get_search_url_encoding_and_only_named_text():
    session = session_with(box(name="search term"))
    url, label = resolved(session, text="cats & dogs + café?")
    assert url == "https://approved.example/search?search+term=cats+%26+dogs+%2B+caf%C3%A9%3F"
    assert label == "Search the library"
    # No value, hidden field or other existing form value is sent.
    assert set(session.elements[1]) >= {"name", "form_action", "form_method", "inside_form"}


def test_empty_method_text_box_and_query_replacement():
    session = session_with(box(
        type="text", form_method="", form_action="https://approved.example/search?old=secret#section",
    ))
    assert resolved(session)[0] == "https://approved.example/search?q=hello"
    assert session.elements[1]["kind"] == "text box"


def test_post_and_unknown_methods_refused():
    for method in ("POST", "post", "dialog", "PUT", None):
        assert resolved(session_with(box(form_method=method)))[0] is None


def test_missing_name_or_form_refused():
    for changes in ({"name": ""}, {"name": None}, {"inside_form": False},
                    {"inside_form": None}, {"form_action": ""}):
        assert resolved(session_with(box(**changes)))[0] is None


def test_invalid_text_refused_before_worker_or_popup():
    for text in ("", "a" * 101, "person@example.com", "1234567", "a1234567z",
                 "two\nlines", "two\rlines", "a\tb", "\x00", None, 123,
                 "١٢٣٤٥٦٧", "²²²²²²²"):
        with patch.object(browser, "_send", side_effect=AssertionError("must not queue invalid text")):
            url, reason = browser.search_url_for(1, text)
        assert url is None and reason


def test_text_boundaries_and_six_digits_allowed():
    for text in ("a", "x" * 100, "123456", "123456 7", "café & dogs"):
        assert resolved(session_with(), text=text)[0] is not None


def test_password_hidden_link_and_bad_numbers_refused():
    session = session_with(box(type="password"), box(shown=False), box())
    assert len(session.elements) == 1
    assert session.elements[1]["type"] == "search"
    for element in (0, 2, -1, True, "1", None):
        assert resolved(session, element=element)[0] is None
    session = session_with(box(tag="a", href="https://approved.example/"))
    assert resolved(session)[0] is None
    # Even inconsistent saved metadata must not turn a password into a text box.
    session.elements[1].update(kind="text box", type="password")
    assert resolved(session)[0] is None


def test_malformed_action_and_missing_page_fail_closed():
    assert resolved(session_with(box(form_action="https://[invalid")))[0] is None
    with patch.object(browser, "_worker", None):
        assert browser.search_url_for(1, "hello")[0] is None
    with patch.object(browser, "_worker", object()), \
            patch.object(browser, "_send", side_effect=RuntimeError("worker failed")):
        assert browser.search_url_for(1, "hello")[0] is None


def tool_call(name, args):
    return types.SimpleNamespace(function=types.SimpleNamespace(name=name, arguments=args))


def run_calls(calls, session=None, decisions=None, after_popup=None, open_result="Page opened.", initial_hosts=(), expected_answer="Done", after_open=None):
    """Run the real model/tool loop with a scripted model and approval recorder."""
    session = session or session_with()
    popups, audit_events, logs, opened, messages, tool_schemas = [], [], [], [], [], []
    lookups = []
    replies = iter([
        types.SimpleNamespace(message=types.SimpleNamespace(tool_calls=calls, content="")),
        types.SimpleNamespace(message=types.SimpleNamespace(tool_calls=[], content="Done")),
    ])
    decisions = decisions or {}

    def chat(**kwargs):
        tool_schemas.append(kwargs["tools"])
        return next(replies)

    def ask(name, args):
        popups.append((name, copy.deepcopy(args)))
        if after_popup is not None:
            after_popup(name, args)
        return decisions.get(name, True)

    def lookup(element, text):
        lookups.append((element, text))
        return resolved(session, element, text)

    def open_url(url):
        assert is_allowed(url), "Unapproved site reached browser_open"
        opened.append(url)
        if after_open is not None:after_open()
        return open_result

    def audit(event, name, args, model, note=""):
        audit_events.append((event, name, copy.deepcopy(args), note))

    fake_fetch.session_hosts.clear()
    fake_fetch.session_hosts.update(initial_hosts)
    with patch.object(core, "chat", side_effect=chat), \
            patch.object(core, "audit", side_effect=audit), \
            patch.object(core, "compact", return_value=False), \
            patch.object(core, "search_url_for", side_effect=lookup), \
            patch.object(core, "browser_open", side_effect=open_url), \
            patch.dict(core.available_functions, {"browser_open": open_url}), \
            patch.object(core, "link_labels", return_value=["Next"]):
        answer, _ = core.run_turn(messages, "Search the library", ask, log=logs.append)
    if expected_answer is None:assert "Notepad workflow paused" in answer
    else:assert answer == expected_answer
    return types.SimpleNamespace(
        popups=popups, audit=audit_events, logs=logs, opened=opened,
        messages=messages, schemas=tool_schemas, lookups=lookups, answer=answer,
    )


def search_call(**changes):
    args = {"element": 1, "text": "cats & dogs"}
    args.update(changes)
    return tool_call("browser_search", args)


def assert_refused(result):
    assert not result.opened
    assert any(event[0] == "search_refused" for event in result.audit)
    assert any(line.startswith("[blocked] browser_search") for line in result.logs)
    assert any(isinstance(m, dict) and m.get("content", "").startswith("Error:")
               for m in result.messages if isinstance(m, dict) and m.get("role") == "tool")


def test_search_own_popup_and_schema():
    result = run_calls([search_call()])
    expected_url = "https://approved.example/search?q=cats+%26+dogs"
    assert result.popups == [("browser_search", {
        "element": 1, "box": "Search the library", "text": "cats & dogs", "url": expected_url,
    })]
    assert result.opened == [expected_url]
    assert "browser_search" in core.NEEDS_APPROVAL
    assert core.available_functions["browser_search"] is browser.browser_search
    assert browser.browser_search in result.schemas[0]
    assert list(inspect.signature(browser.browser_search).parameters) == ["element", "text"]
    assert "Args:" in browser.browser_search.__doc__


def test_popup_even_mid_plan_without_consuming_plan_step():
    result = run_calls([
        tool_call("propose_plan", {"goal": "Open a page", "steps": ["open https://approved.example/next"]}),
        search_call(),
        tool_call("browser_open", {"url": "https://approved.example/next"}),
    ])
    assert [name for name, _ in result.popups] == ["plan", "browser_search"]
    assert len(result.opened) == 2
    assert sum(event[0] == "step_done" for event in result.audit) == 1
    assert not any(event[0] == "plan_changed" for event in result.audit)


def test_approved_host_does_not_authorize_model_written_url():
    assert core.RISK_TIERS["browser_open"] == core.RISK_TIERS["fetch_page"] == "high"
    assert "browser_open" in core.NEEDS_APPROVAL and "fetch_page" in core.NEEDS_APPROVAL
    result = run_calls([tool_call("browser_open", {"url": "https://approved.example/"})])
    assert [name for name, _ in result.popups] == ["outbound_request"]
    assert result.opened == ["https://approved.example/"]


def test_every_arbitrary_url_tool_requires_exact_data_approval():
    urls = (
        "https://approved.example/?q=DEMO_PRIVATE_TEXT",
        "https://approved.example/DEMO_PRIVATE_TEXT",
        "https://approved.example/?%44%45%4d%4f=value",
        "https://approved.example/?q=RE VNTw==".replace(" ", ""),
        "https://approved.example/?q=person%40example.com&number=1234567",
    )
    for name in ("browser_open", "fetch_page"):
        for url in urls:
            sent = []
            with patch.dict(core.available_functions, {"fetch_page": lambda url: sent.append(url) or "Fetched."}):
                denied = run_calls([tool_call(name, {"url": url})], decisions={"outbound_request": False})
                assert denied.popups == [("outbound_request", {"tool": name, "url": url})]
                assert denied.opened == sent == []
                assert any(e[0] == "outbound_refused" for e in denied.audit)
                allowed = run_calls([tool_call(name, {"url": url})])
                assert allowed.popups == [("outbound_request", {"tool": name, "url": url})]
                assert (allowed.opened if name == "browser_open" else sent) == [url]


def test_plan_refuses_query_or_fragment():
    for url in ("https://approved.example/?q=DEMO_PRIVATE_TEXT", "https://approved.example/a#DEMO",
                "https://approved.example/" + "a" * 300, "https://user:pw@approved.example/",
                "https://approved.example/\u200bhidden", "https://192.168.1.1/"):
        result = run_calls([tool_call("propose_plan", {"goal": "Read", "steps": ["open " + url]})])
        assert result.popups == [], url              # refused before you ever see it
        assert any(e[0] == "plan_refused" for e in result.audit)


def test_plan_does_not_cover_fetch_page_or_off_plan_urls():
    url = "https://approved.example/page"
    for name, other in (("fetch_page", url), ("browser_open", url + "2")):
        result = run_calls([
            tool_call("propose_plan", {"goal": "Read", "steps": ["open " + url]}),
            tool_call(name, {"url": other}),
        ], decisions={"outbound_request": False, "plan_changed": True})
        assert [n for n, _ in result.popups][-1] == "outbound_request", (name, result.popups)
        assert not result.opened


def test_session_host_grant_does_not_approve_data():
    result = run_calls([tool_call("browser_open", {"url": "https://session.example/private"})],
                       initial_hosts={"session.example"}, decisions={"outbound_request": False})
    assert [name for name, _ in result.popups] == ["outbound_request"]
    assert not result.opened


def test_new_site_popup_covers_only_the_address_it_showed():
    result = run_calls([tool_call("browser_open", {"url": "https://new.example/private"})],
                       decisions={"outbound_request": False})
    assert result.popups == [("new_site", {"host": "new.example", "url": "https://new.example/private"})]
    assert result.opened == ["https://new.example/private"]
    assert any(e[0] == "outbound_covered" for e in result.audit)
    # the SECOND address on that now-approved site is not covered
    result = run_calls([tool_call("browser_open", {"url": "https://new.example/a"}),
                        tool_call("browser_open", {"url": "https://new.example/b?q=DEMO"})],
                       decisions={"outbound_request": False})
    assert [n for n, _ in result.popups] == ["new_site", "outbound_request"]
    assert result.opened == ["https://new.example/a"]


def test_new_site_no_means_nothing_sent():
    result = run_calls([tool_call("browser_open", {"url": "https://new.example/private"})],
                       decisions={"new_site": False})
    assert [n for n, _ in result.popups] == ["new_site"] and not result.opened


def test_malformed_urls_refused_before_popup():
    for url in ("https://name:password@approved.example/", "https://approved.example/\nsecret",
                "https://approved.example/with space", "https://approved.example\\@evil.example/",
                "https://approved.example/" + "a" * 4096):
        result = run_calls([tool_call("browser_open", {"url": url})])
        assert result.popups == result.opened == []
        assert any(e[0] == "outbound_refused" for e in result.audit)


def test_approval_must_be_literal_true_and_exceptions_deny():
    for answer in (False, None, 1, "yes", "no", [True]):
        result = run_calls([tool_call("browser_open", {"url": "https://approved.example/"})],
                           decisions={"outbound_request": answer})
        assert not result.opened
    def broken_popup(name, args):
        raise RuntimeError("UI failed")
    result = run_calls([tool_call("browser_open", {"url": "https://approved.example/"})],
                       after_popup=broken_popup)
    assert not result.opened


def test_popup_cannot_mutate_approved_url():
    url = "https://approved.example/original?q=hello"
    def mutate(name, args):
        if name == "outbound_request":
            args["url"] = "https://approved.example/changed?q=secret"
    result = run_calls([tool_call("browser_open", {"url": url})], after_popup=mutate)
    assert result.opened == [url]


def test_outbound_popup_displays_full_url_and_warning():
    tree = ast.parse((HERE / "chat_window.py").read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "confirm"
             or isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "WHAT_IT_DOES" for t in n.targets)]
    shown = []
    ns = {"high_risk_confirm": lambda title, lines: shown.append((title, lines)) or False}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "chat_window.py", "exec"), ns)
    url = "https://approved.example/" + "x" * 2000 + "?q=EXACT"
    assert ns["confirm"]("outbound_request", {"tool": "fetch_page", "url": url}) is False
    assert url in shown[0][1]
    assert "private data" in "\n".join(shown[0][1])


def test_downloads_are_blocked_without_schema_or_popup():
    result = run_calls([tool_call("download_file", {"url": "https://approved.example/file"})])
    assert result.popups == [] and result.opened == []
    assert "download_file" not in core.available_functions
    assert all(getattr(tool, "__name__", "") != "download_file" for tool in result.schemas[0])
    assert any(event[0] == "policy_refused" for event in result.audit)


def test_all_tool_arguments_are_checked_before_popup():
    for name, args in (
        ("add", {"a": True, "b": 2}), ("multiply", {"a": 1, "b": "2"}),
        ("browser_read", {"url": "https://evil.example/"}),
        ("browser_open", {"url": 42}), ("read_file", {"name": "x", "extra": 1}),
    ):
        result = run_calls([tool_call(name, args)])
        assert not result.popups and not result.opened
        assert any(event[0] == "arguments_refused" for event in result.audit)


def test_stale_numbers_never_reused_between_reads_or_navigation():
    session = session_with()
    first = next(iter(session.elements))
    session.list_elements()
    second = next(iter(session.elements))
    assert second > first
    assert resolved(session, first)[0] is None
    assert resolved(session, second)[0] is not None
    session.invalidate_elements()
    assert resolved(session, second)[0] is None
    session.list_elements()
    third = next(iter(session.elements))
    assert third > second
    session.page.url = "https://approved.example/elsewhere"
    assert resolved(session, third)[0] is None
    assert session.labels().startswith("Error:")


def test_same_url_main_frame_navigation_invalidates_map():
    session = session_with()
    frame = object()
    session.page.main_frame = frame
    session.navigated(object())  # An unrelated subframe does not replace this page.
    assert session.elements
    session.navigated(frame)  # Includes a reload with no URL change.
    assert not session.elements
    assert resolved(session)[0] is None


def test_search_steps_never_accepted_in_plan():
    for step in ("search cats", "search 1 cats", "browser_search 1 cats"):
        plan, reason = core.parse_plan({"goal": "Search", "steps": [step]})
        assert plan is None and reason
    result = run_calls([tool_call("propose_plan", {"goal": "Search", "steps": ["search cats"]})])
    assert not result.popups and not result.opened
    assert any(event[0] == "plan_refused" for event in result.audit)


def test_existing_click_plan_still_works():
    with patch.object(core, "link_for", return_value=("https://approved.example/next", "Next")):
        result = run_calls([
            tool_call("propose_plan", {"goal": "Follow a link", "steps": ["click Next"]}),
            tool_call("browser_click", {"element": 2}),
        ])
    assert [name for name, _ in result.popups] == ["plan"]
    assert result.opened == ["https://approved.example/next"]
    assert sum(event[0] == "step_done" for event in result.audit) == 1


def test_open_new_site_needs_one_popup():
    result = run_calls([tool_call("browser_open", {"url": "https://new.example/"})])
    assert [name for name, _ in result.popups] == ["new_site"]
    assert result.opened == ["https://new.example/"]


def test_search_new_site_needs_two_popups_even_mid_plan():
    session = session_with(box(form_action="https://new.example/find"))
    result = run_calls([
        tool_call("propose_plan", {"goal": "Read", "steps": ["open https://approved.example/next"]}),
        search_call(),
    ], session=session)
    expected = "https://new.example/find?q=cats+%26+dogs"
    assert [name for name, _ in result.popups] == ["plan", "new_site", "browser_search"]
    assert result.popups[1][1] == {"host": "new.example", "url": expected}
    assert result.popups[2][1]["url"] == expected
    assert result.opened == [expected]


def test_new_site_denial_prevents_search():
    result = run_calls([search_call()], session=session_with(box(form_action="https://new.example/")),
                       decisions={"new_site": False})
    assert [name for name, _ in result.popups] == ["new_site"]
    assert "new.example" not in fake_fetch.session_hosts
    assert_refused(result)


def test_search_denied_after_new_site_approved():
    result = run_calls([search_call()], session=session_with(box(form_action="https://new.example/")),
                       decisions={"browser_search": False})
    assert [name for name, _ in result.popups] == ["new_site", "browser_search"]
    assert_refused(result)


def test_search_denied_even_with_approved_plan():
    result = run_calls([
        tool_call("propose_plan", {"goal": "Read", "steps": ["open https://approved.example/next"]}),
        search_call(),
    ], decisions={"browser_search": False})
    assert [name for name, _ in result.popups] == ["plan", "browser_search"]
    assert_refused(result)


def test_model_supplied_url_or_unknown_args_refused_before_lookup():
    for arguments in (
        {"element": 1, "text": "hello", "url": "https://evil.example/"},
        {"element": 1, "text": "hello", "box": "Fake label"},
        {"element": 1}, {"text": "hello"}, "not a dict", None,
    ):
        result = run_calls([tool_call("browser_search", arguments)])
        assert not result.lookups
        assert not result.popups
        assert_refused(result)


def test_text_rules_and_form_rules_refused_before_any_popup():
    for text in ("person@example.com", "1234567", "hello\nworld", "", "x" * 101):
        result = run_calls([search_call(text=text)], session=session_with(box(form_action="https://new.example/")))
        assert not result.popups
        assert_refused(result)
    for changes in ({"form_method": "POST"}, {"name": ""}, {"inside_form": False}, {"type": "password"}):
        result = run_calls([search_call()], session=session_with(box(**changes)))
        assert not result.popups
        assert_refused(result)


def test_invalid_action_site_refused_before_popup():
    for action in ("file:///C:/secret.txt", "http://approved.example/", "https://192.168.1.1/"):
        result = run_calls([search_call()], session=session_with(box(form_action=action)))
        assert not result.popups
        assert_refused(result)


def test_exact_approved_url_is_not_looked_up_again():
    session = session_with()

    def change_page(name, args):
        if name == "browser_search":
            session.elements[1]["form_action"] = "https://evil.example/changed"

    result = run_calls([search_call()], session=session, after_popup=change_page)
    assert result.opened == [result.popups[0][1]["url"]]
    assert "evil.example" not in result.opened[0]


def test_open_error_logs_search_refusal():
    result = run_calls([search_call()], open_result="Error: Host is not approved.")
    assert len(result.popups) == 1
    assert any(event[0] == "search_refused" for event in result.audit)
    assert any(line.startswith("[blocked] browser_search") for line in result.logs)


def test_browser_search_uses_browser_open_and_returns_errors():
    session = session_with()
    with patch.object(browser, "search_url_for", side_effect=lambda n, t: resolved(session, n, t)), \
            patch.object(browser, "browser_open", return_value="Page opened.") as opener:
        assert browser.browser_search(1, "hello") == "Page opened."
        opener.assert_called_once_with("https://approved.example/search?q=hello")
    with patch.object(browser, "search_url_for", return_value=(None, "bad form")), \
            patch.object(browser, "browser_open", side_effect=AssertionError("must not open")):
        assert browser.browser_search(1, "hello") == "Error: bad form"


def test_real_search_worker_from_two_different_caller_threads():
    assert browser.close_browser() == "Browser closed."
    sessions, results = [], []
    original_session = browser._Session

    class WorkerSession(original_session):
        def __init__(self):
            super().__init__()
            self.page = FakePage([box()])
            self.list_elements()
            sessions.append(self)

    barrier = threading.Barrier(3)

    def caller(text):
        barrier.wait(timeout=5)
        result = browser.search_url_for(1, text)
        results.append((threading.get_ident(), result))

    with patch.object(browser, "_Session", WorkerSession):
        try:
            # Start the worker lazily on the first valid search lookup, as a real
            # chat would already have done with browser_open/browser_read.
            with browser._lock:
                browser._worker = browser._Worker()
            threads = [threading.Thread(target=caller, args=(text,)) for text in ("cats", "dogs")]
            for thread in threads:
                thread.start()
            barrier.wait(timeout=5)
            for thread in threads:
                thread.join(timeout=5)
                assert not thread.is_alive()
            assert len(results) == 2 and len({ident for ident, _ in results}) == 2
            assert all(result[0] == "https://approved.example/search?q=" + text
                       for (_, result), text in zip(sorted(results, key=lambda r: r[1][0]), ("cats", "dogs")))
            assert len(sessions) == 1
            page = sessions[0].page
            assert all(ident != page.owner for ident, _ in results)
            assert page.opened == []
            assert browser.browser_search(1, "cats") == "Page opened."
            assert browser.browser_search(1, "dogs").startswith("Error:")
            assert page.opened == ["https://approved.example/search?q=cats"]
        finally:
            assert browser.close_browser() == "Browser closed."


def test_popup_exact_text_label_full_url_and_default_no():
    tree = ast.parse((HERE / "chat_window.py").read_text(encoding="utf-8"))
    selected = [node for node in tree.body if (
        isinstance(node, ast.FunctionDef) and node.name == "confirm"
    ) or (
        isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "WHAT_IT_DOES" for t in node.targets)
    )]
    shown = []

    def askyesno(title, message, **kwargs):
        shown.append((title, message, kwargs))
        return False

    namespace = {"messagebox": types.SimpleNamespace(askyesno=askyesno),
                 "high_risk_confirm": lambda title, lines: askyesno(title, "\n".join(lines), default="no")}
    exec(compile(ast.Module(body=selected, type_ignores=[]), "chat_window.py", "exec"), namespace)
    full_url = "https://approved.example/" + "x" * 500 + "?q=cats+%26+dogs"
    assert namespace["confirm"]("browser_search", {
        "element": 1, "box": "Search the library", "text": "cats & dogs", "url": full_url,
    }) is False
    title, message, options = shown[0]
    assert "SUBMITS A SEARCH on a website" in message
    assert "Box: Search the library" in message
    assert "\ncats & dogs\n" in message
    assert full_url in message
    assert options["default"] == "no"


def test_topic_search_builds_fixed_encoded_url_without_open_page():
    with patch.object(browser, "_worker", None), patch.object(browser, "_send", side_effect=no_external_call):
        url, provider = browser.web_search_url_for("Mars & café + facts?")
    assert provider == "DuckDuckGo Lite"
    assert url == "https://lite.duckduckgo.com/lite/?q=Mars+%26+caf%C3%A9+%2B+facts%3F&kp=1"


def test_topic_search_invalid_queries_refused_before_popup():
    for query in ("", " ", "x"*101, "me@example.com", "1234567", "a\nb", "!g cats", None, 123):
        if not isinstance(query, str):
            assert browser.web_search_url_for(query)[0] is None
            continue
        result = run_calls([tool_call("browser_web_search", {"query": query})])
        assert not result.popups and not result.opened
        assert any(event[0] == "search_refused" for event in result.audit)


def test_topic_search_cannot_accept_model_address_or_approval():
    for extra in ({"url": "https://evil.example/"}, {"approved": True}, {"provider": "evil"}):
        result = run_calls([tool_call("browser_web_search", {"query": "Mars", **extra})])
        assert not result.popups and not result.opened
        assert any(event[0] == "search_refused" for event in result.audit)
    assert inspect.signature(core.available_functions['browser_web_search']).parameters.keys() == {'query'}


def topic_calls(decisions=None, initial_hosts=(), after_popup=None, plan=False, open_result="Page opened.", expected_answer="Done", after_open=None):
    calls = [tool_call("browser_web_search", {"query": "Mars facts"})]
    if plan:
        calls.insert(0, tool_call("propose_plan", {"goal": "Read", "steps": ["open https://approved.example/"]}))
    with patch.object(core, "browser_read", return_value=browser.TEXT_PREFIX + "\n[1] NASA source") as reader:
        result = run_calls(calls, decisions=decisions, initial_hosts=initial_hosts,
                           after_popup=after_popup, open_result=open_result, expected_answer=expected_answer, after_open=after_open)
        result.reads = reader.call_count
    return result


def test_topic_search_new_site_and_exact_own_popup():
    result = topic_calls()
    url = "https://lite.duckduckgo.com/lite/?q=Mars+facts&kp=1"
    assert [name for name, _ in result.popups] == ['new_site', 'browser_web_search']
    assert result.popups[1][1] == {'query':'Mars facts', 'provider':'DuckDuckGo Lite', 'url':url}
    assert result.opened == [url] and result.reads == 1
    assert any(m.get('content','').startswith(browser.TEXT_PREFIX) for m in result.messages if isinstance(m,dict))


def test_topic_search_never_covered_by_site_or_plan():
    for plan in (False, True):
        result = topic_calls(initial_hosts={'lite.duckduckgo.com'}, plan=plan,
                             decisions={'browser_web_search':False})
        assert [n for n,_ in result.popups] == (['plan'] if plan else []) + ['browser_web_search']
        assert not result.opened and result.reads == 0
    assert core.parse_plan({'goal':'Search','steps':['search Mars']})[0] is None


def test_topic_search_new_site_denial_and_stop_send_nothing():
    result = topic_calls(decisions={'new_site':False})
    assert [n for n,_ in result.popups] == ['new_site'] and not result.opened and not result.reads
    import threading
    stop = threading.Event()
    def stopped_popup(name, args):
        if name=='browser_web_search':stop.set()
    with patch.object(core, 'stopped', side_effect=lambda ignored:stop.is_set()):
        result = topic_calls(after_popup=stopped_popup, expected_answer="(stopped by you)")
    assert not result.opened and not result.reads


def test_topic_search_popup_cannot_change_url_and_open_error_skips_read():
    def mutate(name,args):
        args['url']='https://evil.example/changed'
        args['query']='changed'
    result=topic_calls(after_popup=mutate)
    assert result.opened == ['https://lite.duckduckgo.com/lite/?q=Mars+facts&kp=1']
    result=topic_calls(open_result='Error: network failed')
    assert result.reads == 0 and any(e[0]=='search_refused' for e in result.audit)


def test_topic_search_wrapper_decoding_only_on_fixed_provider_page():
    from urllib.parse import urlencode
    target='https://science.nasa.gov/mars/facts/?x=a%26b'
    wrapper='https://duckduckgo.com/l/?'+urlencode({'uddg':target,'rut':'opaque'})
    page='https://lite.duckduckgo.com/lite/?q=Mars'
    assert browser._recorded_link_url(wrapper,page)==target
    assert browser._recorded_link_url(wrapper,'https://approved.example/')==wrapper
    assert browser._recorded_link_url(wrapper,page.replace('/lite/','/elsewhere'))==wrapper
    for bad in ('http://evil.example/', 'https://192.168.1.1/', 'file:///secret',
                'https://user:pass@evil.example/', 'https://evil.example/a b', 'https://evil.example/\n'):
        assert browser._recorded_link_url('https://duckduckgo.com/l/?'+urlencode({'uddg':bad}),page)==''
    assert browser._recorded_link_url(wrapper+'&uddg=https://evil.example/',page)==''
    assert browser._recorded_link_url('https://duckduckgo.com/l/?rut=missing',page)==''
    spoof=wrapper.replace('duckduckgo.com/l/', 'duckduckgo.com.evil.example/l/')
    assert browser._recorded_link_url(spoof,page)==spoof


def test_topic_result_number_keeps_decoded_destination_and_is_stale_after_read():
    session=session_with(box(tag='a',href='https://duckduckgo.com/l/?uddg=https%3A%2F%2Fnew.example%2Ffacts'))
    session.page.url='https://lite.duckduckgo.com/lite/?q=Mars'
    session.list_elements();number=next(iter(session.elements))
    assert session.lookup(number)=='OK https://new.example/facts\nSearch the library'
    session.list_elements()
    assert session.lookup(number).startswith('Error:')
    with patch.object(core,'link_for',return_value=('https://new.example/facts','NASA facts')):
        result=run_calls([tool_call('browser_click',{'element':number})],decisions={'new_site':False})
    assert [n for n,_ in result.popups]==['new_site'] and not result.opened


def test_topic_search_public_wrapper_and_resume_evidence():
    with patch.object(browser,'browser_open',return_value='Page opened.') as opener, \
         patch.object(browser,'browser_read',return_value=browser.TEXT_PREFIX+'\nNASA') as reader:
        assert browser.browser_web_search('Mars').startswith(browser.TEXT_PREFIX)
        opener.assert_called_once_with('https://lite.duckduckgo.com/lite/?q=Mars&kp=1')
        assert reader.call_count==1
    evidence=core.TurnEvidence(resume=True)
    evidence.result('browser_web_search',browser.TEXT_PREFIX+'\nNASA')
    assert not evidence.problem('browser_click',{'element':1})
    evidence.result('browser_open','Page opened.')
    assert evidence.problem('browser_click',{'element':1})


def test_topic_popup_shows_query_provider_url_and_defaults_no():
    tree=ast.parse((HERE/'chat_window.py').read_text(encoding='utf-8'))
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='confirm'
           or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='WHAT_IT_DOES' for t in n.targets)]
    shown=[]
    namespace={'high_risk_confirm':lambda title,lines:shown.append((title,lines)) or False}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'chat_window.py','exec'),namespace)
    url='https://lite.duckduckgo.com/lite/?q=Mars&kp=1'
    assert namespace['confirm']('browser_web_search',{'query':'Mars','provider':'DuckDuckGo Lite','url':url}) is False
    assert 'Mars' in shown[0][1] and url in shown[0][1]
    assert 'private information' in '\n'.join(shown[0][1])


def test_topic_read_wrong_url_argument_gives_specific_guidance():
    result=run_calls([tool_call('browser_read',{'url':'https://approved.example/'})])
    assert not result.popups and not result.opened
    errors=[m['content'] for m in result.messages if isinstance(m,dict) and m.get('role')=='tool']
    assert 'browser_read takes no arguments' in errors[0] and 'browser_click' in errors[0]


def test_topic_click_returns_exact_opened_source_address():
    url='https://approved.example/'+'a'*120+'?topic=Mars'
    with patch.object(core,'link_for',return_value=(url,'NASA facts')):
        result=run_calls([tool_call('browser_click',{'element':7})])
    observations=[m['content'] for m in result.messages if isinstance(m,dict) and m.get('role')=='tool']
    assert result.opened==[url] and 'Opened URL: '+url in observations[0]
    assert 'Earlier page numbers are invalid' in observations[0]


def test_topic_stop_during_navigation_skips_following_read():
    stop=threading.Event()
    with patch.object(core,'stopped',side_effect=lambda ignored:stop.is_set()):
        result=topic_calls(after_open=stop.set,expected_answer='(stopped by you)')
    assert len(result.opened)==1 and result.reads==0


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    with patch.object(socket, "socket", side_effect=no_external_call), \
            patch.object(socket, "getaddrinfo", side_effect=no_external_call):
        for test in tests:
            try:
                test()
            finally:
                browser.close_browser()
                fake_fetch.session_hosts.clear()
            print(f"PASS {test.__name__}")
    print(f"All {len(tests)} offline tests passed.")
