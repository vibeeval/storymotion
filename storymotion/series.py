"""Explicit, local episode references and manual next-episode drafts.

An attestation is a continuation reference, never publication/semantic QA.
No provider, URL fetch, voice generation or private story bible is involved.
"""
import copy
import io
import json
import zipfile
from .security import WorkflowError, canonical, digest, file_hash
from .store import now
from .writing_context import canon, ident, revision, snapshot, text, validate_binding, bound_brief

from .account_packs import is_serial
WARNING = 'Yalnız açıkça kabul edilen devam referansı. Anlam, olay çözümü, doğal ses ve yayın QA otomatik doğrulanmaz; desteklenen zarf vektör ailesi kullanılır.'


class Series:
    def __init__(self, dashboard):
        self.d = dashboard
        with self.d.connection() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS series_episodes(revision TEXT PRIMARY KEY,series TEXT NOT NULL,
                episode TEXT NOT NULL,ordinal INTEGER NOT NULL,job TEXT NOT NULL,record TEXT NOT NULL,
                UNIQUE(series,episode),UNIQUE(series,ordinal));
              CREATE TABLE IF NOT EXISTS series_heads(series TEXT PRIMARY KEY,revision TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS series_drafts(revision TEXT PRIMARY KEY,previous TEXT NOT NULL,
                child TEXT NOT NULL UNIQUE,record TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS series_draft_heads(previous TEXT PRIMARY KEY,revision TEXT NOT NULL);
            ''')

    def _head(self, db, series):
        r = db.execute('SELECT revision FROM series_heads WHERE series=?', (series,)).fetchone()
        return r[0] if r else None

    def _draft_head(self, db, previous):
        r = db.execute('SELECT revision FROM series_draft_heads WHERE previous=?', (previous,)).fetchone()
        return r[0] if r else None

    def _episode(self, db, key):
        revision(key)
        if key is None: raise WorkflowError('SERIES_REFERENCE_MISSING: Önce kabul edilmiş bölüm seçin')
        r = db.execute('SELECT * FROM series_episodes WHERE revision=?', (key,)).fetchone()
        if not r: raise WorkflowError('SERIES_REFERENCE_MISSING: Kabul edilmiş bölüm bulunamadı')
        data = json.loads(r['record'])
        if digest(data) != key or data['canon']['data']['series_id'] != r['series'] or data['canon']['data']['episode_id'] != r['episode'] or data['ordinal'] != r['ordinal'] or data['job'] != r['job']:
            raise WorkflowError('SERIES_REFERENCE_CHANGED: Kayıt bağı doğrulanamadı')
        return data

    def _verify_episode(self, key):
        with self.d.connection() as db: record = self._episode(db, key)
        before, _, master = self.d.reviews.verified_render(record['job'], record['engine'])
        if before != record['render_binding'] or file_hash(master) != record['canon']['data']['final_sha256']:
            raise WorkflowError('SERIES_FINAL_CHANGED: Önceki kabul edilmiş final değişti veya eksik')
        row = self.d.job(record['job'])
        if digest(row['payload']) != record['job_payload_sha256']:
            raise WorkflowError('SERIES_SOURCE_CHANGED: Önceki bölüm kaynağı değişti')
        return record

    def _video(self, job):
        row = self.d.job(job); self.d.assert_provenance(row)
        if not is_serial(row['payload']['account']['id']) or row['payload']['format']['adapter'] != 'account-pack':
            raise WorkflowError('SERIES_PROFILE_REQUIRED: Bu adım yalnız gizemli hikâyeler konu animatiği içindir')
        return row, self.d.renders.video_input(row)

    def reference_template(self, job, engine):
        with self.d.revision_lock:
            row, video = self._video(job)
            binding, _, _ = self.d.reviews.verified_render(job, engine)
            context = validate_binding(video.get('production_context'), video['brand'])
            previous = row['payload'].get('series_revision')
            with self.d.connection() as db:
                if previous:
                    rec = self._episode(db, previous['previous_revision']); old = rec['canon']['data']
                    head = self._head(db, old['series_id']); ordinal = rec['ordinal'] + 1
                else:
                    old = context['canon']['data'] if context and context['canon'] else None
                    head = None; ordinal = 1
            primary = video['continuity']['object_id']
            candidate = copy.deepcopy(old) if old else {
                'series_id':'my-series','episode_id':'episode-01','bible_version':'customer-bible-1',
                'origin':'customer_attested_final','narrator':'first_person',
                'cast':[{k:c[k] for k in ('id','wardrobe')} for c in video['creative']['characters']],
                'objects':[{'id':primary,'state':video['continuity']['next'],'identity_note':'Müşterinin aynı nesne kimliği; elle doğrulanmalıdır.'}],
                'open_clues':[]}
            if previous: candidate['episode_id'] = 'episode-' + str(ordinal).zfill(2)
            candidate.update(final_sha256=binding['render_sha256'], accepted_by='operator',
                             source_revision=context['sources']['revision'] if context and context['sources'] else None)
            for obj in candidate['objects']:
                if obj['id'] == primary: obj['state'] = video['continuity']['next']
            return {'job':job,'engine':engine,'canon':candidate,'expected_head':head,'ordinal':ordinal,
                    'final_sha256':binding['render_sha256'],'warning':WARNING}

    def _accept_candidate(self, data):
        required = {'job','engine','expected_head','ordinal','canon','accepted_by','rights_confirmed','reference_only'}
        if set(data) != required or data['rights_confirmed'] is not True or data['reference_only'] is not True:
            raise WorkflowError('SERIES_ATTESTATION_REQUIRED: Hak ve yalnız devam referansı onayı gerekli')
        if type(data['ordinal']) is not int or not 1 <= data['ordinal'] <= 10000: raise WorkflowError('SERIES_ORDINAL_INVALID')
        revision(data['expected_head']); approver = text(data['accepted_by'], 120)
        row, video = self._video(data['job']); self.d.clean(data)
        binding, _, master = self.d.reviews.verified_render(data['job'], data['engine'])
        c = canon(data['canon'])
        context = validate_binding(video.get('production_context'), video['brand'])
        if c['final_sha256'] != binding['render_sha256'] or c['accepted_by'] != approver or c['source_revision'] != (context['sources']['revision'] if context and context['sources'] else None):
            raise WorkflowError('SERIES_FINAL_BINDING_CHANGED: Exact final, onaylayan ve kaynak sürümü gerekli')
        actual_cast = [{k:r[k] for k in ('id','wardrobe')} for r in video['creative']['characters']]
        objects = {o['id']:o for o in c['objects']}; primary = video['continuity']['object_id']
        if c['cast'] != actual_cast or primary not in objects or objects[primary]['state'] != video['continuity']['next']:
            raise WorkflowError('SERIES_CANON_CONFLICT: Karakter, kıyafet veya son nesne durumu finalle çelişiyor')
        b = row['payload'].get('series_revision')
        previous = b['previous_revision'] if b else None
        if previous != data['expected_head'] or (b and data['ordinal'] != b['ordinal']) or (not b and data['ordinal'] != 1):
            raise WorkflowError('SERIES_PREVIOUS_CONFLICT: Önceki bölüm/numara değişti')
        return row, c, context, binding, master, previous

    def accept(self, data):
        with self.d.revision_lock:
            row, c, context, binding, master, previous = self._accept_candidate(data)
            if previous:
                rec = self._verify_episode(previous)
                if rec['canon']['data']['series_id'] != c['series_id'] or rec['canon']['data']['bible_version'] != c['bible_version']:
                    raise WorkflowError('SERIES_BIBLE_CONFLICT: Seri/bible sürümü sessizce değiştirilemez')
            record = {'schema_version':1,'job':data['job'],'engine':data['engine'],'ordinal':data['ordinal'],
                      'previous_revision':previous,'job_payload_sha256':digest(row['payload']),
                      'render_binding':binding,'sources':copy.deepcopy(context['sources']) if context else None,
                      'canon':snapshot('canon', row['payload']['account']['id'], c, rec['canon']['revision'] if previous else None),
                      'draft_revision':row['payload'].get('series_revision',{}).get('draft_revision'),
                      'attestation':'operator_continuation_reference_only','human_qa':'incomplete','publication_ready':False}
            key = digest(record)
            with self.d.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                if self._head(db, c['series_id']) != previous:
                    # An exact successful retry remains idempotent; nothing else can overwrite canon.
                    existing = db.execute('SELECT record FROM series_episodes WHERE revision=?', (key,)).fetchone()
                    if existing and existing[0] == canonical(record): return {'revision':key,'record':record,'status':'accepted_reference','publication_ready':False,'reused':True}
                    raise WorkflowError('SERIES_HEAD_CHANGED: Yeni kabul var; önceki seçimi yenileyin')
                again, _, _ = self.d.reviews.verified_render(data['job'], data['engine'])
                if again != binding or file_hash(master) != c['final_sha256']: raise WorkflowError('SERIES_FINAL_CHANGED_DURING_ACCEPT')
                if db.execute('SELECT 1 FROM series_episodes WHERE series=? AND (episode=? OR ordinal=?)',(c['series_id'],c['episode_id'],data['ordinal'])).fetchone():
                    raise WorkflowError('SERIES_EPISODE_ALREADY_ACCEPTED: Kabul edilmiş bölüm yeniden yazılamaz')
                db.execute('INSERT INTO series_episodes VALUES(?,?,?,?,?,?)',(key,c['series_id'],c['episode_id'],data['ordinal'],data['job'],canonical(record)))
                db.execute('INSERT INTO series_heads VALUES(?,?) ON CONFLICT(series) DO UPDATE SET revision=excluded.revision',(c['series_id'],key))
            return {'revision':key,'record':record,'status':'accepted_reference','publication_ready':False,'reused':False}

    def state(self, query=None):
        self.d.assert_runtime_current()
        from .series_history import state
        return {**state(self, {} if query is None else query), 'warning':WARNING}

    def draft_template(self, previous):
        with self.d.revision_lock:
            r = self._verify_episode(previous)
            with self.d.connection() as db:
                if self._head(db,r['canon']['data']['series_id']) != previous: raise WorkflowError('SERIES_STALE_PREVIOUS: Güncel kabul edilmiş bölümü seçin')
                expected = self._draft_head(db, previous)
            _, source = self._video(r['job'])
            from .creative import output_schema
            video = {k:copy.deepcopy(source[k]) for k in output_schema(source['brand'])['properties']}
            video['creative'].pop('audit',None)
            video.update(audio=None,alignment='provisional_silent',title='Yeni bölüm taslağı',brief='Elle yazılan devam planı; yeni ses, timing ve insan incelemesi bekliyor.')
            # Preserve the reference, but do not invent a new story, voice or timestamps.
            video['continuity']['previous'] = next(o['state'] for o in r['canon']['data']['objects'] if o['id']==video['continuity']['object_id'])
            video['scenes'][0]['object_before'] = video['continuity']['previous']
            return {'video':video,'expected_draft':expected,'previous_revision':previous,'next_ordinal':r['ordinal']+1,
                    'warning':WARNING+' Eski metin örnek olarak gösterilir; yeni bölümün senaryo, cue ve sahnelerini birlikte düzenleyin. Aynı metin yeni bölüm olamaz.'}

    def draft(self, data):
        required = {'previous_revision','expected_draft','video','continuation_note','approved_by','rights_confirmed','review_pending'}
        if set(data) != required or data['rights_confirmed'] is not True or data['review_pending'] is not True: raise WorkflowError('SERIES_DRAFT_CONSENT_REQUIRED')
        revision(data['expected_draft']); note=text(data['continuation_note'],1000); approver=text(data['approved_by'],200);self.d.clean(data)
        with self.d.revision_lock:
            previous=data['previous_revision']; rec=self._verify_episode(previous); old=self.d.job(rec['job'])
            ctx={'schema_version':1,'account':old['payload']['account']['id'],'sources':copy.deepcopy(rec['sources']),'canon':copy.deepcopy(rec['canon'])};ctx['binding_sha256']=digest(ctx)
            video=bound_brief(old['payload']['account']['id'],data['video'],ctx)
            if ' '.join(video['script'].split()).casefold() == ' '.join(old['payload']['input']['content'].split()).casefold(): raise WorkflowError('SERIES_SCRIPT_REUSED: Eski senaryo yeni bölüm değildir')
            from .engine import prepare_input
            prepare_input(video)
            record={'schema_version':1,'previous_revision':previous,'previous_final_sha256':rec['canon']['data']['final_sha256'],
                    'canon_revision':rec['canon']['revision'],'sources_revision':rec['sources']['revision'] if rec['sources'] else None,
                    'ordinal':rec['ordinal']+1,'video':video,'continuation_note':note,'approved_by':approver,
                    'execution_fingerprint':self.d.runtime_execution,'review_pending':True}
            key=digest(record)
            p=copy.deepcopy(old['payload'])
            for name in ('audio_revision','edit_revision','raster_revision','scene_plan_revision','rig_revision','series_revision'):p.pop(name,None)
            p['input'].update(title=video['title'],brief=video['brief'],content=video['script'],caption=video['caption'],provider='local',model='manual',template_revision=0)
            p['template']={'revision':0,'template':{**p['template']['template'],'video':video}}
            p.update(generation='manual_serial_draft_no_provider',paid_calls=0,
                     series_revision={'draft_revision':key,'previous_revision':previous,'ordinal':record['ordinal']})
            child=digest(p)[:24]
            with self.d.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                if self._head(db,rec['canon']['data']['series_id']) != previous: raise WorkflowError('SERIES_STALE_PREVIOUS: Güncel kabul edilmiş bölümü seçin')
                current=self._draft_head(db,previous)
                if current==key:
                    saved=db.execute('SELECT child,record FROM series_drafts WHERE revision=?',(key,)).fetchone()
                    if saved and saved['child']==child and saved['record']==canonical(record) and digest(self.d.job(child)['payload'])==digest(p):
                        return {'child_job':child,'parent_job':rec['job'],'previous_revision':previous,'draft_revision':key,'publication_ready':False,'status':'draft_pending','reused':True}
                    raise WorkflowError('SERIES_DRAFT_CHANGED')
                if current!=data['expected_draft']:raise WorkflowError('SERIES_DRAFT_HEAD_CHANGED: Başka taslak kaydedildi; önce yenileyin')
                if db.execute('SELECT 1 FROM series_drafts WHERE revision=?',(key,)).fetchone():raise WorkflowError('SERIES_DRAFT_SUPERSEDED: Eski taslak sessizce yeniden etkinleştirilemez')
                self._verify_episode(previous)
                db.execute('INSERT INTO dashboard_jobs(id,payload,status,created) VALUES(?,?,?,?)',(child,canonical(p),'queued',now()))
                db.execute('INSERT INTO series_drafts VALUES(?,?,?,?)',(key,previous,child,canonical(record)))
                db.execute('INSERT INTO series_draft_heads VALUES(?,?) ON CONFLICT(previous) DO UPDATE SET revision=excluded.revision',(previous,key))
            return {'child_job':child,'parent_job':rec['job'],'previous_revision':previous,'draft_revision':key,'publication_ready':False,'status':'draft_pending','reused':False}

    def guard(self, row):
        b=row['payload'].get('series_revision')
        if not b:return
        if set(b)!={'draft_revision','previous_revision','ordinal'}:raise WorkflowError('SERIES_BINDING_INVALID')
        with self.d.connection() as db:
            r=db.execute('SELECT * FROM series_drafts WHERE revision=?',(b['draft_revision'],)).fetchone()
            if not r:raise WorkflowError('SERIES_DRAFT_MISSING')
            record=json.loads(r['record']);previous=self._episode(db,b['previous_revision'])
            if record['execution_fingerprint']!=self.d.runtime_execution:raise WorkflowError('SERIES_EXECUTION_CHANGED')
            accepted=db.execute('SELECT revision FROM series_episodes WHERE json_extract(record,\'$.draft_revision\')=?',(b['draft_revision'],)).fetchone()
            if digest(record)!=b['draft_revision'] or r['previous']!=b['previous_revision'] or record['ordinal']!=b['ordinal'] or record['previous_final_sha256']!=previous['canon']['data']['final_sha256'] or record['canon_revision']!=previous['canon']['revision']:
                raise WorkflowError('SERIES_DRAFT_BINDING_CHANGED')
            if not accepted and (self._draft_head(db,b['previous_revision'])!=b['draft_revision'] or self._head(db,previous['canon']['data']['series_id'])!=b['previous_revision']):raise WorkflowError('SERIES_DRAFT_SUPERSEDED: Yeni taslak/kabul eski onay ve exportu geçersiz kıldı')
        # Check the pinned previous bytes without recursively rebuilding the entire episode chain.
        # Full selected-job/receipt reconstruction also runs on draft, accept and export.
        from .local_state import guard_control
        previous_master=guard_control(self.d.workspace,'renders/'+previous['render_binding']['engine_job']+'/render-1080.mp4')
        if not previous_master.is_file() or file_hash(previous_master)!=previous['canon']['data']['final_sha256']:raise WorkflowError('SERIES_PREVIOUS_FINAL_CHANGED')
        root=self.d.job(r['child']);expected=root['payload'].get('series_revision')
        if digest(root['payload'])[:24]!=r['child'] or expected!=b or canonical(root['payload']['template']['template']['video'])!=canonical(record['video']):raise WorkflowError('SERIES_DRAFT_PAYLOAD_CHANGED')
        # Existing revision guards validate their own timing/asset/current-head bindings.
        # Here additionally require a hash-bound parent chain back to this serial draft.
        cursor=row;seen=set()
        while cursor['id']!=r['child']:
            if cursor['id'] in seen or len(seen)>=24 or digest(cursor['payload'])[:24]!=cursor['id']:raise WorkflowError('SERIES_LINEAGE_INVALID')
            seen.add(cursor['id']);binding=next((cursor['payload'][n] for n in ('edit_revision','scene_plan_revision','raster_revision','rig_revision','audio_revision') if cursor['payload'].get(n)),None)
            if not binding:raise WorkflowError('SERIES_LINEAGE_MISSING')
            parent=self.d.job(binding['parent_job'])
            if digest(parent['payload'])!=binding['parent_payload_sha256']:raise WorkflowError('SERIES_LINEAGE_CHANGED')
            cursor=parent

    def download(self, job, engine):
        with self.d.revision_lock:
            row, _=self._video(job); b=row['payload'].get('series_revision')
            if not b:raise WorkflowError('SERIES_DRAFT_REQUIRED')
            rec=self._verify_episode(b['previous_revision']);before=self.d.reviews.verified_render(job,engine)[0]
            raw=self.d.renders.download(job,engine,'delivery.zip')
            manifest={'schema_version':1,'job':job,'engine':engine,'series_revision':b,'previous_episode':rec,
                      'current_render_binding':before,'delivery_sha256':__import__('hashlib').sha256(raw).hexdigest(),
                      'status':'draft_pending','human_qa':'incomplete','publication_ready':False}
            output=io.BytesIO()
            with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
                z.writestr('episode-delivery.zip',raw);z.writestr('series-reference.json',canonical(manifest)+'\n')
            self.d.assert_provenance(self.d.job(job));self._verify_episode(b['previous_revision'])
            if self.d.reviews.verified_render(job,engine)[0]!=before:raise WorkflowError('SERIES_EXPORT_CHANGED: Hiçbir byte teslim edilmedi')
            return output.getvalue()

    def action(self, action, data):
        with self.d.revision_lock:
            self.d.assert_runtime_current()
            if action=='state':return self.state(data)
            if action=='reference-template' and set(data)=={'job','engine'}:return self.reference_template(data['job'],data['engine'])
            if action=='draft-template' and set(data)=={'previous_revision'}:return self.draft_template(data['previous_revision'])
            if action=='accept':return self.accept(data)
            if action=='draft':return self.draft(data)
            raise WorkflowError('SERIES_ACTION_INVALID')
