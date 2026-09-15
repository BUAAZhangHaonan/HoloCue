"""One SQLite source of truth. Optimistic revisions reject stale or duplicated plan commits."""
from __future__ import annotations
import sqlite3,json,time,hashlib
from pathlib import Path
from uuid import uuid4
from .models import Session,UserMessage,Decision,SceneSpec
from .state import ConflictError,apply_decision

class Store:
    def __init__(self,path:Path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as c:
            c.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                request_id TEXT NOT NULL, fingerprint TEXT NOT NULL, epoch INTEGER NOT NULL,
                status TEXT NOT NULL, data TEXT NOT NULL, UNIQUE(session_id,request_id));
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL, timestamp REAL NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL);
            """)
    def connection(self):
        c=sqlite3.connect(self.path,timeout=10);c.row_factory=sqlite3.Row;return c
    def _read(self,c,sid):
        r=c.execute('SELECT data FROM sessions WHERE id=?',(sid,)).fetchone()
        if r is None:raise KeyError(sid)
        return Session.model_validate_json(r['data'])
    def _save(self,c,s):
        c.execute('INSERT OR REPLACE INTO sessions(id,data) VALUES(?,?)',(s.session_id,s.model_dump_json()))
    def _event(self,c,sid,kind,data):
        c.execute('INSERT INTO events(session_id,timestamp,kind,data) VALUES(?,?,?,?)',
                  (sid,time.time(),kind,json.dumps(data,ensure_ascii=False)))
    def create(self,scene_id,backend_mode):
        s=Session(session_id=uuid4().hex,scene_id=scene_id,backend_mode=backend_mode)
        with self.connection() as c:self._save(c,s);self._event(c,s.session_id,'created',s.model_dump())
        return s
    def get(self,sid):
        with self.connection() as c:return self._read(c,sid)
    def begin(self,sid,msg:UserMessage):
        fingerprint=hashlib.sha256(json.dumps({'text':msg.text,'image':msg.image_base64,'mime':msg.image_mime},sort_keys=True).encode()).hexdigest()
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            old=c.execute('SELECT * FROM jobs WHERE session_id=? AND request_id=?',(sid,msg.request_id)).fetchone()
            if old:
                if old['fingerprint']!=fingerprint:raise ConflictError('request_id reused with different content')
                return dict(old),self._read(c,sid),False
            s=self._read(c,sid)
            if s.revision!=msg.expected_revision:raise ConflictError('stale expected_revision')
            # Invalidate old display motion immediately, independently of model response time.
            s.epoch+=1;s.revision+=1;s.execution='planning';s.last_error=None
            s.history.append({'role':'user','content':msg.text})
            self._save(c,s)
            c.execute("UPDATE jobs SET status='superseded' WHERE session_id=? AND status='planning'",(sid,))
            job={'id':uuid4().hex,'session_id':sid,'request_id':msg.request_id,'fingerprint':fingerprint,
                 'epoch':s.epoch,'status':'planning','data':json.dumps({'started_at':time.time(),'text':msg.text},ensure_ascii=False)}
            c.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',tuple(job.values()))
            self._event(c,sid,'turn_started',{'job_id':job['id'],'epoch':s.epoch,'text':msg.text})
        return job,s,True
    def commit(self,job_id,d:Decision,scene:SceneSpec,trace:dict):
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            r=c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            if r is None:raise KeyError(job_id)
            s=self._read(c,r['session_id'])
            if r['status']!='planning' or s.epoch!=r['epoch']:return None
            new=apply_decision(s,d,scene)
            self._save(c,new)
            info=json.loads(r['data']);info.update(trace);info.update({'finished_at':time.time(),'decision':d.model_dump(),'revision':new.revision})
            c.execute("UPDATE jobs SET status='done',data=? WHERE id=?",(json.dumps(info,ensure_ascii=False),job_id))
            self._event(c,s.session_id,'plan_committed',info)
            return new
    def fail(self,job_id,error:str,trace:dict|None=None):
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            r=c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            if r is None:return
            s=self._read(c,r['session_id'])
            if r['status']!='planning' or s.epoch!=r['epoch']:return
            s.execution='error';s.last_error=error;s.revision+=1
            self._save(c,s)
            info=json.loads(r['data']);info.update(trace or {});info.update({'error':error,'finished_at':time.time()})
            c.execute("UPDATE jobs SET status='error',data=? WHERE id=?",(json.dumps(info),job_id))
            self._event(c,s.session_id,'turn_error',info)
    def manual(self,sid,revision,d,scene):
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            s=self._read(c,sid)
            if s.revision!=revision:raise ConflictError('stale expected_revision')
            s.epoch+=1
            new=apply_decision(s,d,scene)
            self._save(c,new)
            c.execute("UPDATE jobs SET status='superseded' WHERE session_id=? AND status='planning'",(sid,))
            self._event(c,sid,'user_confirmation',{'operation':d.operation,'revision':new.revision})
            return new
    def job(self,jid):
        with self.connection() as c:
            r=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
            if r is None:raise KeyError(jid)
            x=dict(r);x['data']=json.loads(x['data']);x.pop('fingerprint');return x
    def events(self,sid):
        self.get(sid)
        with self.connection() as c:
            return [{'seq':r['seq'],'timestamp':r['timestamp'],'kind':r['kind'],'data':json.loads(r['data'])}
                    for r in c.execute('SELECT * FROM events WHERE session_id=? ORDER BY seq',(sid,))]
    def recover(self):
        """Restart is visible; persisted actions are paused, never silently replayed."""
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            for r in list(c.execute('SELECT data FROM sessions')):
                s=Session.model_validate_json(r['data'])
                if s.execution in ('running','planning'):
                    s.execution='paused';s.epoch+=1;s.revision+=1
                    s.assistant_message='服务已重启，任务已保留。请确认继续。'
                    self._save(c,s)
            c.execute("UPDATE jobs SET status='interrupted' WHERE status='planning'")
