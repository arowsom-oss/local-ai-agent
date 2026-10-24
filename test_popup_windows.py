"""Offline close/cancel lifecycle tests with fakes, no display/network/model."""
import ast
from collections import deque
import queue
import types
from pathlib import Path
from unittest.mock import patch
import popup_windows as p


class Window:
    def __init__(self):self.exists=True;self.callbacks={};self.destroyed=0;self.grab=None
    def winfo_exists(self):return self.exists
    def destroy(self):self.exists=False;self.destroyed+=1
    def protocol(self,name,fn):self.callbacks[name]=fn
    def bind(self,name,fn):self.callbacks[name]=fn
    def geometry(self,value):self.size=value
    def minsize(self,*values):self.minimum=values
    def wait_visibility(self):pass
    def grab_set(self):self.grab=self
    def grab_release(self):self.grab=None
    def focus_set(self):pass


def test_close_escape_and_x_call_cleanup_once_and_destroy():
    for action in ('WM_DELETE_WINDOW','<Escape>','button'):
        win=Window();calls=[]
        fn=p.dismissible(win,lambda:calls.append('cancel'),button=False)
        result=fn() if action=='button' else win.callbacks[action](None) if action=='<Escape>' else win.callbacks[action]()
        assert result=='break' and calls==['cancel'] and win.destroyed==1
        fn();assert calls==['cancel'] and win.destroyed==1


def test_cleanup_exception_cannot_leave_the_popup_open():
    win=Window()
    def fail():raise ValueError('fixture cleanup failed')
    fn=p.dismissible(win,fail,button=False)
    try:fn()
    except ValueError:pass
    else:raise AssertionError('Expected fixture failure')
    assert not win.exists


def test_geometry_fits_short_and_negative_coordinate_work_areas():
    for area in ((0,0,640,480),(-1280,0,0,720),(1920,80,3840,1080)):
        win=Window()
        with patch.object(p,'work_area',return_value=area):w,h=p.place_popup(win,900,900)
        assert w<=area[2]-area[0]-40 and h<=area[3]-area[1]-80
        assert win.minimum[0]<=w and win.minimum[1]<=h
        if area[0]<0:assert '+-' in win.size


def test_modal_exception_releases_grab_and_restores_enclosing_modal():
    win=Window();outer=Window();current=[outer]
    win.grab_set=lambda:current.__setitem__(0,win)
    win.grab_release=lambda:current.__setitem__(0,None)
    outer.grab_set=lambda:current.__setitem__(0,outer)
    class Root:
        def grab_current(self):return current[0]
        def wait_window(self,window):raise ValueError('fixture wait failed')
    try:p.wait_modal(Root(),win,Window())
    except ValueError:pass
    else:raise AssertionError('Expected fixture failure')
    assert not win.exists and current[0] is outer


def test_all_custom_popup_constructors_have_close_handling():
    expected={'chat_window.py':{'high_risk_confirm','preview_image','share_personal_edge_tab',
              'connect_edge_tab','choose_edge_work_tab','show_log'},
              'progress_panel.py':{'details'},'workspace_panel.py':{'show_documents'},
              'popup_windows.py':{'askyesno'},'chat_library_panel.py':{'__init__','project_editor'},
              'document_qa_panel.py':{'__init__'}}
    for name,functions in expected.items():
        tree=ast.parse(Path(__file__).with_name(name).read_text(encoding='utf-8'))
        found=set()
        for node in ast.walk(tree):
            if not isinstance(node,ast.FunctionDef):continue
            calls=[n for n in ast.walk(node) if isinstance(n,ast.Call)]
            if not any(isinstance(c.func,ast.Attribute) and c.func.attr=='Toplevel' for c in calls):continue
            found.add(node.name)
            assert any(isinstance(c.func,ast.Name) and c.func.id=='dismissible' for c in calls),node.name
        assert found==functions,(name,found)


def test_native_dialogs_have_explicit_parent_and_default_no():
    for name in ('chat_window.py','artifact_panel.py','chat_library_panel.py','document_qa_panel.py'):
        tree=ast.parse(Path(__file__).with_name(name).read_text(encoding='utf-8'))
        for call in ast.walk(tree):
            if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Attribute):continue
            if call.func.attr not in {'askyesno','askopenfilename','asksaveasfilename','askstring'}:continue
            kwargs={kw.arg:kw.value for kw in call.keywords}
            assert 'parent' in kwargs,(name,call.lineno)
            if call.func.attr=='askyesno':assert isinstance(kwargs.get('default'),ast.Constant) and kwargs['default'].value=='no'


def ui_function(name,namespace):
    tree=ast.parse(Path(__file__).with_name('chat_window.py').read_text(encoding='utf-8'))
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),'chat_window.py','exec'),namespace)
    return namespace[name]


def test_activity_is_bounded_and_optional_when_panel_is_closed():
    rows=deque(maxlen=100)
    record=ui_function('record_activity',dict(activity_lines=rows,activity_box=None))
    for n in range(150):record(str(n)+'x'*3000)
    assert len(rows)==100 and rows[0].startswith('50x') and all(len(row)<=2000 for row in rows)


def test_routine_logs_stay_in_activity_and_blocked_results_remain_visible():
    events=queue.Queue();activity=[];shown=[]
    for line in ('[timing] synthetic metadata','fetch_page synthetic request','[blocked] Synthetic refusal'):
        events.put(('log',line))
    fn=ui_function('poll',dict(events=events,queue=queue,busy=False,
        root=types.SimpleNamespace(after=lambda *args:None),record_activity=activity.append,
        show=lambda *args:shown.append(args),remove_pending=lambda:None,
        sync_attachment_chip=lambda:None))
    fn()
    assert len(activity)==3 and shown==[('Blocked','Synthetic refusal')]


def test_brand_assets_have_transparency_and_windows_icon_sizes():
    from PIL import Image
    folder=Path(__file__).parent/'assets'
    with Image.open(folder/'local-studio.png') as image:
        assert image.size==(256,256) and image.mode=='RGBA' and image.getextrema()[3]==(0,255)
    with Image.open(folder/'local-studio.ico') as image:
        assert image.ico.sizes()=={(n,n) for n in (16,20,24,32,40,48,64,128,256)}


if __name__=='__main__':
    assert __debug__
    tests=[value for key,value in sorted(globals().items()) if key.startswith('test_')]
    for test in tests:test();print('PASS',test.__name__)
    print(f'All {len(tests)} offline popup tests passed.')
