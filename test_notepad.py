"""Plain-assert offline Notepad policy tests; Windows backend is never started."""
from dataclasses import replace
import socket
import threading
import types
from unittest.mock import patch
import notepad_tools as n
from notepad_native import Snapshot, check_launch_policy
import test_browser_search as h


class Fake:
    def __init__(self):
        self.value=Snapshot("","Untitled - Notepad",100,101,(1,),(2,))
        self.writes=[]
    def snapshot(self):return self.value
    def set_text(self,text):self.writes.append(text);self.value=replace(self.value,text=text)
    def pump(self):pass


def test_approved_edit_verified_once_and_replay_refused():
    fake=Fake();state=n.State(fake);state.read()
    proposal=state.prepare(1,"Paragraph\nSecond line")
    with patch.object(n.time,"sleep"):
        assert "verified" in state.execute(proposal["token"])["text"]
    assert fake.writes==["Paragraph\nSecond line"]
    try:state.execute(proposal["token"])
    except ValueError:pass
    else:raise AssertionError("replay accepted")


def test_preexisting_content_cannot_be_bound():
    fake=Fake();fake.value=replace(fake.value,text="private existing document")
    try:n.State(fake)
    except ValueError:pass
    else:raise AssertionError("nonempty initial document accepted")


def test_stale_number_text_and_identity_refused():
    fake=Fake();state=n.State(fake);state.read();state.read()
    for element in (1,True,"2",0,999):
        try:state.prepare(element,"new")
        except ValueError:pass
        else:raise AssertionError("stale number accepted")
    fake.value=replace(fake.value,text="human edit")
    try:state.prepare(2,"new")
    except ValueError:pass
    else:raise AssertionError("stale text accepted")
    state.read();fake.value=replace(fake.value,edit_runtime=(999,))
    try:state.prepare(3,"new")
    except ValueError:pass
    else:raise AssertionError("different control accepted")
    assert state.halted and not fake.writes


def test_change_after_preview_or_expiry_prevents_write():
    for problem in ("text","expiry","window"):
        fake=Fake();clock=[0];state=n.State(fake,clock=lambda:clock[0]);state.read()
        p=state.prepare(1,"approved")
        if problem=="text":fake.value=replace(fake.value,text="person edited")
        elif problem=="window":fake.value=replace(fake.value,window=999)
        else:clock[0]=121
        try:state.execute(p["token"])
        except ValueError:pass
        else:raise AssertionError("stale/expired preview accepted")
        assert not fake.writes


def test_verification_failure_halts_without_repeating_mutation():
    fake=Fake();state=n.State(fake);state.read();p=state.prepare(1,"approved")
    fake.set_text=lambda text:fake.writes.append(text)
    with patch.object(n.time,"sleep"):
        try:state.execute(p["token"])
        except ValueError:pass
        else:raise AssertionError("unverified edit accepted")
    assert fake.writes==["approved"] and state.halted
    try:state.read()
    except ValueError:pass
    else:raise AssertionError("halted session resumed")


def test_backend_guard_failure_permanently_halts():
    fake=Fake();state=n.State(fake);state.read();p=state.prepare(1,"new")
    fake.snapshot=lambda:(_ for _ in ()).throw(ValueError("menu/dialog changed"))
    try:state.execute(p["token"])
    except ValueError:pass
    else:raise AssertionError("guard bypassed")
    assert state.halted and not fake.writes


def test_text_and_action_budgets_and_nonreused_session_numbers():
    for text in ("x"*2001,"bad\rline","a\x00b","\ud800","😀"*1001):assert n.text_problem(text)
    for text in ("","x"*2000,"line\nline\tend"):assert not n.text_problem(text)
    state=n.State(Fake(),base=10000);assert "[10001]" in state.read()["text"]
    state.actions=50
    try:state.prepare(10001,"new")
    except ValueError:pass
    else:raise AssertionError("action budget bypassed")
    state.reads=1000
    try:state.read()
    except ValueError:pass
    else:raise AssertionError("read budget bypassed")


def test_model_cannot_supply_pid_window_path_url_or_save_tool():
    for tool,args in (("notepad_start",{"path":"C:/private.txt"}),("notepad_read",{"pid":123}),
                      ("notepad_replace",{"element":1,"text":"new","hwnd":123}),
                      ("notepad_replace",{"element":True,"text":"new"}),
                      ("notepad_replace",{"element":1,"text":"new","url":"https://evil.example"})):
        with patch.object(h.core,"prepare_notepad",side_effect=AssertionError("bad arguments reached lookup")):
            result=h.run_calls([h.tool_call(tool,args)],expected_answer=None)
        assert not result.popups
    for name in ("notepad_save","notepad_open_file","notepad_click","notepad_close","commit_notepad"):
        assert name not in h.core.available_functions
    assert n.notepad_start().startswith("Error:") and n.notepad_replace(1,"new").startswith("Error:")


def test_notepad_popup_required_inside_approved_plan_and_denial_prevents_commit():
    preview={"window":"Untitled - Notepad","before":"old","after":"new"}
    for allow in (True,False):
        with patch.object(h.core,"prepare_notepad",return_value={"token":"private-token","preview":preview}), \
             patch.object(h.core,"commit_notepad",return_value="Verified") as commit:
            result=h.run_calls([h.tool_call("propose_plan",{"goal":"read","steps":["open https://approved.example/"]}),
                h.tool_call("notepad_replace",{"element":1,"text":"new"})],decisions={"notepad_action":allow},expected_answer="Done" if allow else None)
        assert [x[0] for x in result.popups]==["plan","notepad_action"]
        assert commit.call_count==int(allow)
        assert "private-token" not in str(result.messages)


def test_callback_cannot_change_frozen_proposal():
    proposal={"token":"fixed","preview":{"before":"old","after":"approved"}}
    def mutate(name,args):args["after"]="mutated"
    with patch.object(h.core,"prepare_notepad",return_value=proposal),patch.object(h.core,"commit_notepad",return_value="Verified") as commit:
        h.run_calls([h.tool_call("notepad_replace",{"element":1,"text":"approved"})],after_popup=mutate)
    assert proposal["preview"]["after"]=="approved";commit.assert_called_once_with("fixed")


def test_start_denial_and_invalid_lookup_never_launch_or_popup():
    with patch.object(h.core,"start_notepad",side_effect=AssertionError("launch denied")):
        result=h.run_calls([h.tool_call("notepad_start",{})],decisions={"notepad_start":False},expected_answer=None)
    assert result.popups[0][0]=="notepad_start"
    with patch.object(h.core,"prepare_notepad",return_value={"error":"stale"}),patch.object(h.core,"commit_notepad",side_effect=AssertionError("must not commit")):
        result=h.run_calls([h.tool_call("notepad_replace",{"element":1,"text":"new"})],expected_answer=None)
    assert not result.popups and any(event[0]=="notepad_refused" for event in result.audit)


def test_stop_during_approval_prevents_commit():
    stopped=threading.Event()
    responses=iter([types.SimpleNamespace(message=types.SimpleNamespace(content="",tool_calls=[h.tool_call("notepad_replace",{"element":1,"text":"new"})]))])
    def approve(*args):stopped.set();return True
    with patch.object(h.core,"chat",side_effect=lambda **kw:next(responses)),patch.object(h.core,"compact",return_value=False), \
         patch.object(h.core,"audit"),patch.object(h.core,"prepare_notepad",return_value={"token":"x","preview":{}}), \
         patch.object(h.core,"commit_notepad",side_effect=AssertionError("stopped")):
        assert h.core.run_turn([],"test",approve,stop_event=stopped)[0].startswith("(stopped")



def test_configured_debugger_policy_is_respected_without_writes():
    class Key:
        def __enter__(self):return self
        def __exit__(self,*args):return False
    fake=types.SimpleNamespace(HKEY_LOCAL_MACHINE=1,KEY_READ=2,KEY_WOW64_64KEY=4,KEY_WOW64_32KEY=8,
        OpenKey=lambda *args:Key(),QueryInfoKey=lambda key:(0,0,0),
        QueryValueEx=lambda *args:(_ for _ in ()).throw(FileNotFoundError()))
    with patch.dict("sys.modules",{"winreg":fake}):
        check_launch_policy()
        fake.QueryValueEx=lambda *args:("configured-debugger",1)
        try:check_launch_policy()
        except ValueError:pass
        else:raise AssertionError("configured debugger overridden")


def test_concurrent_closed_pipe_returns_error_without_private_details():
    stopped=[]
    session=types.SimpleNamespace(request=lambda *args:(_ for _ in ()).throw(ValueError("private closed-pipe detail")),
                                  stop=lambda:stopped.append(True))
    with patch.object(n,"_session",session):
        for result in (n.notepad_read(),n.commit_notepad("opaque")):
            assert result.startswith("Error:") and "private" not in result
    assert stopped==[True,True]


if __name__=="__main__":
    tests=[value for name,value in sorted(globals().items()) if name.startswith("test_")]
    def no_network(*args,**kwargs):raise AssertionError("No Internet allowed")
    with patch.object(socket,"socket",side_effect=no_network),patch.object(socket,"getaddrinfo",side_effect=no_network):
        for test in tests:test();print("PASS",test.__name__)
    print(f"All {len(tests)} offline Notepad tests passed.")
