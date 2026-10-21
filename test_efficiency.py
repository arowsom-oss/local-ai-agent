"""Offline regressions for wasted work, cancellation and incomplete model replies."""
import ast
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import queue
import socket
import tempfile
import threading
import types
from unittest.mock import patch

import artifact_panel as panel_module
import artifacts
import generation_tools as generation
import media_resources
import model_router
import test_browser_search as h


def reply(content='Ready.', calls=(), reason='stop'):
    return types.SimpleNamespace(message=types.SimpleNamespace(role='assistant', content=content,
        tool_calls=list(calls)), done_reason=reason)


def test_stop_during_compaction_prevents_another_inference():
    stop = threading.Event()
    def compact(*args, **kwargs): stop.set()
    with patch.object(h.core, 'compact', side_effect=compact), patch.object(h.core, 'audit'), \
            patch.object(h.core, 'chat', return_value=reply()) as chat:
        answer, _ = h.core.run_turn([], 'Hi', lambda *a:False, stop_event=stop, log=lambda s:None)
    assert chat.call_count == 0, 'Stop during compaction still started another model inference'
    assert answer == '(stopped by you)'


def test_stop_during_reply_discards_late_content_and_actions():
    for calls in ([], [h.tool_call('add', {'a':1, 'b':2})]):
        stop = threading.Event(); messages = []
        def late(**kwargs): stop.set(); return reply('Late answer', calls)
        with patch.object(h.core, 'chat', side_effect=late), patch.object(h.core, 'audit'), \
                patch.object(h.core, 'compact', return_value=False):
            answer, _ = h.core.run_turn(messages, 'Hi', lambda *a:False, stop_event=stop, log=lambda s:None)
        assert answer == '(stopped by you)' and len(messages) == 1, 'Late stopped reply entered history'


def test_empty_replies_are_errors_instead_of_breaking_the_ui():
    for content in (None, '', ' \n\t'):
        with patch.object(h.core, 'chat', return_value=reply(content)), patch.object(h.core, 'audit'):
            answer, _ = h.core.run_turn([], 'Hi', lambda *a:False, log=lambda s:None)
        assert isinstance(answer, str) and answer.startswith('Error:'), 'Empty reply can break UI polling'


def test_incomplete_or_empty_media_observation_is_not_presented_as_complete():
    for bad in (reply(None), reply(''), reply('partial', reason='length')):
        messages=[]
        with patch.object(h.core, 'chat', return_value=bad), patch.object(h.core, 'audit'):
            answer, _ = h.core.run_turn(messages, 'Describe this.', lambda *a:False,
                observation_text='Synthetic audio transcript.', log=lambda s:None)
        assert answer.startswith('Error:') and not messages


def old_history():
    return [{'role':'user','content':'x'*25000}, {'role':'assistant','content':'old'}] + [
        {'role':'user','content':'recent'} for _ in range(6)]


def test_failed_compaction_never_replaces_the_original_history():
    for bad in (reply(None), reply(''), reply('partial', reason='length'),
                reply('summary', [h.tool_call('add', {'a':1,'b':2})]), reply('x'*2001)):
        messages=old_history(); before=deepcopy(messages)
        with patch.object(h.core, 'chat', return_value=bad), patch.object(h.core, 'audit'):
            try: h.core.compact(messages, model_router.FAST_MODEL, log=lambda s:None)
            except ValueError: pass
            else: raise AssertionError('Invalid compaction silently discarded conversation history')
        assert messages == before


def test_tool_arguments_count_toward_history_and_survive_summary_input():
    payload='PRIVATE SYNTHETIC DRAFT ' + 'x'*26000
    messages=[{'role':'user','content':'Create this'}, reply('', [
        h.tool_call('create_artifact', {'title':'Draft','kind':'document','content':payload})]).message]
    messages.extend({'role':'user','content':'recent'} for _ in range(6))
    assert h.core.estimate_tokens(messages) > h.core.COMPACT_AT, 'Tool arguments were invisible to compaction'
    seen=[]
    with patch.object(h.core, 'chat', side_effect=lambda **kw:seen.append(kw) or reply('Bounded summary.')), \
            patch.object(h.core, 'audit'):
        assert h.core.compact(messages, model_router.FAST_MODEL, log=lambda s:None)
    assert 'create_artifact' in seen[0]['messages'][0]['content']
    assert 'PRIVATE SYNTHETIC DRAFT' in seen[0]['messages'][0]['content']


def test_generation_cancelled_while_waiting_does_not_start_a_gpu_worker():
    for stage in ('lease', 'ram'):
        stop=threading.Event()
        @contextmanager
        def lease():
            if stage=='lease': stop.set()
            yield
        def memory(*args):
            if stage=='ram': stop.set()
        with patch.object(generation, 'local_asset', return_value=Path('fixed-local-model')), \
                patch.object(model_router, 'media_lease', lease), patch.object(media_resources, 'require_ram', side_effect=memory), \
                patch.object(generation, 'Worker') as worker:
            worker.return_value.receive.return_value={'ok':True}
            result=generation.run_generation('video', 'A synthetic scene', stop)
        assert not worker.called, 'A queued cancelled job still started a heavy GPU worker'
        assert 'stopped' in result['error']


class Value:
    def __init__(self, value=None): self.value=value
    def set(self, value): self.value=value
    def get(self, *args): return self.value
    def configure(self, **kwargs): pass
    def pack(self, **kwargs): pass


def import_panel():
    store=artifacts.Store(); original=store.create('Article','document','Original')
    jobs=[]; loads=[]
    panel=types.SimpleNamespace(selected=original, version=original.current, dirty=False,
        serial=1, stop_event=threading.Event(), playing=False, play_job=None,
        frames=[], photo=None, signature=((original.number,1),), choice=Value(), image=Value(),
        timeline=Value(0), play_row=Value(), status=Value(), editor=Value('Original'),
        mail=queue.Queue(), after=lambda *a:None, tick=lambda:None, show_frame=lambda index:None)
    def load(number, revision=None, **kwargs):
        panel.serial+=1; panel.selected=store.get(number); panel.version=panel.selected.current
        panel.dirty=False; loads.append((number,kwargs))
        if kwargs.get('preview') is None: jobs.append('decode-again')
        else: panel.frames=kwargs['preview']
    panel.load=load
    panel.discard_ok=lambda:True
    panel.preview_stop=None
    panel.cancel_preview=lambda:panel_module.ArtifactPanel.cancel_preview(panel)
    panel.pause_playback=lambda:panel_module.ArtifactPanel.pause_playback(panel)
    panel.refresh=lambda:panel_module.ArtifactPanel.refresh(panel)
    return panel,store,jobs,loads


def enqueue_import(panel, frames):
    """Use the production request shape on both old and fixed source."""
    captured=[]
    panel.decode=lambda kind,data,imported=None:captured.append(imported)
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'selected.jpg'; path.write_bytes(b'person selected JPEG')
        with patch.object(panel_module.filedialog,'askopenfilename',return_value=str(path)):
            panel_module.ArtifactPanel.import_file(panel)
    assert len(captured)==1
    panel.mail.put((panel.serial,frames,captured[0],None))


def test_imported_media_reuses_validated_frames_once():
    panel, store, jobs, loads=import_panel()
    frames=[(0.0, types.SimpleNamespace(png=b'normalized PNG'))]
    enqueue_import(panel, frames)
    with patch.object(panel_module, 'store', store): panel_module.ArtifactPanel.tick(panel)
    assert panel.selected.kind=='image' and panel.frames is frames
    assert not jobs and len(loads)==1, 'An import was decoded again after validation'
    assert panel.version.data==b'normalized PNG'


def test_async_import_preserves_text_edited_during_validation():
    panel, store, jobs, loads=import_panel()
    frames=[(0.0,types.SimpleNamespace(png=b'normalized PNG'))]
    enqueue_import(panel, frames)
    panel.editor.set('Original plus new human edit'); panel.dirty=True
    with patch.object(panel_module, 'store', store): panel_module.ArtifactPanel.tick(panel)
    assert panel.selected.kind=='document' and panel.dirty and not loads
    assert panel.editor.value.endswith('new human edit') and len(store.items())==2


def test_replaced_preview_cancels_worker_and_does_not_queue_stale_pixels():
    panel, store, jobs, loads=import_panel()
    panel.preview_stop=None
    class InlineThread:
        def __init__(self, target, **kw): self.target=target
        def start(self): self.target()
    def cancelled_preview(kind,data,stop):
        panel_module.ArtifactPanel.cancel_preview(panel)
        assert stop.is_set()
        return [(0.0,types.SimpleNamespace(png=b'old pixels'))]
    with patch.object(panel_module.threading,'Thread',InlineThread), \
            patch.object(panel_module,'prepare_preview',side_effect=cancelled_preview):
        panel_module.ArtifactPanel.decode(panel,'image',b'synthetic')
    assert panel.mail.empty(), 'Stale decoded pixels retained after cancellation'


def test_rapid_pause_resume_has_only_one_playback_timer():
    pending={}; counter=iter(range(10)); cancelled=[]
    panel=types.SimpleNamespace(frames=[(0.0,None),(.5,None),(1.0,None)], serial=1,
        stop_event=threading.Event(), playing=False, play_job=None, timeline=Value(0))
    def after(ms, callback):
        key=next(counter); pending[key]=callback; return key
    def cancel(key): cancelled.append(key); pending.pop(key,None)
    panel.after=after; panel.after_cancel=cancel
    panel.pause_playback=lambda:panel_module.ArtifactPanel.pause_playback(panel)
    panel.advance=lambda serial:panel_module.ArtifactPanel.advance(panel,serial)
    for _ in range(3): panel_module.ArtifactPanel.toggle_play(panel)
    assert len(pending)==1 and cancelled, 'Pause/resume accumulated multiple frame timers'
    panel.pause_playback()
    assert not pending and not panel.playing


def test_display_clean_handles_missing_text_without_killing_poll():
    tree=ast.parse(Path(__file__).with_name('chat_window.py').read_text(encoding='utf-8'))
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='clean')
    import re
    ns={'re':re};exec(compile(ast.Module(body=[node], type_ignores=[]),'chat_window.py','exec'),ns)
    assert ns['clean'](None)=='' and ns['clean']('**Text** `x`')=='Text x'


if __name__=='__main__':
    import sys
    failures=[]
    tests=[v for k,v in sorted(globals().items()) if k.startswith('test_')]
    def no_network(*args,**kwargs):raise AssertionError('Offline tests cannot use the network')
    with patch.object(socket,'socket',side_effect=no_network), patch.object(socket,'getaddrinfo',side_effect=no_network):
        for test in tests:
            try:test();print('PASS',test.__name__)
            except Exception as exc:
                failures.append(test.__name__); print('FAIL',test.__name__,type(exc).__name__,str(exc))
    print(json.dumps(dict(tests=len(tests), failures=failures)))
    sys.exit(bool(failures))
