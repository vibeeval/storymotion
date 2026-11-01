from .local_state import private_directory, private_database, write_private
from .account_packs import account_catalog, render_profile, sample_brief, template_brief
"""Loopback dashboard. ElevenLabs is off by default; explicit demo/live host modes."""
import argparse
import contextlib
import copy
import hashlib
import http.server
import json
import mimetypes
import re
import sqlite3
import threading
import time
import tempfile
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from typing import Literal,Optional,Union
from .engine import Engine, ROOT, microusd
from .security import WorkflowError, canonical, digest, file_hash, scan_bytes, within, write_json
from .store import Store, now
from .provenance import execution_provenance
from .provider_catalog import public_capabilities
from .local_state import guard_workspace
from .local_session import LocalSession, request_path
from .dashboard_routes import json_get

UI_REVISION='0.14.1-account-topic-planning'


class Dashboard:
    def __init__(self,workspace='work',hf=None,key_ttl_seconds=900,elevenlabs_mode='off',elevenlabs_service=None,llm_mode='off',llm_service=None):
        self.session_auth=LocalSession()
        self.workspace=guard_workspace(workspace,database='jobs.sqlite3');self.hf=hf
        self.runtime_execution=execution_provenance()['fingerprint']
        self.catalog=account_catalog(json.loads((ROOT/'catalog/accounts.json').read_text()))
        self.providers=json.loads((ROOT/'catalog/providers.json').read_text())
        if not isinstance(key_ttl_seconds,(int,float)) or not 0<key_ttl_seconds<=900:raise WorkflowError('Invalid demo expiry')
        self.key_ttl_seconds=key_ttl_seconds
        self.slots={};self.expiry_timers={};self.mutex=threading.Lock();self.action_lock=threading.Lock()
        self._local_log=None
        self.worker_lock=threading.Lock();self.last_worker_result=None
        self.revision_lock=threading.RLock()
        from .render_slot import RenderSlot
        self.render_slot=RenderSlot()
        with self.connection() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS dashboard_jobs(id TEXT PRIMARY KEY,payload TEXT NOT NULL,status TEXT NOT NULL,
              engine_job TEXT,manifest TEXT NOT NULL DEFAULT '{}',error TEXT,created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS dashboard_templates(account TEXT,format TEXT,revision INTEGER NOT NULL,payload TEXT NOT NULL,
              PRIMARY KEY(account,format));
            CREATE TABLE IF NOT EXISTS dashboard_budgets(job TEXT PRIMARY KEY,cap_microusd INTEGER NOT NULL,
              quote_source TEXT NOT NULL,approved_by TEXT NOT NULL,created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS dashboard_events(seq INTEGER PRIMARY KEY,job TEXT,event TEXT,created TEXT);
            ''')
            columns={r[1] for r in db.execute('PRAGMA table_info(dashboard_jobs)')}
            for name,kind in [('lease_owner','TEXT'),('lease_until','REAL'),('lease_token','TEXT'),('attempts','INTEGER NOT NULL DEFAULT 0')]:
                if name not in columns:db.execute('ALTER TABLE dashboard_jobs ADD COLUMN '+name+' '+kind)
        from .elevenlabs import ElevenService
        self.eleven=elevenlabs_service or ElevenService(self.workspace/'voice',mode=elevenlabs_mode)
        self.eleven.source_guard=self._voice_source_guard
        from .llm_service import LLMService
        self.llm=llm_service or LLMService(self.workspace/'writing',mode=llm_mode)
        from .dashboard_render import DashboardRender
        self.renders=DashboardRender(self)
        from .dashboard_review import DashboardReview
        self.reviews=DashboardReview(self)
        from .audio_retime import AudioRevisions
        self.audio=AudioRevisions(self)
        from .raster_revision import RasterRevisions
        self.raster=RasterRevisions(self)
        from .manual_scene_revision import ManualSceneRevisions
        self.plans=ManualSceneRevisions(self)
        from .scene_revision import SceneRevisions
        self.edits=SceneRevisions(self)
        from .rig_revision import RigRevisions
        self.rigs=RigRevisions(self)
        from .series import Series
        self.series=Series(self)
        from .taxonomy import Taxonomy
        self.taxonomy=Taxonomy(self)
        from .template_studio import TemplateStudio
        self.template_studio=TemplateStudio(self)
        from .family_render import FamilyRender
        self.family_renders=FamilyRender(self)

    @property
    def local_log(self):
        with self.mutex:
            if self._local_log is None:
                from .local_log import LocalLog
                self._local_log=LocalLog(self.workspace)
            return self._local_log

    def close_local_log(self):
        with self.mutex:
            if self._local_log is not None:self._local_log.close()

    @contextlib.contextmanager
    def connection(self):
        guard_workspace(self.workspace,database='jobs.sqlite3',canonical_alias=False)
        private_directory(self.workspace)
        db=private_database(self.workspace,'jobs.sqlite3',timeout=10);db.row_factory=sqlite3.Row
        try:yield db;db.commit()
        except Exception:db.rollback();raise
        finally:db.close()

    def account_format(self,account,fmt):
        a=next((a for a in self.catalog['accounts'] if a['id']==account),None)
        f=next((f for f in self.catalog['formats'] if f['id']==fmt),None)
        if not a or not f or fmt not in a['formats']:raise WorkflowError('Hesap ve format eşleşmesi geçersiz')
        return a,f

    def provider_model(self,provider,model,task):
        p=next((p for p in self.providers['providers'] if p['id']==provider),None)
        if not p or task not in p['capabilities'] or model not in [m['id'] for m in p['models']]:
            raise WorkflowError('Sağlayıcı, model ve görev uyumsuz; anahtarlar servisler arasında ortak değildir')
        return p

    def template(self,account,fmt):
        a,f=self.account_format(account,fmt)
        with self.connection() as db:
            row=db.execute('SELECT * FROM dashboard_templates WHERE account=? AND format=?',(account,fmt)).fetchone()
        appearance=None
        if f['adapter'] in {'hyperframes-fixture','account-pack'}:
            profile=render_profile(account)
            appearance={k:profile[k] for k in ['palette','title_size','subtitle_size']}
        if row:
            saved=json.loads(row['payload']);saved.setdefault('appearance',appearance)
            return {'revision':row['revision'],'template':saved}
        v=template_brief(account,f['adapter']) if f['adapter'] in {'account-pack','hyperframes-fixture'} else None
        return {'revision':0,'template':{'language':a['language'],'tone':a['tone'],'visual_style':a['style'],
                'source_notes':'','appearance':appearance,'video':v}}

    def clean(self,value):
        raw=canonical(value)
        if len(raw.encode())>100000 or scan_bytes(raw.encode()):raise WorkflowError('Girdi fazla büyük veya olası gizli değer içeriyor; değer kaydedilmedi')
        def walk(v):
            if isinstance(v,dict):
                for k,x in v.items():
                    if re.search(r'(?i)(?:api.?key|secret|password|access.?token|credential)',k):raise WorkflowError('İş ve şablon verisine credential alanı alınmaz')
                    walk(x)
            elif isinstance(v,list):
                for x in v:walk(x)
        walk(value)
        from .providers import safe_public_json
        for service in (self.eleven,self.llm):safe_public_json(value,service.broker)

    def save_template(self,data):
        self.assert_runtime_current()
        if set(data)!={'account','format','revision','template'}:raise WorkflowError('Şablon alanları geçersiz')
        self.account_format(data['account'],data['format']);value=data['template'];self.clean(value)
        if set(value)!={'language','tone','visual_style','source_notes','video','appearance'} or value['language'] not in {'tr','en','de'}:
            raise WorkflowError('Şablon: language, tone, visual_style, source_notes ve video alanlarını kullan')
        if not all(isinstance(value[k],str) and len(value[k])<12000 for k in ['tone','visual_style','source_notes']):raise WorkflowError('Şablon metni geçersiz')
        a,f=self.account_format(data['account'],data['format'])
        if f['adapter'] in {'hyperframes-fixture','account-pack'}:
            from .engine import validate,apply_appearance
            if f['adapter']=='account-pack':
                from .creative import validate_proposal
                from .writing_context import bound_brief
                bound_brief(a['id'],value['video'])
            validate(value['video'],render_profile(a['id']))
            apply_appearance(render_profile(a['id']),value['appearance'])
        elif value['video'] is not None or value['appearance'] is not None:raise WorkflowError('Bu format için video adaptörü hazır değil; plan alanlarını kullan')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT revision FROM dashboard_templates WHERE account=? AND format=?',(data['account'],data['format'])).fetchone()
            current=row[0] if row else 0
            if type(data['revision']) is not int or current!=data['revision']:raise WorkflowError('Şablon başka bir işlemde değişti; yenile ve tekrar düzenle')
            db.execute('INSERT INTO dashboard_templates VALUES(?,?,?,?) ON CONFLICT(account,format) DO UPDATE SET revision=excluded.revision,payload=excluded.payload',
                       (data['account'],data['format'],current+1,canonical(value)))
        return {'revision':current+1,'template':value,'composition_fields':['language','appearance','video'],
                'planning_only_fields':['tone','visual_style','source_notes']}

    def enqueue(self,data):
        self.assert_runtime_current()
        required={'account','format','title','brief','content','caption','provider','model','task','template_revision'}
        if not isinstance(data,dict) or set(data)-{'brand_identity'}!=required:raise WorkflowError('İş alanları geçersiz')
        from .identity import normalize_identity
        data=copy.deepcopy(data)
        data['brand_identity']=normalize_identity(data.get('brand_identity'))
        a,f=self.account_format(data['account'],data['format'])
        if data['task'] not in f['allowed_tasks']:raise WorkflowError('Seçilen sağlayıcı görevi bu içerik formatına uygun değil')
        self.provider_model(data['provider'],data['model'],data['task']);self.clean(data)
        for k in ['title','brief','content','caption']:
            if not isinstance(data[k],str) or not data[k].strip() or len(data[k])>20000:raise WorkflowError('Başlık, brief, metin ve caption gerekli; boş veya fazla uzun alan var')
        t=self.template(a['id'],f['id'])
        if t['revision']!=data['template_revision']:raise WorkflowError('Şablon revizyonu değişti; önce yenile')
        payload={'input':data,'account':a,'format':f,'template':t,'generation':'not_run','paid_calls':0,'execution':execution_provenance()}
        key=digest(payload)[:24]
        with self.connection() as db:
            db.execute('INSERT OR IGNORE INTO dashboard_jobs(id,payload,status,created) VALUES(?,?,?,?)',(key,canonical(payload),'queued',now()))
            db.execute('INSERT INTO dashboard_events(job,event,created) VALUES(?,?,?)',(key,'created_or_reused',now()))
        return self.job(key)

    def job(self,key):
        if not re.fullmatch('[a-f0-9]{24}',key):raise WorkflowError('Geçersiz iş kimliği')
        with self.connection() as db:row=db.execute('SELECT * FROM dashboard_jobs WHERE id=?',(key,)).fetchone()
        if not row:raise WorkflowError('İş bulunamadı')
        r=dict(row);r.pop('lease_token',None);r['payload']=json.loads(r['payload']);r['manifest']=json.loads(r['manifest'])
        r['files']=[p for p in r['manifest'] if p in {'draft.md','caption.txt','plan.json','cover.svg','subtitles.srt','check.json','qa.json','package.zip'}]
        return r

    def jobs(self):
        with self.connection() as db:ids=[r[0] for r in db.execute('SELECT id FROM dashboard_jobs ORDER BY created DESC LIMIT 100')]
        return [self.job(i) for i in ids]

    def output(self,key):
        # Dashboard owns these exact directories; never silently resolve a linked child.
        for p in [self.workspace/'dashboard',self.workspace/'dashboard'/key]:
            if p.is_symlink():raise WorkflowError('Dashboard output path must not be linked')
        return within(self.workspace,'dashboard/'+key)

    def assert_runtime_current(self):
        if self.runtime_execution!=execution_provenance()['fingerprint']:
            raise WorkflowError('Çalışan uygulamanın kaynak dosyaları değişti; yerel sunucuyu yeniden başlat. Yeni üretim durduruldu')

    def assert_provenance(self,row):
        self.assert_runtime_current()
        if row['payload'].get('execution',{}).get('fingerprint')!=execution_provenance()['fingerprint']:
            raise WorkflowError('Üretim kodu/adaptör/vendor sürümü değişti veya eski iş kaydı; yeni iş oluştur. Eski çıktı sessizce yeniden kullanılmaz')
        if hasattr(self,'series'):self.series.guard(row)

    def _voice_source_guard(self,payload):
        from .elevenlabs import text_sha
        row=self.job(payload['job']);self.assert_provenance(row)
        if row['payload'].get('edit_revision') or row['payload'].get('raster_revision') or row['payload'].get('scene_plan_revision') or row['payload'].get('rig_revision'):raise WorkflowError('Görsel/rig revizyonu senaryo/sesi korur; yeni ses için kaynak işinden ilerleyin')
        if text_sha(row['payload']['input']['content'])!=payload['source_script_sha256']:
            raise WorkflowError('Ses onayının kaynak senaryosu değişti; yeni önizleme gerekli')

    def prepare(self,key,lease_token=None):
        self.audio.guard(key)
        self.eleven.guard_old_timing(key)
        with Engine(self.workspace,self.hf) as e:
            # Shared workspace lock prevents duplicate preparation with CLI and other HTTP requests.
            with e.store.lock(blocking=lease_token is not None):
                row=self.job(key);self.assert_provenance(row);out=self.output(key);p=row['payload'];d=p['input'];fmt=p['format']
                with self.connection() as db:lease=db.execute('SELECT lease_token,lease_until FROM dashboard_jobs WHERE id=?',(key,)).fetchone()
                if lease['lease_token'] and lease['lease_until']>time.time() and lease['lease_token']!=lease_token:
                    raise WorkflowError('İş yerel worker tarafından tutuluyor; aynı hazırlama ikinci kez başlatılmadı')
                if row['status'] in {'prepared','checked','packaged'} and row['manifest'] and all(within(out,f).is_file() and file_hash(within(out,f))==h for f,h in row['manifest'].items()):return row
                with self.connection() as db:db.execute('UPDATE dashboard_jobs SET status=?,error=NULL WHERE id=?',('preparing',key))
                private_directory(out)
                try:
                    if fmt['adapter'] in {'hyperframes-fixture','account-pack'}:
                        video=self.renders.video_input(row)
                        if video['script']!=d['content']:raise WorkflowError('Video senaryosunu şablon editöründeki cue alanlarıyla birlikte düzenle; otomatik ses hizalaması yok')
                        write_json(out/'video-input.json',video)
                        job,payload=e.plan(out/'video-input.json')
                        e.store.db.execute('INSERT OR IGNORE INTO jobs VALUES(?,?,?)',(job,canonical(payload),now()));e.store.db.commit()
                        from .compose import build
                        generated=out/'source';files=build(payload,generated,ROOT)
                        # The dashboard keeps its own immutable queue binding; CLI work is separately identified.
                        files=['source/'+f for f in files]
                        for name in ['cover.svg','caption.txt','subtitles.srt']:
                            write_private(out/name,(generated/name).read_bytes());files.append(name)
                        if p.get('audio_revision'):files += ['audio-binding.json']
                        if video.get('audio_timing'):files += ['audio-timing.json',video['audio']['file']]
                        if p.get('edit_revision'):files += ['revision.json']
                        if video.get('rig'):files += ['rig.json']
                        # A visual child retains its rig ancestor marker. Its own
                        # revision.json binds that ancestry, which audio.guard and
                        # video_input verify; only the rig origin owns this file.
                        if p.get('rig_revision') and not p.get('edit_revision'):files += ['rig-binding.json']
                        if video.get('scene_plan'):files += ['manual-plan.json']
                        if video.get('raster'):files += ['raster.json',video['raster']['asset']['file']]
                        with self.connection() as db:db.execute('UPDATE dashboard_jobs SET engine_job=? WHERE id=?',(job,key))
                    else:
                        write_private(out/'draft.md','# '+d['title']+'\n\n'+d['content']+'\n\n## Brief\n'+d['brief']+'\n\n## Kaynak notları\n'+p['template']['template']['source_notes']+'\n')
                        write_private(out/'caption.txt',d['caption']+'\n')
                        files=['draft.md','caption.txt']
                    write_json(out/'plan.json',{'account':p['account'],'format':fmt,'input':d,'template':p['template'],
                        'status':'manual_draft_for_review' if fmt['adapter']=='manual-text' else 'plan_or_fixture_for_review',
                        'provider_executed':isinstance(p['generation'],dict),'audio_generated':False,'paid_calls':p['paid_calls'],
                        'generation':p['generation'],'human_review':'pending','automatic_live_dispatch':False})
                    files.append('plan.json');manifest={f:file_hash(out/f) for f in files}
                    with self.connection() as db:
                        db.execute('UPDATE dashboard_jobs SET status=?,manifest=?,error=NULL WHERE id=?',('prepared',canonical(manifest),key))
                        db.execute('INSERT INTO dashboard_events(job,event,created) VALUES(?,?,?)',(key,'local_prepare_complete',now()))
                except Exception:
                    with self.connection() as db:db.execute('UPDATE dashboard_jobs SET status=?,error=? WHERE id=?',('failed','Yerel hazırlık tamamlanmadı; girdiyi ve format kapasitesini kontrol et',key))
                    raise
            return self.job(key)

    def claim(self,owner,lease_seconds=120):
        if not isinstance(owner,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,60}',owner) or not 0<lease_seconds<=600:raise WorkflowError('Invalid worker lease')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE dashboard_jobs SET status='queued',lease_owner=NULL,lease_until=NULL,lease_token=NULL WHERE status IN ('leased','preparing') AND lease_token IS NOT NULL AND lease_until<=?",(time.time(),))
            row=db.execute("SELECT id FROM dashboard_jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if not row:return None
            token=uuid.uuid4().hex
            db.execute("UPDATE dashboard_jobs SET status='leased',lease_owner=?,lease_until=?,lease_token=?,attempts=attempts+1 WHERE id=?",(owner,time.time()+lease_seconds,token,row['id']))
            db.execute('INSERT INTO dashboard_events(job,event,created) VALUES(?,?,?)',(row['id'],'local_worker_claimed',now()))
        return {'job':row['id'],'token':token,'owner':owner}

    def finish_claim(self,claim,error=False):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT lease_token FROM dashboard_jobs WHERE id=?',(claim['job'],)).fetchone()
            if not row or row['lease_token']!=claim['token']:raise WorkflowError('Worker lease no longer belongs to this execution')
            if error:db.execute("UPDATE dashboard_jobs SET status='failed',error='Yerel worker hazırlığı tamamlayamadı; provider çalıştırılmadı' WHERE id=?",(claim['job'],))
            db.execute('UPDATE dashboard_jobs SET lease_owner=NULL,lease_until=NULL,lease_token=NULL WHERE id=?',(claim['job'],))
            db.execute('INSERT INTO dashboard_events(job,event,created) VALUES(?,?,?)',(claim['job'],'local_worker_failed' if error else 'local_worker_prepared',now()))

    def renew_claim(self,claim,lease_seconds=120):
        with self.connection() as db:
            result=db.execute('UPDATE dashboard_jobs SET lease_until=? WHERE id=? AND lease_token=?',(time.time()+lease_seconds,claim['job'],claim['token']))
            return result.rowcount==1

    def start_worker_once(self):
        if not self.worker_lock.acquire(blocking=False):return {'status':'already_running','provider_calls':0}
        def run():
            try:
                from .worker import LocalWorker
                self.last_worker_result=LocalWorker(self).run_once()
            except Exception:self.last_worker_result={'status':'failed','provider_calls':0}
            finally:self.worker_lock.release()
        thread=threading.Thread(target=run,daemon=True);thread.start()
        return {'status':'started_local_worker','provider_calls':0,'scope':'one queued local preparation; no provider or render dispatch'}

    def check(self,key):
        with Store(self.workspace) as store,store.lock(blocking=True):return self._check_locked(key)

    def _check_locked(self,key):
        self.audio.guard(key)
        self.eleven.guard_old_timing(key)
        r=self.job(key)
        self.assert_provenance(r)
        if r['status'] not in {'prepared','checked','packaged'}:raise WorkflowError('Önce yerel kaynağı hazırla')
        out=self.output(key);fmt=r['payload']['format']
        if fmt['adapter'] in {'hyperframes-fixture','account-pack'}:
            with Engine(self.workspace,self.hf) as engine:raw=engine.hf_call(['check','--json'],out/'source')
            report=json.loads(raw)
            if not report.get('ok') or report.get('browserSkipped'):raise WorkflowError('Gerçek browser check geçmedi')
        else:report={'ok':True,'check':'manual_input_package_schema','content_correctness':'pending_human_review','provider_executed':False}
        write_json(out/'check.json',report)
        manifest=r['manifest'];manifest.pop('package.zip',None);manifest['check.json']=file_hash(out/'check.json')
        with self.connection() as db:db.execute('UPDATE dashboard_jobs SET status=?,manifest=? WHERE id=?',('checked',canonical(manifest),key))
        return self.job(key)

    def budget(self,key,data):
        self.job(key)
        if set(data)!={'max_usd','quote_source','approved_by'}:raise WorkflowError('Bütçe alanları geçersiz')
        self.clean(data);amount=microusd(data['max_usd'])
        if not all(isinstance(data[k],str) and data[k].strip() and len(data[k])<500 for k in ['quote_source','approved_by']):raise WorkflowError('Tutar kaynağı ve onay referansı gerekli')
        with self.connection() as db:db.execute('INSERT INTO dashboard_budgets VALUES(?,?,?,?,?) ON CONFLICT(job) DO UPDATE SET cap_microusd=excluded.cap_microusd,quote_source=excluded.quote_source,approved_by=excluded.approved_by,created=excluded.created',(key,amount,data['quote_source'],data['approved_by'],now()))
        return {'status':'local_plan_limit_only','actual_microusd':0,'live_calls_enabled':False,'provider_billing_cap':False}

    def demo_key(self,data):
        if set(data)!={'provider','value'}:raise WorkflowError('Demo alanları geçersiz')
        if data['provider'] not in [p['id'] for p in self.providers['providers'] if p['key_kind']!='none']:raise WorkflowError('Bu sağlayıcı için key alanı yok')
        value=data['value']
        if not isinstance(value,str) or not re.fullmatch('FAKE_[A-Za-z0-9_]{3,80}',value):raise WorkflowError('Bu sürüm yalnız FAKE_ demo değerlerini kabul eder; gerçek anahtar gönderme')
        provider=data['provider'];until=time.monotonic()+self.key_ttl_seconds
        with self.mutex:
            old=self.expiry_timers.pop(provider,None)
            if old:old.cancel()
            self.slots[provider]={'value':value,'until':until}
            timer=threading.Timer(self.key_ttl_seconds,self._expire_slot,args=(provider,until));timer.daemon=True
            self.expiry_timers[provider]=timer;timer.start()
        return {'provider':provider,'demo_slot':True,'verified':False,'expires_in_seconds':self.key_ttl_seconds,'storage':'server_ram_only'}

    def _expire_slot(self,provider,until):
        with self.mutex:
            slot=self.slots.get(provider)
            if slot and slot['until']==until:
                slot['value']=None;self.slots.pop(provider,None);self.expiry_timers.pop(provider,None)

    def key_status(self):
        with self.mutex:
            for k,v in list(self.slots.items()):
                if v['until']<=time.monotonic():
                    v['value']=None;self.slots.pop(k);timer=self.expiry_timers.pop(k,None)
                    if timer:timer.cancel()
            return {'slots':[{'provider':k,'demo_slot':True,'verified':False} for k in self.slots],'storage':'fake_only_server_ram_15min'}

    def clear_keys(self):
        with self.mutex:
            for timer in self.expiry_timers.values():timer.cancel()
            self.expiry_timers.clear()
            for value in self.slots.values():value['value']=None
            self.slots.clear()
        self.eleven.disconnect()
        self.llm.disconnect()
        return {'cleared':True}

    def export(self,key):
        with Store(self.workspace) as store,store.lock(blocking=True):return self._export_locked(key)

    def _export_locked(self,key):
        self.audio.guard(key)
        self.eleven.guard_old_timing(key)
        r=self.job(key);out=self.output(key)
        self.assert_provenance(r)
        if r['status'] not in {'prepared','checked','packaged'}:raise WorkflowError('Önce hazırlama adımını tamamla')
        files=[f for f in r['manifest'] if f!='package.zip']
        if not all(within(out,f).is_file() and file_hash(within(out,f))==r['manifest'][f] for f in files):raise WorkflowError('Çıktı değişti; hazırlama/kontrol adımını yeniden çalıştır')
        for f in files:
            if Path(f).suffix not in {'.woff2'} and scan_bytes((out/f).read_bytes()):raise WorkflowError('Paket taraması olası secret buldu; export durdu')
        fd,tmpname=tempfile.mkstemp(prefix='.package-',suffix='.tmp',dir=out)
        import os
        os.close(fd);tmp=Path(tmpname)
        try:
            with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
                for f in sorted(files):z.write(out/f,f)
            tmp.replace(out/'package.zip')
        finally:tmp.unlink(missing_ok=True)
        with zipfile.ZipFile(out/'package.zip') as z:
            if z.testzip():raise WorkflowError('ZIP doğrulaması başarısız')
        manifest=r['manifest'];manifest['package.zip']=file_hash(out/'package.zip')
        with self.connection() as db:db.execute('UPDATE dashboard_jobs SET status=?,manifest=? WHERE id=?',('packaged',canonical(manifest),key))
        return {'url':'/files/'+key+'/package.zip','status':'review_copy','paid_calls':0}

    def voice_action(self,action,data):
        if action not in {'disconnect','cancel','state'}:self.assert_runtime_current()
        if action=='connect':
            if set(data)!={'value'}:raise WorkflowError('Yalnız oturumluk anahtar alanı bekleniyor')
            return self.eleven.connect(data['value'])
        if action=='disconnect':
            if not isinstance(data.get('connection'),str) or not re.fullmatch('[a-f0-9]{32}',data['connection']):raise WorkflowError('Geçerli bağlantı kimliği gerekli')
            return self.eleven.disconnect(data['connection'])
        if action=='metadata':return self.eleven.metadata(data['connection'])
        if action=='state':
            row=self.job(data['job'])
            return {'requests':self.eleven.job_state(row['id']),**self.eleven.config()}
        if action=='cancel':
            request=self.eleven.row(data['request']);self.job(request['job'])
            return self.eleven.cancel(data['request'])
        if action=='preview':
            row=self.job(data['job']);self.assert_provenance(row)
            return self.eleven.preview(data['connection'],row['id'],row['payload']['input']['content'],
                data['tts_text'],data['voice_id'],data['model_id'])
        if action in {'approve','execute'}:
            request=self.eleven.row(data['request']);row=self.job(request['job']);self.assert_provenance(row)
            script=row['payload']['input']['content']
            if action=='approve':return self.eleven.approve(data['connection'],data['request'],script,
                data['maximum_characters'],data.get('ack_unknown_cost'),data.get('rights_confirmed'),data.get('budget'))
            return self.eleven.execute(data['connection'],data['request'],script)
        raise WorkflowError('ElevenLabs işlemi desteklenmiyor')

    def render_action(self,key,action,data):
        if set(data)!={'engine'}:raise WorkflowError('Yalnız açık engine alanı gerekli')
        if action=='render':return self.renders.start(key,data['engine'])
        if action=='render-state':return self.renders.state(key,data['engine'])
        if action=='render-cancel':return self.renders.cancel(key,data['engine'])
        if action=='edit-plan':return self.renders.edit_plan(key,data['engine'])
        raise WorkflowError('Render işlemi desteklenmiyor')

    def writing_context_action(self,action,data):
        fields={'state':{'account'},'save-sources':{'account','expected_revision','sources','rights_confirmed'},
                'accept-reference':{'account','expected_revision','reference','accepted_final_confirmed','rights_confirmed'}}
        if action not in fields or set(data)!=fields[action]:raise WorkflowError('Writing context action fields invalid')
        self.clean(data)
        if action=='state':return self.llm.contexts.state(data['account'])
        self.assert_runtime_current()
        if action=='save-sources':return self.llm.contexts.save('sources',data['account'],data['sources'],data['expected_revision'],data['rights_confirmed'])
        confirmed=data['accepted_final_confirmed'] is True and data['rights_confirmed'] is True
        return self.llm.contexts.save('canon',data['account'],data['reference'],data['expected_revision'],confirmed)

    def llm_action(self,action,data):
        fields={'connect':{'provider','value'},'disconnect':{'connection'},'metadata':{'connection'},
                'preview':{'connection','context','model','max_output_tokens'},
                'approve':{'connection','request','maximum_output_tokens','ack_unknown_cost','rights_confirmed','budget'},
                'execute':{'connection','request'},'state':{'request'},'cancel':{'request'},
                'accept':{'request','brand_identity'}}
        if action not in fields or set(data)!=fields[action]:raise WorkflowError('LLM işlem alanları geçersiz')
        if action not in {'disconnect','cancel','state'}:self.assert_runtime_current()
        if action=='connect':return self.llm.connect(data['provider'],data['value'])
        if action=='disconnect':return self.llm.disconnect(data['connection'])
        if action=='metadata':return self.llm.metadata(data['connection'])
        if action=='preview':return self.llm.preview(data['connection'],data['context'],data['max_output_tokens'],data['model'])
        if action=='approve':return self.llm.approve(data['connection'],data['request'],data['maximum_output_tokens'],data['ack_unknown_cost'],data['rights_confirmed'],data['budget'])
        if action=='execute':return self.llm.execute(data['connection'],data['request'])
        if action=='state':return self.llm.get(data['request'])
        if action=='cancel':return self.llm.cancel(data['request'])
        from .identity import normalize_identity
        identity=normalize_identity(data['brand_identity']);self.clean(identity)
        previous=self.llm.get(data['request'])
        if previous['accepted_job'] and self.job(previous['accepted_job'])['payload']['input'].get('brand_identity')!=identity:
            raise WorkflowError('Kabul edilmiş işin marka kimliği sabittir; eski iş değiştirilmedi')
        def create_job(proposal,receipt):
            account=proposal['brand'];a,f=self.account_format(account,'account-video')
            self.clean(proposal);self.clean(receipt)
            profile=render_profile(account)
            # No mutable saved-template revision in an accepted proposal's
            # identity. A crash between these two databases reuses the same job.
            template={'revision':0,'template':{'language':proposal.get('language','tr'),'tone':a['tone'],
                'visual_style':a['style'],'source_notes':'Versioned account pack; human source review pending',
                'appearance':{k:profile[k] for k in ['palette','title_size','subtitle_size']},'video':proposal}}
            value={'account':account,'format':'account-video','title':proposal['title'],'brief':proposal['brief'],
                   'content':proposal['script'],'caption':proposal['caption'],'provider':'local','model':'manual',
                   'task':'text','template_revision':0,'brand_identity':identity}
            # Only a new immutable job; voice/render/publishing require later actions.
            payload={'input':value,'account':a,'format':f,'template':template,'generation':receipt,
                'paid_calls':0 if receipt['synthetic'] else None,'execution':execution_provenance()}
            key=digest(payload)[:24]
            with self.connection() as db:
                db.execute('INSERT OR IGNORE INTO dashboard_jobs(id,payload,status,created) VALUES(?,?,?,?)',
                           (key,canonical(payload),'queued',now()))
            return key
        return self.llm.accept(data['request'],create_job)


class Handler(http.server.BaseHTTPRequestHandler):
    server_version='StoryMotionLocal/0.3'
    def log_message(self,*args):pass  # no URLs, bodies or secrets in access logs
    def local_failure(self,code,error):
        self.server.dashboard.local_log.warning(code,error)
    def headers_for(self,mime:str,length:int,*,sandbox=False)->None:
        self.send_header('Content-Type',mime);self.send_header('Content-Length',str(length))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"sandbox; default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'" if sandbox else "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=()')
    def send(self,status:int,value:object)->None:
        raw=json.dumps(value,ensure_ascii=False,allow_nan=False).encode();self.send_response(status);self.headers_for('application/json; charset=utf-8',len(raw));self.end_headers();self.wfile.write(raw)
    def send_verified_mp4(self,raw):
        # download() has verified the complete current source/receipt/hash first.
        # do_GET keeps its revision lock through the last sliced response byte.
        from .http_media import media_slice
        ranges=self.headers.get_all('Range',[])
        header=None if not ranges else ranges[0] if len(ranges)==1 else 'invalid'
        # Without an emitted validator, If-Range gets the full verified entity.
        if self.headers.get('If-Range') is not None:header=None
        status,start,stop,content_range=media_slice(raw,header)
        self.send_response(status);self.headers_for('video/mp4',stop-start)
        self.send_header('Accept-Ranges','bytes');self.send_header('Content-Disposition','inline')
        if content_range:self.send_header('Content-Range',content_range)
        self.end_headers()
        if stop>start:self.wfile.write(raw[start:stop])
    def allowed(self,write=False):
        expected=f'127.0.0.1:{self.server.server_address[1]}'
        if len(self.headers.get_all('Host',[]))!=1 or self.headers.get('Host')!=expected:return False
        if write and getattr(self.server,'_closing',False):return False
        return not write or (len(self.headers.get_all('Origin',[]))==1 and len(self.headers.get_all('X-Storymotion-Local',[]))==1 and self.headers.get('Origin')=='http://'+expected and self.headers.get('X-Storymotion-Local')=='1')
    def session_required(self):
        raw=urlparse(self.path).path
        return not (raw=='/' or re.fullmatch(r'/[a-zA-Z0-9-]+\.(?:html|js|css)',raw))
    def session_allowed(self):
        auth=getattr(self.server.dashboard,'session_auth',None)
        return bool(auth is not None and auth.authenticated(self.headers,self.server.server_address[1]))
    def do_GET(self):
        if not self.allowed():self.send(403,{'error':'Loopback host required'});return
        if self.session_required() and not self.session_allowed():self.send(401,{'error':'LOCAL_SESSION_REQUIRED'});return
        try:path=request_path(self.path)
        except WorkflowError as error:self.send(400,{'error':str(error)});return
        # Decode before choosing the revision lock; encoded download routes
        # receive the same lock and final rechecks as their canonical form.
        if path.startswith(('/files/','/render-files/','/review-files/','/series-files/','/family-files/','/family-render-files/')):
            with self.server.dashboard.revision_lock:return self._get(path)
        return self._get(path)
    def _get(self,path=None):
        if not self.allowed():self.send(403,{'error':'Loopback host required'});return
        if self.session_required() and not self.session_allowed():self.send(401,{'error':'LOCAL_SESSION_REQUIRED'});return
        d=self.server.dashboard
        try:
            path=request_path(self.path) if path is None else path
            parts=path.strip('/').split('/')
            if parts[:2] in (['api','reference-catalog'],['api','style-gallery']):
                origins=self.headers.get_all('Origin',[])
                if getattr(self.server,'_closing',False) or origins and (len(origins)!=1 or origins[0]!='http://127.0.0.1:'+str(self.server.server_address[1])):
                    self.send(403,{'error':'Same-origin active local session required'});return
            if parts[:2]==['api','family-renders'] or parts[0]=='family-render-files':
                origins=self.headers.get_all('Origin',[])
                if getattr(self.server,'_closing',False) or origins and (len(origins)!=1 or origins[0]!='http://127.0.0.1:'+str(self.server.server_address[1])):
                    self.send(403,{'error':'Same-origin active local session required'});return
                if parts[:2]==['api','family-renders']:
                    if len(parts)==4:self.send(200,d.family_renders.state(parts[2],parts[3]));return
                    if len(parts)==6 and parts[4]=='attempts':self.send(200,d.family_renders.state(parts[2],parts[3],parts[5]));return
                elif len(parts)==5:
                    name,raw=d.family_renders.download(parts[1],parts[2],parts[3],parts[4])
                    self.send_verified_mp4(raw);return
                raise WorkflowError('FAMILY_RENDER_ROUTE_INVALID')
            if parts[:2]==['api','family-jobs'] or parts[0]=='family-files':
                origins=self.headers.get_all('Origin',[])
                if getattr(self.server,'_closing',False) or origins and (len(origins)!=1 or origins[0]!='http://127.0.0.1:'+str(self.server.server_address[1])):
                    self.send(403,{'error':'Same-origin active local session required'});return
                history=d.template_studio.history
                if parts[:2]==['api','family-jobs']:
                    if len(parts)==3:self.send(200,history.listing(parts[2]));return
                    if len(parts)==4:self.send(200,history.detail(parts[2],parts[3]));return
                elif len(parts) in (4,5) and (len(parts)==4 or parts[4]=='view'):
                    if not re.fullmatch(r'[a-f0-9]{64}',parts[3]):raise WorkflowError('FAMILY_RECORD_UNAVAILABLE')
                    name,raw=history.detail(parts[1],parts[2],parts[3],view=len(parts)==5)
                    view=len(parts)==5
                    self.send_response(200);self.headers_for('image/svg+xml' if view else 'application/octet-stream',len(raw),sandbox=True)
                    self.send_header('Content-Disposition',('inline' if view else 'attachment')+'; filename="'+name+'"')
                    self.end_headers();self.wfile.write(raw);return
                raise WorkflowError('FAMILY_ROUTE_INVALID')
            response=json_get(d,path,ui_revision=UI_REVISION,
                              current_provenance=execution_provenance,capabilities=public_capabilities)
            if response is not None:self.send(*response);return
            parts=path.strip('/').split('/')
            if len(parts)==4 and parts[0]=='series-files' and parts[3]=='episode-package.zip':
                raw=d.series.download(parts[1],parts[2])
                self.send_response(200);self.headers_for('application/zip',len(raw));self.send_header('Content-Disposition','attachment');self.end_headers();self.wfile.write(raw);return
            if len(parts)==4 and parts[0]=='review-files':
                raw=d.reviews.download(parts[1],parts[2],parts[3])
                self.send_response(200);self.headers_for(mimetypes.guess_type(parts[3])[0] or 'application/octet-stream',len(raw));self.end_headers();self.wfile.write(raw);return
            if len(parts)==3 and parts[0]=='llm-files':
                raw=d.llm.download(parts[1],parts[2])
                self.send_response(200);self.headers_for('application/json; charset=utf-8',len(raw));self.send_header('Content-Disposition','attachment');self.end_headers();self.wfile.write(raw);return
            if len(parts)==4 and parts[0]=='render-files':
                raw=d.renders.download(parts[1],parts[2],parts[3])
                if parts[3] in {'render-1080.mp4','render-mobile.mp4'}:self.send_verified_mp4(raw);return
                mime=mimetypes.guess_type(parts[3])[0] or 'application/octet-stream'
                self.send_response(200);self.headers_for(mime,len(raw));self.send_header('Content-Disposition','attachment');self.end_headers();self.wfile.write(raw);return
            if len(parts)==4 and parts[:2]==['voice-files','elevenlabs']:
                raw=d.eleven.download(parts[2],parts[3])
                mime='audio/mpeg' if parts[3].endswith('.mp3') else 'application/json' if parts[3].endswith('.json') else 'text/plain; charset=utf-8'
                self.send_response(200);self.headers_for(mime,len(raw));self.send_header('Content-Disposition','attachment');self.end_headers();self.wfile.write(raw);return
            if len(parts)==4 and parts[:2]==['api','template']:self.send(200,d.template(parts[2],parts[3]));return
            if len(parts)==3 and parts[:2]==['api','jobs']:self.send(200,d.job(parts[2]));return
            if len(parts)==3 and parts[0]=='files':
                r=d.job(parts[1]);name=parts[2]
                d.audio.guard(parts[1])
                if name=='package.zip':d.eleven.guard_old_timing(parts[1])
                if name not in r['files']:raise WorkflowError('Dosya bu işte erişilebilir değil')
                file=within(d.output(parts[1]),name)
            else:
                file=within(ROOT/'dashboard','index.html' if path=='/' else path.lstrip('/'))
                if file.suffix not in {'.html','.js','.css'}:raise WorkflowError('Dosya desteklenmiyor')
            if not file.is_file():self.send(404,{'error':'Bulunamadı'});return
            raw=file.read_bytes()
            if len(parts)==3 and parts[0]=='files' and hashlib.sha256(raw).hexdigest()!=r['manifest'][parts[2]]:
                raise WorkflowError('Dosya hash doğrulaması başarısız; indirme durdu. Kaynağı yeniden hazırla/kontrol et')
            mime=mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
            self.send_response(200);self.headers_for(mime,len(raw));self.end_headers();self.wfile.write(raw)
        except WorkflowError as ex:self.send(400,{'error':str(ex)})
        except (OSError,sqlite3.Error,ValueError,KeyError,TypeError,RuntimeError) as error:
            self.local_failure('LOCAL_READ_FAILED',error)
            self.send(500,{'error':'Yerel okuma tamamlanmadı; değerler günlüğe yazılmadı'})
    def do_POST(self):
        if not self.allowed(True):self.send(403,{'error':'Same-origin local request required'});return
        with self.server.dashboard.action_lock:self._post()
    def _post(self):
        if not self.allowed(True):self.send(403,{'error':'Same-origin local request required'});return
        try:
            if urlparse(self.path).path!='/api/bootstrap' and not self.session_allowed():self.send(401,{'error':'LOCAL_SESSION_REQUIRED'});return
            path=request_path(self.path)
            bootstrap=path=='/api/bootstrap'
            length=int(self.headers.get('Content-Length','0'))
            from .local_audio import MAX_IMPORT_BODY
            local_upload=re.fullmatch(r'/api/jobs/[a-f0-9]{24}/audio-import',urlparse(self.path).path) is not None
            from .raster_revision import MAX_RASTER_BODY
            raster_upload=re.fullmatch(r'/api/jobs/[a-f0-9]{24}/raster-import',urlparse(self.path).path) is not None
            maximum=MAX_RASTER_BODY if raster_upload else MAX_IMPORT_BODY if local_upload else 120000
            if not 0<length<=maximum or self.headers.get('Content-Type','').split(';')[0]!='application/json':raise WorkflowError('Bounded JSON required')
            data=json.loads(self.rfile.read(length));d=self.server.dashboard
            if not isinstance(data,dict):raise WorkflowError('JSON object required')
            if bootstrap:
                values=self.headers.get_all('X-Storymotion-Token',[])
                cookie=d.session_auth.bootstrap(values[0] if len(values)==1 and data=={} else None,self.server.server_address[1])
                if cookie is None:self.send(401,{'error':'LOCAL_SESSION_REQUIRED'});return
                raw=b'{"ok":true}'
                self.send_response(200);self.headers_for('application/json; charset=utf-8',len(raw));self.send_header('Set-Cookie',cookie);self.end_headers();self.wfile.write(raw);return
            if path=='/api/jobs':result=d.enqueue(data)
            elif path=='/api/template':result=d.save_template(data)
            elif path=='/api/template-families/prepare':result=d.template_studio.prepare(data)
            elif path in ('/api/template-families/fields','/api/template-families/validate'):
                result=d.template_studio.field_action(path.rsplit('/',1)[1],data)
            elif path.startswith('/api/family-renders/'):
                parts=path.strip('/').split('/')
                if len(parts)!=5:raise WorkflowError('FAMILY_RENDER_ROUTE_INVALID')
                result=d.family_renders.action(parts[2],parts[3],parts[4],data)
            elif path.startswith('/api/taxonomy/') and len(path.strip('/').split('/'))==3:
                result=d.taxonomy.action(path.rsplit('/',1)[1],data)
            elif path=='/api/keys':result=d.demo_key(data)
            elif path=='/api/keys/clear':result=d.clear_keys()
            elif path=='/api/worker/run-once':result=d.start_worker_once()
            elif path.startswith('/api/series/') and len(path.strip('/').split('/'))==3:
                result=d.series.action(path.rsplit('/',1)[1],data)
            elif path.startswith('/api/elevenlabs/') and len(path.strip('/').split('/'))==3:
                result=d.voice_action(path.rsplit('/',1)[1],data)
            elif path.startswith('/api/writing-context/') and len(path.strip('/').split('/'))==3:
                result=d.writing_context_action(path.rsplit('/',1)[1],data)
            elif path.startswith('/api/llm/') and len(path.strip('/').split('/'))==3:
                result=d.llm_action(path.rsplit('/',1)[1],data)
            else:
                parts=path.strip('/').split('/')
                if len(parts)!=4 or parts[:2]!=['api','jobs']:self.send(404,{'error':'Bulunamadı'});return
                key,action=parts[2:]
                if action=='prepare':result=d.prepare(key)
                elif action=='audio-bind':result=d.audio.bind_voice(key,data)
                elif action=='audio-import':
                    from .local_audio import import_local
                    result=import_local(d,key,data)
                elif action=='scene-plan-template':result=d.plans.template(key)
                elif action=='rig-template':result=d.rigs.template(key)
                elif action=='rig-import':result=d.rigs.create(key,data)
                elif action=='scene-plan':result=d.plans.create(key,data)
                elif action=='raster-import':result=d.raster.import_local(key,data)
                elif action=='scene-revise':result=d.edits.create(key,data)
                elif action=='check':result=d.check(key)
                elif action=='export':result=d.export(key)
                elif action=='budget':result=d.budget(key,data)
                elif action in {'render','render-state','render-cancel','edit-plan'}:result=d.render_action(key,action,data)
                elif action in {'review-create','review-state','review-issue','review-resolve','review-recheck'}:result=d.reviews.action(key,action,data)
                else:raise WorkflowError('Live dispatch, render veya yayın bu dashboard sürümünde kapalı')
            self.send(200,result)
        except (WorkflowError,ValueError,KeyError,TypeError,RecursionError,OverflowError) as ex:
            self.send(400,{'error':str(ex) if isinstance(ex,WorkflowError) else 'Geçersiz girdi; değerler kaydedilmedi'})
        except (OSError,sqlite3.Error,RuntimeError) as error:
            self.local_failure('LOCAL_WRITE_FAILED',error)
            self.send(500,{'error':'Yerel işlem tamamlanmadı; gizli değer günlüğe yazılmadı'})


class LocalDashboardServer(http.server.ThreadingHTTPServer):
    # Closing the listener must not release the workspace while an HTTP worker
    # can still mutate it or write previously authorized response bytes.
    daemon_threads=False
    block_on_close=True
    def __init__(self,*args,**kwargs):
        # Initialize before the base constructor, whose failure cleanup may
        # call server_close. Never lazily create competing close mutexes.
        self._close_lock=threading.Lock()
        super().__init__(*args,**kwargs)
    @property
    def dashboard_url(self):return self.dashboard.session_auth.launch_url(self.server_address[1])
    def get_request(self):
        connection,address=super().get_request();connection.settimeout(30);return connection,address
    def handle_error(self,request,client_address):
        # Never let stdlib print raw exception values or request data.
        import sys
        d=getattr(self,'dashboard',None)
        if d is not None:d.local_log.warning('LOCAL_HTTP_FAILED',sys.exc_info()[1])
    def server_close(self):
        # stdlib _Threads.join empties its list before waiting. Only the
        # serialized drain owner may observe completion and release flock.
        with self._close_lock:
            if getattr(self,'_close_complete',False):return
            self._closing=True
            if getattr(self,'_http_drain_failed',False):
                raise WorkflowError('DASHBOARD_HTTP_DRAIN_INCOMPLETE: HTTP işçileri doğrulanamadı; workspace kilidi süreç bitene kadar korunuyor')
            try:super().server_close()  # close socket and drain non-daemon HTTP workers
            except BaseException:
                # join may have consumed its thread list before interruption;
                # a later close must not treat that list as a successful drain.
                self._http_drain_failed=True
                raise
            d=getattr(self,'dashboard',None)
            if d:
                d.clear_keys();d.renders.close();threads=[]
                family=getattr(d,'family_renders',None)
                if family:
                    family.close()
                    with family.lock:threads.extend(t for _,t,_,_ in family.active.values())
                for service in (d.eleven,d.llm):
                    with service.lock:threads.extend(service.threads.values())
                for thread in threads:
                    if thread is not threading.current_thread():thread.join(1)
                with d.renders.lock:threads.extend(t for _,t in d.renders.active.values())
                if d.worker_lock.locked() or any(t.is_alive() for t in threads):
                    # Fail closed. Keep the descriptor until a later successful
                    # close or process exit; never permit overlapping writers.
                    raise WorkflowError('DASHBOARD_BACKGROUND_WORK_ACTIVE: Sunucu kapandı fakat workspace kilidi işçiler bitene kadar korunuyor; sonra server_close tekrar çağrılabilir')
            if d:
                reviews=getattr(d,'reviews',None)
                if reviews:reviews.close()
                auth=getattr(d,'session_auth',None)
                if auth:auth.close()
                close_log=getattr(d,'close_local_log',None)
                if close_log:close_log()
            guard=getattr(self,'instance_guard',None)
            if guard:guard.close()
            self._close_complete=True


def make_server(workspace:Union[str,Path]='work',port:int=4397,hf:Optional[Union[str,Path]]=None,
                elevenlabs_mode:Literal['off','demo','live']='off',
                llm_mode:Literal['off','demo','live']='off')->LocalDashboardServer:
    from .instance_guard import WorkspaceInstance
    guard=WorkspaceInstance(workspace).acquire();server=None
    try:
        server=LocalDashboardServer(('127.0.0.1',port),Handler,bind_and_activate=False)
        server.instance_guard=guard
        server.dashboard=Dashboard(guard.root,hf,elevenlabs_mode=elevenlabs_mode,llm_mode=llm_mode)
        server.dashboard.local_log  # configure owned diagnostics before accepting requests
        server.server_bind();server.server_activate();return server
    except Exception:
        if server:server.server_close()
        else:guard.close()
        raise


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',default='work');parser.add_argument('--port',type=int,default=4397);parser.add_argument('--hf')
    parser.add_argument('--elevenlabs',choices=['off','demo','live'],default='off',help='Explicit live network requires own key and per-request UI approval; demo is synthetic only')
    parser.add_argument('--llm',choices=['off','demo','live'],default='off',help='Registered text-adapter session BYOK; live requires explicit per-request approval; demo is synthetic')
    args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error('Port must be 1024–65535')
    try:server=make_server(args.workspace,args.port,args.hf,args.elevenlabs,args.llm)
    except WorkflowError as ex:parser.exit(2,str(ex)+'\n')
    print(f'Dashboard: {server.dashboard_url} · ElevenLabs mode: {args.elevenlabs}; LLM mode: {args.llm}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
