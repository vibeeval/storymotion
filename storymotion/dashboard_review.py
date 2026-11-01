"""Host-owned job mapping for local QA. Client input cannot select a file path."""
from .engine import Engine
from .security import WorkflowError,canonical,digest,file_hash
import json
import re


class DashboardReview:
    def __init__(self,dashboard):
        self.d=dashboard;self.service=None
        with self.d.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS dashboard_reviews(job TEXT,engine TEXT,review TEXT,binding TEXT,PRIMARY KEY(job,engine))')
            if 'binding' not in {r[1] for r in db.execute('PRAGMA table_info(dashboard_reviews)')}:
                db.execute('ALTER TABLE dashboard_reviews ADD COLUMN binding TEXT')
    def runtime(self):
        if self.service is None:
            from .qa_review import ReviewService
            self.service=ReviewService(self.d.workspace/'reviews',media_root=self.d.workspace/'renders')
        return self.service
    def close(self):
        if self.service is not None:
            self.service.close()
            self.service=None
    def binding(self,job,engine):
        self.d.renders.validate(job,engine)
        with self.d.connection() as db:row=db.execute('SELECT review FROM dashboard_reviews WHERE job=? AND engine=?',(job,engine)).fetchone()
        return row[0] if row else None
    def state(self,job,engine):
        review=self.binding(job,engine)
        if not review:return {'job':job,'engine':engine,'status':'not_started','files':{},'issues':[]}
        with self.d.connection() as db:bound=db.execute('SELECT binding FROM dashboard_reviews WHERE job=? AND engine=?',(job,engine)).fetchone()[0]
        try:
            current,_,_=self.verified_render(job,engine)
            if not bound or canonical(current)!=bound:raise WorkflowError('QA render receipt binding changed')
        except WorkflowError:
            return {'job':job,'engine':engine,'review_id':review,'state':'invalidated','status':'incomplete','current':False,
                    'files':{},'issues':[],'reason':'Render receipt, job or hash changed; create a new bound QA review'}
        result=self.runtime().status(review)
        return {**result,'job':job,'engine':engine,'review_id':review,'files':self.file_map(review) if result.get('state')=='ready' else {}}
    def verified_render(self,job,engine):
        """Do not trust a dashboard complete flag or UI enablement as a receipt."""
        row=self.d.renders.validate(job,engine);render=self.d.renders.state(job,engine)
        sha=render.get('files',{}).get('render-1080.mp4')
        receipt_sha=render.get('files',{}).get('render-engine.json')
        if render.get('status')!='complete' or not all(isinstance(h,str) and re.fullmatch('[0-9a-f]{64}',h) for h in [sha,receipt_sha]):
            raise WorkflowError('QA için tamamlanmış render, MP4 hash ve motor receipt gerekli')
        engine_job=render.get('engine_job')
        if not isinstance(engine_job,str) or not re.fullmatch('[0-9a-f]{24}',engine_job):raise WorkflowError('QA engine job binding missing')
        e=Engine(self.d.workspace/'renders')
        try:
            payload=e.payload(engine_job);out=e.directory(engine_job)
            stage=e.store.stage(engine_job,'render')
            expected={'render-1080.mp4':sha,'render-engine.json':receipt_sha}
            if not stage or stage['status']!='complete' or json.loads(stage['manifest'])!=expected:
                raise WorkflowError('QA render receipt manifest missing or mismatched')
            for name,h in expected.items():
                path=out/name
                if path.is_symlink() or not path.is_file() or file_hash(path)!=h:raise WorkflowError('QA render receipt bytes changed')
            receipt=json.loads((out/'render-engine.json').read_text())
            if (payload.get('render_engine')!=engine or receipt.get('engine')!=engine or receipt.get('render_sha256')!=sha or
                receipt.get('execution_fingerprint')!=payload.get('execution',{}).get('fingerprint')):
                raise WorkflowError('QA receipt is not bound to this engine and execution')
            # Rebuild the pinned input instead of accepting another job's valid MP4.
            source=self.d.output(job)/('render-input-'+engine+'.json')
            if source.is_symlink() or not source.is_file() or canonical(json.loads(source.read_text()))!=canonical(self.d.renders.video_input(row)):
                raise WorkflowError('QA dashboard input binding changed')
            expected_job,expected_payload=e.plan(source,render_engine=engine)
            if expected_job!=engine_job or canonical(expected_payload)!=canonical(payload):raise WorkflowError('QA engine job does not match the selected dashboard job')
            binding={'dashboard_job':job,'engine':engine,'engine_job':engine_job,'render_sha256':sha,
                     'receipt_sha256':receipt_sha,'manifest_sha256':digest(expected),'payload_sha256':digest(payload)}
            return binding,payload,out/'render-1080.mp4'
        except (ValueError,KeyError,TypeError,OSError):
            raise WorkflowError('QA render receipt or job binding is invalid') from None
        finally:e.close()
    def file_map(self,review):
        result={}
        for item in self.runtime().files(review):
            alias=item['path'].replace('/','__')
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,180}',alias) or alias in result:
                raise WorkflowError('QA dosya adı güvenli ve benzersiz olmalı')
            result[alias]=item
        return result
    def action(self,job,action,data):
        with self.d.revision_lock:return self._action_locked(job,action,data)
    def _action_locked(self,job,action,data):
        expected={'review-create':{'engine'},'review-state':{'engine'},'review-recheck':{'engine'},
                  'review-issue':{'engine','issue'},'review-resolve':{'engine','issue_id','local_fix'}}
        if action not in expected or set(data)!=expected[action]:raise WorkflowError('QA işlem alanları geçersiz')
        self.d.clean(data);engine=data['engine'];review=self.binding(job,engine)
        if action=='review-state':return self.state(job,engine)
        if action=='review-create':
            bound,payload,path=self.verified_render(job,engine)
            result=self.runtime().create(path,payload['brief'],source_fingerprint=payload['execution']['fingerprint'],
                asset_hashes=None,expected_render_sha256=bound['render_sha256'],render_binding=bound)
            after,_,_=self.verified_render(job,engine)
            if bound!=after:raise WorkflowError('QA render receipt changed during capture; no review binding committed')
            review=result['review_id']
            with self.d.connection() as db:db.execute('INSERT INTO dashboard_reviews(job,engine,review,binding) VALUES(?,?,?,?) ON CONFLICT(job,engine) DO UPDATE SET review=excluded.review,binding=excluded.binding',(job,engine,review,canonical(bound)))
        elif not review:raise WorkflowError('Önce yerel QA panosunu hazırla')
        else:
            if self.state(job,engine).get('state')=='invalidated':raise WorkflowError('QA render receipt changed; create a new review')
            if action=='review-issue':self.runtime().record_issue(review,data['issue'])
            elif action=='review-resolve':self.runtime().resolve_issue(review,data['issue_id'],data['local_fix'])
            elif action=='review-recheck':self.runtime().recheck(review)
        return self.state(job,engine)
    def download(self,job,engine,name):
        with self.d.revision_lock:return self._download_locked(job,engine,name)
    def _download_locked(self,job,engine,name):
        review=self.binding(job,engine)
        if not review:raise WorkflowError('QA dosyası henüz yok')
        if self.state(job,engine).get('state')=='invalidated':raise WorkflowError('QA receipt changed; stale evidence cannot be downloaded')
        mapping=self.file_map(review)
        if name not in mapping:raise WorkflowError('QA dosyası bu incelemede kayıtlı değil')
        before=self.verified_render(job,engine)[0]
        raw=self.runtime().file(review,mapping[name]['path']).read_bytes()
        import hashlib
        if (hashlib.sha256(raw).hexdigest()!=mapping[name]['sha256'] or self.binding(job,engine)!=review or
            self.verified_render(job,engine)[0]!=before or self.file_map(review).get(name)!=mapping[name]):
            raise WorkflowError('QA report/revision binding changed during download; no bytes released')
        return raw
