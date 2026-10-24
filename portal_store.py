"""Bounded local-preview records, separate from desktop chats and files."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import stat
import threading
import time
import uuid

ROOT=Path(__file__).resolve().parent/'portal_data'


def identifier(value):
    if not isinstance(value,str) or re.fullmatch('[0-9a-f]{32}',value) is None:raise ValueError('Invalid record ID')
    return value


def text(value,limit):
    if (not isinstance(value,str) or not value.strip() or len(value)>limit
            or any(not c.isprintable() and c not in '\n\r\t' for c in value)):
        raise ValueError('Text is empty, oversized or contains unsupported controls')
    return value


class Store:
    def __init__(self,root=ROOT,owner='local-preview-owner'):
        self.root=Path(root);self.owner=owner;self.lock=threading.RLock()
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS chats(id TEXT PRIMARY KEY,owner TEXT,title TEXT,created REAL)')
            db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,owner TEXT,chat TEXT REFERENCES chats(id),request TEXT,hash TEXT,model TEXT,message TEXT,status TEXT,answer TEXT,error TEXT,created REAL,UNIQUE(owner,request))')
            db.execute('CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY,owner TEXT,job TEXT REFERENCES jobs(id),kind TEXT,body TEXT,UNIQUE(owner,job,kind))')
            db.execute("UPDATE jobs SET status='interrupted',error='App restarted; no automatic retry' WHERE owner=? AND status IN ('queued','running')",(owner,))

    @contextmanager
    def db(self):
        with self.lock:
            self.root.mkdir(parents=True,exist_ok=True)
            path=self.root/'portal.sqlite3'
            for p in (self.root,*self.root.parents,path,Path(str(path)+'-journal'),Path(str(path)+'-wal'),Path(str(path)+'-shm')):
                if p.exists() or p.is_symlink():
                    info=p.lstat()
                    if p.is_symlink() or getattr(info,'st_file_attributes',0)&1024:raise ValueError('Portal paths cannot be links or junctions')
            if path.exists() and (not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size>8_000_000):raise ValueError('Portal database exceeds its bound')
            db=sqlite3.connect(path,timeout=2)
            try:
                db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA trusted_schema=OFF')
                db.execute('PRAGMA max_page_count=1950');db.execute('BEGIN IMMEDIATE')
                yield db;db.commit()
            except Exception:db.rollback();raise
            finally:db.close()

    def quota(self,db):
        used=db.execute('SELECT coalesce(sum(length(CAST(message AS BLOB))+length(CAST(answer AS BLOB))),0) FROM jobs').fetchone()[0]
        used+=db.execute('SELECT coalesce(sum(length(CAST(body AS BLOB))),0) FROM artifacts').fetchone()[0]
        if used>4_000_000:raise ValueError('Portal storage quota reached')

    def new_chat(self,title):
        title=text(title,80).strip();key=uuid.uuid4().hex
        with self.db() as db:
            if db.execute('SELECT count(*) FROM chats WHERE owner=?',(self.owner,)).fetchone()[0]>=20:raise ValueError('At most 20 web chats in this preview')
            db.execute('INSERT INTO chats VALUES(?,?,?,?)',(key,self.owner,title,time.time()))
        return key

    def require_chat(self,db,chat):
        if not db.execute('SELECT 1 FROM chats WHERE id=? AND owner=?',(identifier(chat),self.owner)).fetchone():raise ValueError('Record unavailable')

    def submit(self,chat,request,message,model):
        identifier(chat);identifier(request);message=text(message,4000)
        if len(message.encode('utf-8'))>5000:raise ValueError('Message exceeds 5000 UTF-8 bytes')
        digest=hashlib.sha256(json.dumps([chat,message,model],ensure_ascii=False).encode()).hexdigest()
        with self.db() as db:
            self.require_chat(db,chat)
            old=db.execute('SELECT id,hash FROM jobs WHERE owner=? AND request=?',(self.owner,request)).fetchone()
            if old:
                if old[1]!=digest:raise ValueError('Request ID was already used for different content')
                return old[0],False
            if db.execute('SELECT count(*) FROM jobs WHERE owner=?',(self.owner,)).fetchone()[0]>=96:raise ValueError('At most 96 requests in this preview')
            if db.execute("SELECT 1 FROM jobs WHERE owner=? AND chat=? AND status IN ('queued','running')",(self.owner,chat)).fetchone():raise ValueError('This chat already has a pending request')
            key=uuid.uuid4().hex
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)',(key,self.owner,chat,request,digest,model,message,'queued','','',time.time()))
            self.quota(db)
            return key,True

    def job(self,key):
        with self.db() as db:
            row=db.execute('SELECT chat,model,message,status,answer FROM jobs WHERE id=? AND owner=?',(identifier(key),self.owner)).fetchone()
            if row is None:raise ValueError('Record unavailable')
            return dict(zip(('chat','model','message','status','answer'),row))

    def update(self,key,status,answer='',error=''):
        if status not in ('running','completed','failed','cancelled'):raise ValueError('Invalid job state')
        if answer or status=='completed':text(answer,32000)
        if error:text(error,200)
        with self.db() as db:
            row=db.execute('SELECT status FROM jobs WHERE owner=? AND id=?',(self.owner,identifier(key))).fetchone()
            if row is None:raise ValueError('Record unavailable')
            if row[0] in ('completed','failed','cancelled','interrupted'):return False
            db.execute('UPDATE jobs SET status=?,answer=?,error=? WHERE owner=? AND id=?',(status,answer,error,self.owner,key))
            self.quota(db)
        return True

    def history(self,chat):
        with self.db() as db:
            self.require_chat(db,chat)
            rows=db.execute("SELECT message,answer FROM jobs WHERE owner=? AND chat=? AND status='completed' ORDER BY created DESC LIMIT 10",(self.owner,chat)).fetchall()
        return [{'role':role,'content':value} for pair in reversed(rows) for role,value in zip(('user','assistant'),pair)]

    def state(self,chat=None):
        with self.db() as db:
            chats=[dict(zip(('id','title'),r)) for r in db.execute('SELECT id,title FROM chats WHERE owner=? ORDER BY created DESC',(self.owner,))]
            chat=chat or (chats[0]['id'] if chats else None)
            if chat:self.require_chat(db,chat)
            jobs=[dict(zip(('id','message','status','answer','error','model'),r)) for r in db.execute('SELECT id,message,status,answer,error,model FROM jobs WHERE owner=? AND chat=? ORDER BY created',(self.owner,chat))]
            artifacts=[dict(zip(('id','kind'),r)) for r in db.execute('SELECT id,kind FROM artifacts WHERE owner=? ORDER BY rowid DESC',(self.owner,))]
        return dict(chats=chats,chat=chat,jobs=jobs,artifacts=artifacts)

    def keep(self,job,kind):
        if kind not in ('document','code'):raise ValueError('Only inert text/code Artifacts are supported')
        result=self.job(job)
        if result['status']!='completed':raise ValueError('Only a completed answer can become an Artifact')
        with self.db() as db:
            old=db.execute('SELECT id FROM artifacts WHERE owner=? AND job=? AND kind=?',(self.owner,job,kind)).fetchone()
            if old:return old[0]
            if db.execute('SELECT count(*) FROM artifacts WHERE owner=?',(self.owner,)).fetchone()[0]>=30:raise ValueError('At most 30 web Artifacts in this preview')
            key=uuid.uuid4().hex;db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?)',(key,self.owner,job,kind,result['answer']))
            self.quota(db);return key

    def artifact(self,key):
        with self.db() as db:
            row=db.execute('SELECT kind,body FROM artifacts WHERE id=? AND owner=?',(identifier(key),self.owner)).fetchone()
        if row is None:raise ValueError('Record unavailable')
        return dict(kind=row[0],body=row[1])
