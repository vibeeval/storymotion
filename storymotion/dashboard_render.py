"""Local dashboard bridge to the same pinned Engine. No provider calls or code upload."""
import copy
import json
import threading
import time
from .engine import Engine
from .runtime import require_engine
from .security import WorkflowError,file_hash,within,digest
from .local_state import guard_private,private_directory,write_private
from .render_slot import WorkerStart,join_owned,require_settled_start

ENGINES={'hyperframes','remotion'}
FILES={'render-1080.mp4','render-mobile.mp4','cover.png','cover-360.png','subtitles.srt',
       'caption.txt','qa.json','render-engine.json','delivery.zip','delivery.json','audio-timing.json','source-brief.json','writing-context.json','edit-plan.json','revision.json','raster.json','manual-plan.json','rig.json'}


class DashboardRender:
    def __init__(self,dashboard):
        self.d=dashboard;self.lock=threading.RLock();self.active={};self.slot_tokens={}
        with self.d.connection() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS dashboard_renders(job TEXT,engine TEXT,engine_job TEXT,
              status TEXT,error TEXT,updated REAL,PRIMARY KEY(job,engine))''')
        # No automatic restart: stage rows are durable, explicit start resumes
        # under the Engine's POSIX lock. A second server cannot duplicate work.
    def validate(self,job,engine):
        if engine not in ENGINES:raise WorkflowError('Açık motor seç: hyperframes veya remotion')
        row=self.d.job(job);self.d.assert_provenance(row);self.d.eleven.guard_old_timing(job)
        self.d.audio.guard(job)
        if row['payload']['format']['adapter'] not in {'hyperframes-fixture','account-pack'}:
            raise WorkflowError('Bu hesabın tam video adaptörü henüz yok; plan/metin kaynağı gerçek render değildir')
        return row
    def row(self,job,engine):
        if engine not in ENGINES:raise WorkflowError('Geçersiz motor')
        self.d.job(job)
        with self.d.connection() as db:r=db.execute('SELECT * FROM dashboard_renders WHERE job=? AND engine=?',(job,engine)).fetchone()
        return dict(r) if r else None
    def state(self,job,engine):
        r=self.row(job,engine)
        try:self.d.audio.guard(job)
        except WorkflowError:
            return {'job':job,'engine':engine,'status':'invalidated','files':{},'provider_calls':0,'publication_ready':False,
                    'error':'Audio revision changed; use the current bound job and create new downstream evidence'}
        if not r:return {'job':job,'engine':engine,'status':'not_started','files':{},'provider_calls':0}
        e=Engine(self.d.workspace/'renders');files={}
        try:
            stages=e.store.status(r['engine_job'])['stages']
            for stage in stages:
                if stage['status']=='complete':
                    for name,h in json.loads(stage['manifest']).items():
                        path=within(e.directory(r['engine_job']),name)
                        if name in FILES and path.is_file() and file_hash(path)==h:files[name]=h
            from .edit_plan import verify_staged_assets
            if r['status']=='complete' or any(s['name']=='prepare' and s['status']=='complete' for s in stages):
                verify_staged_assets(e.payload(r['engine_job']),e.directory(r['engine_job']),delivery=any(s['name']=='delivery' and s['status']=='complete' for s in stages))
        except WorkflowError:
            return {'job':job,'engine':engine,'status':'invalidated','files':{},'provider_calls':0,'publication_ready':False,'error':'Staged or packaged required assets differ from pinned edit plan'}
        finally:e.close()
        with self.lock:owned=(job,engine) in self.active
        row=self.d.job(job)
        if row['payload'].get('audio_revision') or ((row['payload'].get('raster_revision') or row['payload'].get('edit_revision') or row['payload'].get('scene_plan_revision') or row['payload'].get('rig_revision')) and row['payload']['template']['template']['video'].get('audio_timing')):
            self.d.audio.guard(job)
            if r['status']=='complete':
                receipt_path=self.d.workspace/'renders'/r['engine_job']/'render-engine.json'
                if ('render-1080.mp4' not in files or 'render-engine.json' not in files or
                    not receipt_path.is_file()):
                    raise WorkflowError('Audio final render receipt is not bound to this timing revision')
                receipt=json.loads(receipt_path.read_text());video=row['payload']['template']['template']['video'];b=row['payload'].get('audio_revision') or {'timing_sha256':digest(video['audio_timing']),'audio_sha256':video['audio']['sha256']}
                if (receipt.get('audio_timing_sha256')!=b['timing_sha256'] or receipt.get('audio_sha256')!=b['audio_sha256'] or
                    receipt.get('render_sha256')!=files['render-1080.mp4'] or receipt.get('engine')!=engine or
                    receipt.get('execution_fingerprint')!=row['payload']['execution']['fingerprint']):
                    raise WorkflowError('Audio final receipt hash/source binding changed')
        if r['status']=='running' and not owned:r['status']='interrupted_or_other_process; explicit resume uses workspace lock'
        return {**r,'stages':[{k:s[k] for k in ['name','status','error']} for s in stages],
                'files':files,'provider_calls':0,'publication_ready':False}
    def video_input(self,row):
        if row['payload'].get('edit_revision'):return self.d.edits.render_input(row)
        if row['payload'].get('scene_plan_revision'):return self.d.plans.render_input(row)
        if row['payload'].get('raster_revision'):return self.d.raster.render_input(row)
        if row['payload'].get('rig_revision'):return self.d.rigs.render_input(row)
        if row['payload'].get('audio_revision'):return self.d.audio.render_input(row)
        return self.base_video_input(row)
    def edit_plan(self,job,engine):
        # Read-only: no staging, runtime requirement, media probe or dispatch.
        with self.d.revision_lock:
            row=self.validate(job,engine)
            from .engine import prepare_input,ROOT
            from .edit_plan import compile_edit_plan
            brief,profile=prepare_input(self.video_input(row))
            if not brief.get('creative'):raise WorkflowError('Kurgu planı sürümlü sahne sözleşmesi gerektirir; eski fixture desteklenmez')
            return {'job':job,'engine':engine,'edit_plan':compile_edit_plan(profile,brief,ROOT),'provider_calls':0,'render_started':False}
    def base_video_input(self,row):
        """Rebuild the immutable host input; shared by dispatch and QA binding."""
        p=row['payload'];d=p['input'];video=copy.deepcopy(p['template']['template']['video'])
        video.update(title=d['title'],brief=d['brief'],caption=d['caption'],language=p['template']['template']['language'],
                     appearance=p['template']['template']['appearance'])
        video['production_notes']={k:p['template']['template'][k] for k in ['tone','visual_style','source_notes']}
        if 'brand_identity' in d:video['brand_identity']=d['brand_identity']
        if video['script']!=d['content']:raise WorkflowError('Senaryo ve cue şablonunu birlikte düzenle')
        if video.get('audio') or video['alignment']!='provisional_silent':
            raise WorkflowError('Panel renderi bu sürümde sessiz animatik içindir; yeni ses sonrası retime kabulü gerekir')
        return video
    def start(self,job,engine):
        with self.d.revision_lock,self.lock:
            token=self.d.render_slot.claim(('normal',job,engine))
            if token is None:return {'status':'local_render_already_running','active':True,'provider_calls':0}
            self.slot_tokens[(job,engine)]=token
            try:
                result=self._start_locked(job,engine)
                if result.get('status')!='started':
                    self.release_slot((job,engine),token)
                return result
            except BaseException:
                if (job,engine) not in self.active or self.slot_tokens.get((job,engine))!=token:
                    self.release_slot((job,engine),token)
                raise
    def release_slot(self,key,token):
        with self.lock:
            if self.slot_tokens.get(key)==token:self.slot_tokens.pop(key,None)
        self.d.render_slot.release(token)
    def forget_owned(self,key,owned,token):
        with self.lock:
            if self.active.get(key) is owned:self.active.pop(key,None)
            self.release_slot(key,token)
    def bookkeeping_warning(self,error):
        try:self.d.local_log.warning('LOCAL_WRITE_FAILED',error)
        except Exception:pass  # Logging cannot strand an already stopped worker.
    def _start_locked(self,job,engine):
        row=self.validate(job,engine);require_engine(engine)
        with self.lock:
            if self.active:return {'status':'local_render_already_running','active':True,'provider_calls':0}
            video=self.video_input(row)
            path=self.d.output(job)/('render-input-'+engine+'.json')
            guard_private(self.d.workspace,path.relative_to(self.d.workspace))
            private_directory(path.parent)
            write_private(path,json.dumps(video,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
            with Engine(self.d.workspace/'renders') as e:engine_job=e.create(path,render_engine=engine)['job']
            with self.d.connection() as db:db.execute('INSERT INTO dashboard_renders VALUES(?,?,?,?,?,?) ON CONFLICT(job,engine) DO UPDATE SET '
                'engine_job=excluded.engine_job,status=excluded.status,error=NULL,updated=excluded.updated',
                (job,engine,engine_job,'running',None,time.time()))
            cancel=threading.Event();entry=WorkerStart(self.work,(job,engine,engine_job,cancel))
            thread=threading.Thread(target=entry.run,daemon=True)
            key=(job,engine);owned=(cancel,thread);token=self.slot_tokens.get(key)
            self.active[key]=owned
            try:thread.start()
            except BaseException:
                thread._storymotion_start_unconfirmed=True
                uncertain=not entry.abort_before_entry()
                try:
                    if self.active.get(key) is owned:
                        with self.d.connection() as db:db.execute("UPDATE dashboard_renders SET status=?,error=?,updated=? WHERE job=? AND engine=? AND engine_job=? AND status='running'",
                            ('running' if uncertain else 'failed','LOCAL_RENDER_THREAD_START_UNCONFIRMED' if uncertain else 'LOCAL_RENDER_THREAD_START_FAILED',time.time(),job,engine,engine_job))
                except Exception as error:self.bookkeeping_warning(error)
                finally:
                    if not uncertain:self.forget_owned(key,owned,token)
                raise
        return {'status':'started','job':job,'engine':engine,'engine_job':engine_job,'provider_calls':0}
    def work(self,job,engine,engine_job,cancel):
        key=(job,engine)
        with self.lock:
            owned=self.active.get(key);token=self.slot_tokens.get(key)
            if owned is None:
                self.release_slot(key,token);return
            if owned[0] is not cancel or owned[1] is not threading.current_thread():return
        try:
            e=None
            try:
                e=Engine(self.d.workspace/'renders');e.run(engine_job,cancel_event=cancel)
                status='complete';error=None
            except Exception:
                status='cancelled' if cancel.is_set() else 'failed'
                error='Yerel render tamamlanmadı; stage durumunu ve doctor çıktısını incele. Otomatik kurulum/motor geçişi yok.'
            finally:
                if e:
                    try:e.close()
                    except Exception as error:self.bookkeeping_warning(error);return
            with self.lock:
                if self.active.get(key) is not owned or self.slot_tokens.get(key)!=token:return
                try:
                    with self.d.connection() as db:db.execute("UPDATE dashboard_renders SET status=?,error=?,updated=? WHERE job=? AND engine=? AND engine_job=? AND status='running'",
                        (status,error,time.time(),job,engine,engine_job))
                except Exception as error:self.bookkeeping_warning(error)
        finally:self.forget_owned(key,owned,token)
    def cancel(self,job,engine):
        self.row(job,engine)
        with self.lock:
            current=self.active.get((job,engine))
            if current:current[0].set()
        return {'status':'cancel_requested' if current else 'no_owned_running_render','provider_calls':0}
    def download(self,job,engine,name):
        with self.d.revision_lock:return self._download_locked(job,engine,name)
    def _download_locked(self,job,engine,name):
        self.validate(job,engine)
        if name not in FILES:raise WorkflowError('Render dosyası desteklenmiyor')
        r=self.state(job,engine)
        if r['status']!='complete' or name not in r['files']:raise WorkflowError('Tamamlanmış ve hash doğrulanmış render gerekli')
        p=self.d.job(job)['payload'];bound=bool(p.get('audio_revision') or p.get('edit_revision') or p.get('raster_revision') or p.get('scene_plan_revision') or p.get('rig_revision') or p.get('series_revision'));audio=bool(p['template']['template']['video'].get('audio_timing'));before=None
        if bound:
            # Reuse QA's full selected dashboard/Engine input+payload verifier.
            before,payload,_=self.d.reviews.verified_render(job,engine)
            if before['engine_job']!=r['engine_job']:raise WorkflowError('Selected render binding changed before download')
        with Engine(self.d.workspace/'renders') as e:path=within(e.directory(r['engine_job']),name)
        if audio and name in {'delivery.zip','delivery.json'}:
            from .audio_retime import verify_final_audio
            verify_final_audio(payload,path.parent,delivery=True)
        raw=path.read_bytes()
        import hashlib
        if hashlib.sha256(raw).hexdigest()!=r['files'][name]:raise WorkflowError('Render hash değişti; indirme durdu')
        self.validate(job,engine)
        current=self.state(job,engine)
        if current.get('status')!='complete' or current.get('engine_job')!=r['engine_job'] or current.get('files',{}).get(name)!=r['files'][name]:
            raise WorkflowError('Render revision/file binding changed during download; no bytes released')
        if bound and self.d.reviews.verified_render(job,engine)[0]!=before:
            raise WorkflowError('Selected audio/Engine binding changed during download; no bytes released')
        return raw
    def close(self):
        with self.lock:active=list(self.active.values())
        for event,thread in active:event.set()
        for event,thread in active:join_owned(thread,10)
        with self.lock:require_settled_start(self.active.values())
