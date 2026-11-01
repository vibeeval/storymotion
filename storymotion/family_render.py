"""Account-bound local family attempts. No UI, provider dispatch or auto-resume."""
import hashlib
import contextlib
import math
import os
import re
import sqlite3
import threading
import time
import uuid

from .account_packs import load_pack
from .engine import Engine, probe
from .family_jobs import decode, read_owned
from .local_state import guard_control, guard_private, guard_workspace, private_directory, validate_open_control, write_private
from .runtime import require_engine
from .render_slot import WorkerStart,join_owned,require_settled_start
from .security import WorkflowError, canonical, digest, scan_bytes
from .template_families import fields, validate_brief

HEX24 = re.compile(r'[a-f0-9]{24}')
HEX32 = re.compile(r'[a-f0-9]{32}')
HEX64 = re.compile(r'[a-f0-9]{64}')
ACTIVE = ('queued', 'running', 'cancel_requested')
RETRYABLE = ('failed', 'cancelled', 'blocked_runtime', 'invalidated', 'failed_before_start')
MEDIA = ('render-1080.mp4', 'render-mobile.mp4')
MAX_MEDIA = 128 * 1024 * 1024
PROFILE = 'silent-1080x1920-540x960-30fps-v1'


def fail(code):
    raise WorkflowError('FAMILY_RENDER_' + code)


def identifier(value, pattern):
    if not isinstance(value, str) or not pattern.fullmatch(value):fail('IDENTITY_INVALID')
    return value


class FamilyRender:
    def __init__(self, dashboard):
        self.d = dashboard
        self.lock = threading.RLock()
        self.active = {}
        self.epoch = uuid.uuid4().hex
        self.closing = False
        with self.d.connection() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS family_render_attempts(
                id TEXT PRIMARY KEY,account TEXT NOT NULL,prepare_job TEXT NOT NULL,engine TEXT NOT NULL,
                generation INTEGER NOT NULL,request_key TEXT NOT NULL,request_hash TEXT NOT NULL,
                owner TEXT NOT NULL,binding TEXT NOT NULL,preparation_revision TEXT NOT NULL,
                execution_binding TEXT NOT NULL,status TEXT NOT NULL,error TEXT,manifest TEXT,
                previous_attempt TEXT,created REAL NOT NULL,updated REAL NOT NULL,
                UNIQUE(account,prepare_job,engine,generation),UNIQUE(account,prepare_job,engine,request_key))''')

    def identity(self, account, job):
        load_pack(account)
        identifier(job, HEX24)

    def snapshot(self, account, job, *, current=True):
        self.identity(account, job)
        result = self.d.template_studio.history.execution_snapshot(account, job, require_current=current)
        proof = result['proof']
        result['execution_binding'] = digest({'preparation_revision':result['preparation_revision'],
            'proof':proof,'output_profile':PROFILE,'silent':True})
        return result

    def revalidate(self, snapshot):
        self.d.assert_runtime_current()
        payload = snapshot['payload'];brief = payload['brief'];account = snapshot['proof']['account']
        self.d.clean(brief)
        if scan_bytes(snapshot['raw']):fail('INPUT_UNSAFE')
        if brief.get('audio') is not None or brief.get('alignment') != 'provisional_silent':fail('SILENT_ONLY')
        validate_brief(brief, payload['profile'])
        context = brief.get('production_context')
        if context is not None:self.d.llm.contexts.assert_current(account, context)
        subject = brief.get('template_subject')
        if subject is not None and self.d.taxonomy.state(account)['planning_context'] != subject:
            fail('PLANNING_CHANGED')

    def latest(self, db, account, job, engine):
        return db.execute('SELECT * FROM family_render_attempts WHERE account=? AND prepare_job=? AND engine=? ORDER BY generation DESC LIMIT 1', (account,job,engine)).fetchone()

    @contextlib.contextmanager
    def read_db(self):
        guard_workspace(self.d.workspace,canonical_alias=False)
        path = guard_private(self.d.workspace,'jobs.sqlite3')
        if not path.is_file():fail('STORE_UNAVAILABLE')
        try:
            with path.open('rb') as stream:header=stream.read(100)
            if len(header)!=100 or header[:16]!=b'SQLite format 3\x00' or header[18:20]!=b'\x01\x01':fail('STORE_UNAVAILABLE')
            if any(guard_private(self.d.workspace,'jobs.sqlite3'+suffix).exists() for suffix in ('-wal','-shm')):fail('STORE_UNAVAILABLE')
            with contextlib.closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=1)) as db:
                db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON');yield db
        except (OSError,sqlite3.Error):fail('STORE_UNAVAILABLE')

    def row(self, account, job, attempt=None):
        self.identity(account, job)
        if attempt is not None:identifier(attempt, HEX32)
        with self.read_db() as db:
            if attempt is None:
                value = db.execute('SELECT * FROM family_render_attempts WHERE account=? AND prepare_job=? ORDER BY generation DESC LIMIT 1', (account,job)).fetchone()
            else:
                value = db.execute('SELECT * FROM family_render_attempts WHERE account=? AND prepare_job=? AND id=?', (account,job,attempt)).fetchone()
        if attempt is not None and value is None:fail('ATTEMPT_UNAVAILABLE')
        if value:
            value=dict(value)
            if (value['engine'] not in ('hyperframes','remotion') or type(value['generation']) is not int or value['generation']<1
                    or value['status'] not in ACTIVE+RETRYABLE+('complete',)
                    or value['error'] not in (None,'FAMILY_RENDER_FAILED','FAMILY_RENDER_THREAD_START_FAILED','FAMILY_RENDER_THREAD_START_UNCONFIRMED','FAMILY_RENDER_RUNTIME_UNAVAILABLE')):fail('RECORD_INVALID')
            identifier(value['id'],HEX32);identifier(value['owner'],HEX32);identifier(value['request_key'],HEX32)
            identifier(value['request_hash'],HEX64)
            if value['previous_attempt'] is not None:identifier(value['previous_attempt'],HEX32)
        return value if value else None

    def verify_binding(self, row, snapshot):
        if (decode(row['binding'])!=snapshot['proof'] or row['engine']!=snapshot['proof']['engine']
                or row['preparation_revision']!=snapshot['preparation_revision']
                or row['execution_binding']!=snapshot['execution_binding']):fail('BINDING_CHANGED')

    def attempt_binding(self, row):
        keys=('id','account','prepare_job','engine','generation','request_key','request_hash','owner',
              'preparation_revision','execution_binding','previous_attempt')
        return {**{key:row[key] for key in keys},'preparation':decode(row['binding'])}

    def directory(self, attempt):
        identifier(attempt, HEX32)
        return guard_private(self.d.workspace, 'family-executions/' + attempt, 'dir')

    def owned(self, row):
        with self.lock:
            owned=self.active.get(row['id'])
            return row['owner']==self.epoch and owned is not None and owned[2]==row['generation']

    def public(self, row, source_current):
        status = row['status']
        if status in ACTIVE and not self.owned(row):status = 'interrupted_unconfirmed'
        value = {'ref':{'kind':'family_render','account':row['account'],'prepare_job':row['prepare_job'],
            'id':row['id'],'generation':row['generation']},'account':row['account'],'prepare_job':row['prepare_job'],
            'attempt':row['id'],'engine':row['engine'],'generation':row['generation'],'status':status,
            'previous_attempt':row['previous_attempt'],'request_key':row['request_key'],
            'preparation_revision':row['preparation_revision'],'execution_binding':row['execution_binding'],
            'source_current':source_current,'error':row['error'],'files':[],
            'actual_render':False,'provider_calls':0,'publication_ready':False,'output_profile':PROFILE}
        if status == 'complete':
            try:
                manifest = self.verified_outputs(row)
                for name, sha in manifest.items():
                    token = digest({'attempt':row['id'],'generation':row['generation'],'binding':row['execution_binding'],'files':manifest,'name':name})
                    value['files'].append({'name':name,'sha256':sha,'download_url':'/family-render-files/'+row['account']+'/'+row['prepare_job']+'/'+row['id']+'/'+token})
                value['actual_render'] = True
            except (WorkflowError, OSError, ValueError, KeyError, TypeError):
                value.update(status='invalidated',error='FAMILY_RENDER_OUTPUT_CHANGED',files=[])
        self.d.clean(value);self.d.template_studio.history.clean(value)
        return value

    def state(self, account, job, attempt=None):
        with self.d.revision_lock:
            return self._state(account, job, attempt)

    def _state(self, account, job, attempt=None):
        snapshot = self.snapshot(account, job, current=False)
        row = self.row(account, job, attempt)
        if row:self.verify_binding(row,snapshot)
        value = self.public(row, snapshot['source_current']) if row else {'account':account,'prepare_job':job,
            'engine':snapshot['proof']['engine'],'status':'not_started','generation':0,'files':[],
            'actual_render':False,'provider_calls':0,'publication_ready':False}
        return {**value,'preparation_revision':snapshot['preparation_revision'],
                'execution_binding':snapshot['execution_binding'],'source_current':snapshot['source_current']}

    def action(self, account, job, action, data):
        self.identity(account, job);self.d.clean(data)
        if action == 'cancel':
            fields(data, {'engine','attempt','generation'})
            return self.cancel(account, job, data)
        if action not in ('start','retry'):fail('ACTION_INVALID')
        required = {'engine','preparation_revision','execution_binding','request_key','expected_generation','ack_local_render'}
        fields(data, required | ({'previous_attempt'} if action == 'retry' else set()))
        if data['engine'] not in ('hyperframes','remotion') or data['ack_local_render'] is not True:fail('EXPLICIT_LOCAL_APPROVAL_REQUIRED')
        for name in ('preparation_revision','execution_binding'):identifier(data[name], HEX64)
        identifier(data['request_key'], HEX32)
        generation = data['expected_generation']
        if type(generation) is not int or not 0 <= generation < 9007199254740991:fail('GENERATION_INVALID')
        if action == 'retry':identifier(data['previous_attempt'], HEX32)
        request_hash = digest({'action':action,'data':data})
        with self.d.revision_lock,self.d.renders.lock,self.lock:
            if self.closing:fail('CLOSING')
            # Replays are observations, never fresh dispatch authorization.
            with self.d.connection() as db:
                replay = db.execute('SELECT * FROM family_render_attempts WHERE account=? AND prepare_job=? AND engine=? AND request_key=?', (account,job,data['engine'],data['request_key'])).fetchone()
            if replay:
                if replay['request_hash'] != request_hash:fail('REQUEST_KEY_REBOUND')
                return self.state(account, job, replay['id'])
            snapshot = self.snapshot(account, job)
            if snapshot['proof']['engine'] != data['engine']:fail('ENGINE_BINDING_CHANGED')
            if any(snapshot[k] != data[k] for k in ('preparation_revision','execution_binding')):fail('BINDING_CHANGED')
            self.revalidate(snapshot)
            if self.d.renders.active:fail('WORKER_BUSY')
            slot = self.d.render_slot.claim(('family',account,job,data['engine']))
            if slot is None:fail('WORKER_BUSY')
            attempt = uuid.uuid4().hex;cancel = threading.Event();owned = None
            try:
                with self.d.connection() as db:
                    db.execute('BEGIN IMMEDIATE')
                    prior = self.latest(db, account, job, data['engine'])
                    if action == 'start':
                        if prior is not None or generation != 0:fail('EXPLICIT_RETRY_REQUIRED')
                    else:
                        if prior is None or prior['id'] != data['previous_attempt'] or prior['generation'] != generation:fail('STALE_ATTEMPT')
                        self.verify_binding(prior,snapshot)
                        interrupted = prior['status'] in ACTIVE and not self.owned(prior)
                        invalidated = False
                        if prior['status'] == 'complete':
                            try:self.verified_outputs(dict(prior))
                            except (WorkflowError,OSError,ValueError,KeyError,TypeError):invalidated=True
                        if not interrupted and not invalidated and prior['status'] not in RETRYABLE:fail('NOT_RETRYABLE')
                        if prior['id'] in self.active:fail('WORKER_BUSY')
                    now = time.time()
                    db.execute('INSERT INTO family_render_attempts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (attempt,account,job,data['engine'],generation+1,data['request_key'],request_hash,self.epoch,
                         canonical(snapshot['proof']),snapshot['preparation_revision'],snapshot['execution_binding'],
                         'queued',None,'{}',prior['id'] if prior else None,now,now))
                snapshot={**snapshot,'attempt_binding':self.attempt_binding(self.row(account,job,attempt))}
                entry = WorkerStart(self.work,(account,job,attempt,generation+1,cancel,snapshot,slot))
                thread = threading.Thread(target=entry.run,daemon=False)
                owned = (cancel,thread,generation+1,slot)
                self.active[attempt] = owned
                try:thread.start()
                except BaseException:
                    thread._storymotion_start_unconfirmed=True
                    uncertain=not entry.abort_before_entry()
                    try:
                        if uncertain:
                            if self.active.get(attempt) is owned:
                                with self.d.connection() as db:db.execute("UPDATE family_render_attempts SET error=?,updated=? WHERE account=? AND prepare_job=? AND id=? AND generation=? AND owner=? AND status IN ('queued','running','cancel_requested') AND generation=(SELECT MAX(b.generation) FROM family_render_attempts b WHERE b.account=family_render_attempts.account AND b.prepare_job=family_render_attempts.prepare_job AND b.engine=family_render_attempts.engine)",
                                    ('FAMILY_RENDER_THREAD_START_UNCONFIRMED',time.time(),account,job,attempt,generation+1,self.epoch))
                        else:self.finish(account,job,attempt,generation+1,'failed_before_start','FAMILY_RENDER_THREAD_START_FAILED')
                    except Exception as error:
                        try:self.d.local_log.warning('LOCAL_WRITE_FAILED',error)
                        except Exception:pass
                    finally:
                        if not uncertain and self.active.get(attempt) is owned:self.active.pop(attempt,None)
                    raise
            except BaseException:
                if owned is None or self.active.get(attempt) is not owned:self.d.render_slot.release(slot)
                raise
        return self.state(account, job, attempt)

    def transition(self, account, job, attempt, generation, old, new, error=None, manifest=None):
        with self.d.connection() as db:
            changed = db.execute('UPDATE family_render_attempts SET status=?,error=?,manifest=?,updated=? WHERE account=? AND prepare_job=? AND id=? AND generation=? AND owner=? AND generation=(SELECT MAX(b.generation) FROM family_render_attempts b WHERE b.account=family_render_attempts.account AND b.prepare_job=family_render_attempts.prepare_job AND b.engine=family_render_attempts.engine) AND status IN ('+','.join('?' for _ in old)+')',
                (new,error,canonical(manifest or {}),time.time(),account,job,attempt,generation,self.epoch,*old)).rowcount
        return bool(changed)

    def finish(self, account, job, attempt, generation, status, error=None, manifest=None):
        with self.lock:
            row = self.row(account,job,attempt)
            owned=self.active.get(attempt)
            if row['status'] == 'cancel_requested' or owned is not None and owned[2]==generation and owned[0].is_set():
                status,error,manifest = 'cancelled',None,None
            return self.transition(account,job,attempt,generation,ACTIVE,status,error,manifest)

    def cancel(self, account, job, data):
        identifier(data['attempt'], HEX32)
        if type(data['generation']) is not int or data['generation'] < 1:fail('GENERATION_INVALID')
        with self.lock:
            row = self.row(account,job,data['attempt'])
            if row['engine'] != data['engine'] or row['generation'] != data['generation']:fail('STALE_ATTEMPT')
            with self.d.connection() as db:latest = self.latest(db,account,job,data['engine'])
            if latest['id'] != row['id']:fail('STALE_ATTEMPT')
            if row['owner'] == self.epoch and row['status'] in ACTIVE:
                self.transition(account,job,row['id'],row['generation'],('queued','running'),'cancel_requested')
                owned = self.active.get(row['id'])
                if owned is not None and owned[2] == row['generation']:owned[0].set()
        return self.state(account,job,row['id'])

    def work(self, account, job, attempt, generation, cancel, snapshot, slot):
        try:
            if cancel.is_set():return self.finish(account,job,attempt,generation,'cancelled')
            try:require_engine(snapshot['proof']['engine'])
            except WorkflowError:return self.finish(account,job,attempt,generation,'blocked_runtime','FAMILY_RENDER_RUNTIME_UNAVAILABLE')
            if not self.transition(account,job,attempt,generation,('queued',),'running'):
                return self.finish(account,job,attempt,generation,'cancelled')
            with self.d.revision_lock:
                fresh = self.snapshot(account,job)
                if fresh['proof'] != snapshot['proof']:fail('BINDING_CHANGED')
                if self.attempt_binding(self.row(account,job,attempt))!=snapshot['attempt_binding']:fail('ATTEMPT_CHANGED')
                self.revalidate(fresh)
                if cancel.is_set():return self.finish(account,job,attempt,generation,'cancelled')
                parent = guard_private(self.d.workspace,'family-executions','dir');private_directory(parent)
                directory = self.directory(attempt);directory.mkdir(mode=0o700)
                source = guard_private(directory,'input.json')
                from .local_state import open_control
                fd = open_control(source,os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,'O_NOFOLLOW',0),0o600)
                with os.fdopen(fd,'wb') as stream:
                    validate_open_control(stream.fileno(),private=True);stream.write(snapshot['raw']);stream.flush();os.fsync(stream.fileno())
            manifest = self.execute(attempt,snapshot,cancel)
            self.finish(account,job,attempt,generation,'complete',manifest=manifest)
        except Exception:
            self.finish(account,job,attempt,generation,'cancelled' if cancel.is_set() else 'failed',None if cancel.is_set() else 'FAMILY_RENDER_FAILED')
        finally:
            with self.lock:
                owned = self.active.get(attempt)
                if owned is not None and owned[2:] == (generation,slot):self.active.pop(attempt,None)
            self.d.render_slot.release(slot)

    def execute(self, attempt, snapshot, cancel):
        if snapshot['attempt_binding']['id']!=attempt or snapshot['attempt_binding']['preparation']!=snapshot['proof']:fail('ATTEMPT_CHANGED')
        directory = self.directory(attempt)
        source = guard_private(directory,'input.json')
        if hashlib.sha256(read_owned(directory,'input.json',1024*1024)).hexdigest() != snapshot['proof']['source_sha256']:fail('INPUT_CHANGED')
        work = guard_private(directory,'work','dir')
        with Engine(work,self.d.hf) as engine:
            job = engine.create(source,render_engine=snapshot['proof']['engine'])['job']
            if job != snapshot['proof']['prepare_job']:fail('ENGINE_IDENTITY_CHANGED')
            engine.run(job,'mobile',cancel_event=cancel)
            with engine.store.lock():
                if digest(engine.payload(job)) != snapshot['proof']['payload_sha256']:fail('ENGINE_IDENTITY_CHANGED')
                manifest = {}
                for stage, names in (('render',('render-1080.mp4','render-engine.json')),('mobile',('render-mobile.mp4',))):
                    row = engine.store.stage(job,stage)
                    if not row or row['status'] != 'complete':fail('STAGES_INCOMPLETE')
                    values = decode(row['manifest'])
                    if set(values) != set(names):fail('OUTPUT_CHANGED')
                    for name in names:
                        raw = read_owned(engine.directory(job),name,MAX_MEDIA if name in MEDIA else 1024*1024)
                        if hashlib.sha256(raw).hexdigest() != values[name]:fail('OUTPUT_CHANGED')
                        if name in MEDIA:
                            size = (1080,1920) if name == MEDIA[0] else (540,960)
                            media = probe(guard_control(engine.directory(job),name))
                            streams = [v for v in media['streams'] if v.get('codec_type') == 'video']
                            duration=media['duration']
                            if (len(streams)!=1 or any(v.get('codec_type')!='video' for v in media['streams'])
                                    or (streams[0].get('width'),streams[0].get('height'))!=size
                                    or streams[0].get('codec_name')!='h264' or streams[0].get('r_frame_rate')!='30/1'
                                    or streams[0].get('sample_aspect_ratio')!='1:1'
                                    or type(duration) not in (int,float) or not math.isfinite(duration)
                                    or abs(duration-snapshot['payload']['brief']['duration'])>.1):fail('MEDIA_INVALID')
                            manifest[name] = values[name]
                        else:
                            receipt = decode(raw);self.d.clean(receipt)
                            if (receipt.get('engine') != snapshot['proof']['engine'] or receipt.get('execution_fingerprint') != snapshot['proof']['execution_fingerprint'] or receipt.get('render_sha256') != values[MEDIA[0]] or type(receipt.get('paid_provider_calls')) is not int or receipt['paid_provider_calls'] != 0):fail('OUTPUT_RECEIPT_CHANGED')
        proof = {'attempt':attempt,'preparation':snapshot['proof'],'attempt_binding':snapshot['attempt_binding'],'files':manifest,'output_profile':PROFILE}
        write_private(guard_private(directory,'completion.json'),canonical(proof))
        return manifest

    def verified_outputs(self, row):
        manifest = decode(row['manifest'])
        if set(manifest) != set(MEDIA) or any(not isinstance(v,str) or not HEX64.fullmatch(v) for v in manifest.values()):fail('OUTPUT_CHANGED')
        directory = self.directory(row['id'])
        proof = decode(read_owned(directory,'completion.json',1024*1024))
        if proof != {'attempt':row['id'],'preparation':decode(row['binding']),'attempt_binding':self.attempt_binding(row),'files':manifest,'output_profile':PROFILE}:fail('OUTPUT_CHANGED')
        if hashlib.sha256(read_owned(directory,'input.json',1024*1024)).hexdigest() != proof['preparation']['source_sha256']:fail('INPUT_CHANGED')
        base = guard_private(directory,'work','dir')
        output = guard_private(base,row['prepare_job'],'dir')
        for name,expected in manifest.items():
            if hashlib.sha256(read_owned(output,name,MAX_MEDIA)).hexdigest() != expected:fail('OUTPUT_CHANGED')
        return manifest

    def download(self, account, job, attempt, token):
        identifier(token,HEX64)
        with self.d.revision_lock,self.lock:
            snapshot = self.snapshot(account,job,current=False)
            row = self.row(account,job,attempt)
            if row['status'] != 'complete':fail('OUTPUT_UNAVAILABLE')
            self.verify_binding(row,snapshot)
            manifest = self.verified_outputs(row)
            for name in MEDIA:
                expected = digest({'attempt':attempt,'generation':row['generation'],'binding':row['execution_binding'],'files':manifest,'name':name})
                if token == expected:
                    directory = self.directory(attempt)
                    output = guard_private(guard_private(directory,'work','dir'),job,'dir')
                    raw = read_owned(output,name,MAX_MEDIA)
                    if hashlib.sha256(raw).hexdigest() != manifest[name]:fail('OUTPUT_CHANGED')
                    return name, raw
        fail('OUTPUT_UNAVAILABLE')

    def close(self):
        with self.lock:
            self.closing=True;active=list(self.active.values())
            for event,thread,_,_ in active:event.set()
        for _,thread,_,_ in active:
            join_owned(thread,10)
        with self.lock:require_settled_start(self.active.values())
