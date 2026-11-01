from .local_state import open_control
from .local_state import private_directory, private_database, write_private
import contextlib
import datetime
from . import file_lock as fcntl
import json
import os
import sqlite3
from pathlib import Path
from .security import WorkflowError, canonical
from .local_state import guard_workspace, guard_control, validate_open_control


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class Store:
    def __init__(self, workspace):
        self.root = guard_workspace(workspace)
        private_directory(self.root)
        guard_workspace(self.root, canonical_alias=False)
        self.db = private_database(self.root, 'jobs.sqlite3', timeout=10)
        self._closed = False
        self.db.row_factory = sqlite3.Row
        try:
            self.db.execute('PRAGMA foreign_keys=ON')
            self.db.executescript('''
              CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, payload TEXT NOT NULL, created TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS stages(job TEXT, name TEXT, status TEXT NOT NULL, manifest TEXT,
                error TEXT, updated TEXT, PRIMARY KEY(job,name), FOREIGN KEY(job) REFERENCES jobs(id));
              CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, job TEXT, stage TEXT,
                event TEXT NOT NULL, detail TEXT NOT NULL, created TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY, job TEXT NOT NULL, payload TEXT NOT NULL,
                status TEXT NOT NULL, cap_microusd INTEGER, approver TEXT, approved_until TEXT, receipt TEXT,
                FOREIGN KEY(job) REFERENCES jobs(id));
              CREATE TABLE IF NOT EXISTS costs(id INTEGER PRIMARY KEY, request TEXT UNIQUE NOT NULL,
                simulated_microusd INTEGER NOT NULL, actual_microusd INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL,
                FOREIGN KEY(request) REFERENCES requests(id));
            ''')
            self.db.commit()
        except BaseException:
            self.close()
            raise

    def close(self):
        if not self._closed:
            self.db.close()
            self._closed = True

    def __enter__(self):
        if self._closed:raise WorkflowError('STORE_CLOSED')
        return self

    def __exit__(self,*args):
        self.close()

    @contextlib.contextmanager
    def lock(self,blocking=False):
        guard_workspace(self.root, canonical_alias=False)
        path=guard_control(self.root, '.workflow.lock')
        try:
            fd=open_control(path,os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0)|getattr(os,'O_CLOEXEC',0),0o600)
        except OSError:
            raise WorkflowError('LOCAL_STATE_UNSAFE: workflow lock unavailable; no external path was followed') from None
        try:
            validate_open_control(fd,private=True)
        except Exception:
            os.close(fd)
            raise
        with os.fdopen(fd,'a') as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            except BlockingIOError:
                raise WorkflowError('Another workflow owns this workspace; retry after it finishes')
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def event(self, job, stage, event, detail=None):
        guard_workspace(self.root, canonical_alias=False)
        self.db.execute('INSERT INTO events(job,stage,event,detail,created) VALUES(?,?,?,?,?)',
                        (job, stage, event, canonical(detail or {}), now()))
        self.db.commit()

    def stage(self, job, name):
        row = self.db.execute('SELECT * FROM stages WHERE job=? AND name=?', (job, name)).fetchone()
        return dict(row) if row else None

    def set_stage(self, job, name, status, manifest=None, error=None):
        guard_workspace(self.root, canonical_alias=False)
        self.db.execute('INSERT INTO stages VALUES(?,?,?,?,?,?) ON CONFLICT(job,name) DO UPDATE SET '
                        'status=excluded.status,manifest=excluded.manifest,error=excluded.error,updated=excluded.updated',
                        (job, name, status, canonical(manifest or {}), error, now()))
        self.db.commit()

    def status(self, job):
        return {'job': job, 'stages': [dict(x) for x in self.db.execute('SELECT * FROM stages WHERE job=? ORDER BY rowid', (job,))],
                'requests': [dict(x) for x in self.db.execute('SELECT id,status,cap_microusd,approver,approved_until FROM requests WHERE job=?', (job,))],
                'costs': [dict(x) for x in self.db.execute('SELECT c.* FROM costs c JOIN requests r ON r.id=c.request WHERE r.job=?', (job,))]}
