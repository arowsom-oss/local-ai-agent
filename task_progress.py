"""RAM-only task evidence. Model plans never grant permission or mark completion."""
from dataclasses import dataclass
from collections import deque
import re
import threading

LABELS={
    'add':'Calculate sum','multiply':'Calculate product','read_file':'Read sandbox file',
    'fetch_page':'Fetch page','browser_open':'Open browser page','browser_read':'Read browser page',
    'browser_click':'Open recorded link','browser_search':'Submit search','propose_plan':'Browser plan',
    'browser_web_search':'Find research sources',
    'desktop_start':'Open practice app','desktop_read':'Read practice app','desktop_type':'Change practice draft',
    'desktop_click':'Use practice control','notepad_start':'Open scratch Notepad','notepad_read':'Read scratch Notepad',
    'notepad_replace':'Edit scratch Notepad','generate_image':'Generate image','generate_video':'Generate video',
    'create_artifact':'Create Artifact','revise_artifact':'Revise Artifact','read_artifact':'Read Artifact',
    'list_artifacts':'List Artifacts','document_list':'List Documents','document_read':'Read saved document',
    'document_save':'Save document version','document_edit':'Edit saved document',
    'document_append_requested':'Append requested text','outline_task':'Proposed task steps'}
DOCUMENT_WRITES={'document_save','document_edit','document_append_requested'}
READS={'read_file','fetch_page','browser_read','desktop_read','notepad_read','read_artifact','list_artifacts','document_list','document_read'}
READS.add('browser_web_search')
VERIFIED={'notepad_replace':'Notepad edit verified by exact read-back.',
          'desktop_type':'Practice action verified.','desktop_click':'Practice action verified.',
          'document_save':'Saved and verified Document ', 'document_edit':'Saved and verified Document ',
          'document_append_requested':'Saved and verified Document ',
          'create_artifact':'Artifact ','revise_artifact':'Artifact '}
APPROVALS={'workspace_access':'Workspace read permission','document_save_exact':'Exact document save',
    'notepad_action':'Exact Notepad edit','notepad_start':'Scratch Notepad launch','desktop_action':'Exact practice change',
    'desktop_start':'Practice launch','new_site':'Website permission','outbound_request':'Exact outbound address',
    'browser_search':'Search submission','browser_click':'Recorded link','read_file':'Sandbox file read',
    'generation':'Local generation','plan':'Browser plan approval','plan_changed':'Browser plan change'}
APPROVALS['browser_web_search']='Exact web search'


def valid_steps(steps):
    if not isinstance(steps,list) or not 1<=len(steps)<=8 or any(
            not isinstance(s,str) or not 1<=len(s)<=120 or not s.isprintable() for s in steps):
        return 'use 1 to 8 printable proposed steps, each 1 to 120 characters'
    return ''


def outline_task(steps: list) -> str:
    """Display proposed steps in the task panel; this grants no permissions or completion status.

    Args:
        steps: One to eight short printable descriptions of intended steps. These remain unverified proposals.
    """
    return 'Error: '+valid_steps(steps) if valid_steps(steps) else 'Proposed steps recorded for display only. Each tool retains its normal checks and approvals.'


@dataclass(frozen=True)
class Row:
    label: str
    state: str


@dataclass(frozen=True)
class Snapshot:
    serial: int
    phase: str
    rows: tuple
    proposed: tuple
    verified: int
    observations: int
    resumable: bool
    request: str


class TaskProgress:
    def __init__(self):
        self.lock=threading.RLock();self.serial=0;self.reset()

    def reset(self):
        with self.lock:
            self.serial+=1;self.phase='Ready';self.request='';self.rows=deque(maxlen=100)
            self.proposed=();self.verified=self.observations=0;self.resumable=False;self.finished=False
            return self.serial

    def begin(self,request,resume=False):
        if resume:
            with self.lock:
                if not self.resumable:raise ValueError('no paused task to resume')
                self.serial+=1;self.phase='Working';self.finished=False;self.resumable=False
                self.rows.append(Row('Resume checkpoint','Fresh reads required'))
                return self.serial
        serial=self.reset()
        with self.lock:
            self.request=str(request) if len(str(request))<=4000 else '';self.phase='Working'
        return serial

    def event(self,serial,kind,tool='',status='',steps=None):
        with self.lock:
            if serial!=self.serial or self.finished:return
            if kind=='plan':
                if not valid_steps(steps):self.proposed=tuple(steps)
            elif kind=='request':
                self.phase='Checking request';self.rows.append(Row(LABELS.get(tool,'Unknown tool'),'Requested'))
            elif kind=='approval':
                self.phase='Awaiting approval';self.rows.append(Row(APPROVALS.get(tool,'Tool approval'),'Awaiting approval'))
            elif kind=='decision':
                self.phase='Working';self.rows.append(Row(APPROVALS.get(tool,'Tool approval'),'Approved' if status=='approved' else 'Denied'))
            elif kind=='result':
                self.rows.append(Row(LABELS.get(tool,'Unknown tool'),status))
                if status=='Verified':self.verified+=1
                if status=='Observed':self.observations+=1
                self.phase='Working'
            elif kind=='finish':
                self.phase=status if status in {'Reply ready','Paused','Stopped','Failed'} else 'Failed'
                self.resumable=self.phase in {'Paused','Stopped','Failed'} and bool(self.request)
                self.finished=True

    def stop(self):
        with self.lock:
            if not self.finished:
                self.phase='Stopped';self.resumable=bool(self.request);self.finished=True

    def snapshot(self):
        with self.lock:return Snapshot(self.serial,self.phase,tuple(self.rows),self.proposed,self.verified,
            self.observations,self.resumable,self.request)

    def resume_request(self):
        with self.lock:
            if not self.resumable:raise ValueError('no paused task to resume')
            return 'Continue my previous request after checking the current state again. Do not reuse old approvals or target numbers. Previous request:\n'+self.request


class TurnEvidence:
    """Core-owned event emitter and fresh-read gate. Never consumes model final text as evidence."""
    def __init__(self,sink=None,resume=False):
        self.sink=sink;self.resume=resume;self.fresh=set();self.artifacts=set();self.documents=set()
        self.refused=set();self.active={};self.outcome='Failed'

    @property
    def had_refusal(self):return bool(self.refused)

    def emit(self,kind,tool='',status='',steps=None):
        if self.sink is not None:
            try:self.sink(kind=kind,tool=tool,status=status,steps=steps)
            except Exception:pass # Display failures cannot grant permission or repeat an action.

    def request(self,name,args):
        self.active[name]={k:args[k] for k in ('artifact','document') if isinstance(args,dict) and type(args.get(k)) is int}
        self.emit('request',name)

    def problem(self,name,args):
        if name=='document_append_requested' and args.get('document') not in self.documents:
            return 'bound append requires document_read of the latest target in this turn'
        if not self.resume:return ''
        reads={'browser_click':'browser_read','browser_search':'browser_read','notepad_replace':'notepad_read',
               'desktop_type':'desktop_read','desktop_click':'desktop_read'}
        needed=reads.get(name)
        if needed and needed not in self.fresh:return 'resume requires a fresh '+needed+' before this action'
        if name in {'revise_artifact','document_save'} and args.get('artifact') not in self.artifacts:
            return 'resume requires reading the current Artifact before revising or saving it'
        if name in DOCUMENT_WRITES and args.get('document')!=0 and args.get('document') not in self.documents:
            return 'resume requires document_read of the current saved document before this save'
        return ''

    def result(self,name,text):
        text=str(text)
        if text.startswith('Error:'):
            if 'queued action not run' not in text:self.refused.add(name)
            status=('Unconfirmed' if name in DOCUMENT_WRITES and ('outcome uncertain' in text or 'outcome unconfirmed' in text) else
                    'Deferred' if 'queued action not run' in text else 'Refused')
        elif name in VERIFIED and text.startswith(VERIFIED[name]):status='Verified'
        elif name in READS:status='Observed'
        else:status='Returned' # A successful status is not independent verification of an entire task.
        self.emit('result',name,status)
        if name in {'notepad_replace','notepad_start'}:self.fresh.discard('notepad_read')
        if name in {'desktop_type','desktop_click','desktop_start'}:self.fresh.discard('desktop_read')
        if name in {'browser_open','browser_click','browser_search','browser_web_search'}:self.fresh.discard('browser_read')
        if text.startswith('Error:'):return
        if name=='browser_web_search':self.fresh.add('browser_read')
        self.refused.discard(name)
        args=self.active.get(name,{})
        self.fresh.add(name)
        if name=='read_artifact':self.artifacts.add(args.get('artifact'))
        if name=='create_artifact':
            match=re.match(r'Artifact (\d+), revision 1 created',text)
            if match:self.artifacts.add(int(match[1]))
        if name=='document_read':
            self.documents.add(args.get('document'))
            match=re.search(r'^Document \d+, saved version \d+; latest is \d+\. Artifact (\d+), revision 1 contains this draft\.',text,re.M)
            if match:self.artifacts.add(int(match[1]))
        # A mutation consumes its observation; the next action must observe again.
        if name in {'notepad_replace','desktop_type','desktop_click'}:
            self.fresh.discard('notepad_read' if name=='notepad_replace' else 'desktop_read')
        if name in {'browser_open','browser_click','browser_search'}:self.fresh.discard('browser_read')
        if name in DOCUMENT_WRITES:self.documents.discard(args.get('document'))
