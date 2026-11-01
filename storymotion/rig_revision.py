from .local_state import private_directory, write_private, copy_private
from .account_packs import capability
"""Explicit manual, fresh audio-bound rig revisions; no phoneme extraction."""
import copy
import json
import os
import shutil
import tempfile
from pathlib import Path
from .security import WorkflowError,canonical,digest,file_hash,write_json
from .store import now

RIG_TIMING_MARKER={'status':'manual_track_pending_review','reason':'Separate fresh audio-bound rig track; phonetic and perceptual acceptance pending'}


def rig_camera_operations(operations):
    """The serial scene's owned 900px SVG starts at global y=550."""
    value=copy.deepcopy(operations)
    for op in value:
        groups=[op['values']] if op['op']=='set' else [op['before'],op['after']]
        for group in groups:
            if 'svgOrigin' in group:
                x,y=map(float,group['svgOrigin'].split());group['svgOrigin']=format(x,'g')+' '+format(y+550,'g')
    return value


def rig_camera_program(scene):
    """One global courier camera resets at each scene, including reverse seek."""
    ops=rig_camera_operations(scene['camera_motion']);initial={'x':0,'y':0,'scale':1,'rotation':0,'svgOrigin':'540 1000'}
    for op in ops:
        if op['op']=='set':initial.update(op['values'])
    lines=[]
    if scene['start']==0:lines.append('gsap.set("#rig-camera",'+json.dumps(initial)+');')
    lines.append('tl.set("#rig-camera",'+json.dumps(initial)+','+str(scene['start'])+');')
    for op in ops:
        if op['op']=='tween':
            after=dict(op['after'],duration=op['duration'],ease='power2.inOut',immediateRender=False)
            lines.append('tl.fromTo("#rig-camera",'+json.dumps(op['before'])+','+json.dumps(after)+','+str(scene['start']+op['offset'])+');')
    return ''.join(lines)


def rig_timing(brief):
    v=copy.deepcopy(brief);v['audio_timing']['viseme']=copy.deepcopy(RIG_TIMING_MARKER);return v


def rebind_visual_rig(before,after):
    """Only metadata-only scene changes may retain annotations for identical audio."""
    if not before.get('rig'):return after
    a=copy.deepcopy(before['audio_timing']);b=copy.deepcopy(after['audio_timing'])
    a.pop('scene_sha256');b.pop('scene_sha256')
    if a!=b or before['audio']!=after['audio'] or before['script']!=after['script'] or before['duration']!=after['duration']:
        raise WorkflowError('RIG_FRESH_DATA_REQUIRED: Ses/metin/zaman değişti; yeni viseme girdisi gerekiyor')
    after['rig']=copy.deepcopy(before['rig']);after['rig']['source_timing_sha256']=digest(after['audio_timing'])
    return after


class RigRevisions:
    def __init__(self,dashboard):
        self.d=dashboard
        with self.d.connection() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS dashboard_rigs(parent TEXT,child TEXT PRIMARY KEY,binding_sha256 TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS dashboard_rig_heads(parent TEXT PRIMARY KEY,child TEXT NOT NULL);''')

    def source(self,job):
        row=self.d.job(job);self.d.assert_provenance(row)
        if row['payload'].get('rig_revision'):
            self.guard(job);return self.source(row['payload']['rig_revision']['parent_job'])
        if any(row['payload'].get(k) for k in ('edit_revision','raster_revision','scene_plan_revision')):
            raise WorkflowError('RIG_SOURCE_REQUIRED: Yeni ağız girdisini görsel revizyon öncesindeki ses işinden bağlayın')
        if row['payload']['format']['adapter']!='account-pack' or not capability(row['payload']['account']['id'], 'rig_mode'):
            raise WorkflowError('RIG_PROFILE_UNSUPPORTED: Bu nötr rig yalnız AI ve temel gizemli karakter sahnelerinde desteklenir')
        self.d.audio.guard(job);self.d.eleven.guard_old_timing(job)
        video=self.d.renders.video_input(row)
        if not video.get('audio') or not video.get('audio_timing'):raise WorkflowError('RIG_MEASURED_AUDIO_REQUIRED: Önce gerçek ses ve kelime zamanlarını bağlayın')
        return row,video

    def template(self,job):
        from .viseme import rig_descriptor
        from .audio_retime import script_sha
        row,source=self.source(job);video=rig_timing(source);definition=rig_descriptor()
        duration=video['audio_timing']['audio_duration_seconds'];end=video['duration']
        return {'job':row['id'],'expected_video_sha256':digest(source),'rig_descriptor':definition,
                'spec':{'schema_version':1,'account':video['brand'],'rig_id':'neutral-presenter-1','rig_sha256':definition['sha256'],
                  'source_audio_sha256':video['audio']['sha256'],'source_script_sha256':script_sha(video['script']),
                  'source_timing_sha256':digest(video['audio_timing']),'audio_duration_seconds':duration,'timeline_duration_seconds':end,'fps':30,
                  'provenance':{'method':'manual_annotation','tool':'manual','note':'Bu sese ait gerçek zaman damgalı ağız girdisini buraya eşleyin; otomatik fonem üretimi yapılmadı.',
                    'approved_by':'operator','rights_confirmed':False,'human_phonetic':'pending','human_visual':'pending'},
                  'mouthCues':[],'visual_tracks':{'blinks':[],'head':[{'time':0,'rotate':0,'x':0,'y':0},{'time':end,'rotate':0,'x':0,'y':0}]}},
                'warning':'Boş mouthCues kasıtlıdır. Genlik/harf/word zamanından fonem uydurulmaz. A–H/X aralıklarını gerçek ses için elle veya doğrulanabilir tool exportuyla sağlayın; fonetik ve algısal kabul bekler.'}

    def video(self,source,spec):
        from .viseme import validate_rig
        from .engine import prepare_input
        video=rig_timing(source);video['rig']=validate_rig(spec,video)
        return prepare_input(video)[0]

    def create(self,job,data):
        if not isinstance(data,dict) or set(data)!={'spec','expected_video_sha256','approved_by','review_pending'} or data['review_pending'] is not True:
            raise WorkflowError('RIG_IMPORT_FIELDS: Explicit rig spec, kaynak hash ve bekleyen insan incelemesi gerekli')
        if not isinstance(data['approved_by'],str) or not 1<=len(data['approved_by'].strip())<=200:
            raise WorkflowError('RIG_OPERATOR_REQUIRED')
        self.d.clean(data)
        row,source=self.source(job);job=row['id']
        if data['expected_video_sha256']!=digest(source):raise WorkflowError('RIG_SOURCE_CHANGED: Kaynak önizlemesini yenileyin')
        video=self.video(source,data['spec'])
        if video['rig']['provenance']['approved_by']!=data['approved_by'].strip():raise WorkflowError('RIG_OPERATOR_MISMATCH')
        binding={'schema_version':1,'parent_job':job,'parent_payload_sha256':digest(row['payload']),'parent_video_sha256':digest(source),
                 'rig_sha256':digest(video['rig']),'video_sha256':digest(video),'audio_sha256':video['audio']['sha256'],
                 'timing_sha256':digest(video['audio_timing']),'execution_fingerprint':self.d.runtime_execution,
                 'approved_by':data['approved_by'].strip(),'review_status':'incomplete','publication_ready':False}
        payload=copy.deepcopy(row['payload']);payload.pop('audio_revision',None);payload['rig_revision']=binding;payload['template']['template']['video']=video
        child=digest(payload)[:24];out=self.d.output(child)
        from .raster_revision import pinned_path
        with tempfile.TemporaryDirectory(prefix='rig-import-',dir=self.d.workspace) as temporary:
            stage=Path(temporary)/'child';stage.mkdir(mode=0o700);write_json(stage/'rig.json',video['rig']);write_json(stage/'rig-binding.json',binding);write_json(stage/'audio-timing.json',video['audio_timing'])
            audio=pinned_path(self.d.output(job),video['audio']['file']);target=pinned_path(stage,video['audio']['file']);private_directory(target.parent)
            if file_hash(audio)!=binding['audio_sha256']:raise WorkflowError('RIG_AUDIO_CHANGED')
            copy_private(audio,target)
            if file_hash(target)!=binding['audio_sha256']:raise WorkflowError('RIG_AUDIO_COPY_CHANGED')
            owned=None;committed=False
            try:
                with self.d.revision_lock,self.d.connection() as db:
                    db.execute('BEGIN IMMEDIATE');current,actual=self.source(job)
                    if digest(current['payload'])!=binding['parent_payload_sha256'] or digest(actual)!=binding['parent_video_sha256']:raise WorkflowError('RIG_SOURCE_CHANGED_DURING_SAVE')
                    head=db.execute('SELECT child FROM dashboard_rig_heads WHERE parent=?',(job,)).fetchone();known=db.execute('SELECT child FROM dashboard_rigs WHERE child=?',(child,)).fetchone()
                    if known:
                        if not head or head[0]!=child:raise WorkflowError('RIG_SUPERSEDED: Eski ağız girdisi yeniden etkinleştirilmedi')
                        self.guard(child);return self.result(job,child,True)
                    if out.exists() or out.is_symlink():raise WorkflowError('RIG_UNEXPECTED_FILES: Mevcut sonuç incelenmeden üzerine yazılmaz')
                    private_directory(out.parent);st=stage.stat();owned=(st.st_dev,st.st_ino);os.rename(stage,out)
                    db.execute('INSERT INTO dashboard_jobs(id,payload,status,created) VALUES(?,?,?,?)',(child,canonical(payload),'queued',now()))
                    db.execute('INSERT INTO dashboard_rigs VALUES(?,?,?)',(job,child,digest(binding)))
                    db.execute('INSERT INTO dashboard_rig_heads VALUES(?,?) ON CONFLICT(parent) DO UPDATE SET child=excluded.child',(job,child))
                    db.execute('INSERT INTO dashboard_events(job,event,created) VALUES(?,?,?)',(child,'explicit_fresh_manual_rig',now()))
                committed=True
            except Exception:
                if not committed:self._cleanup(out,owned,child)
                raise
        self.guard(child);return self.result(job,child,False)

    def _cleanup(self,out,owned,child):
        if owned is None:return
        try:
            with self.d.connection() as db:
                if db.execute('SELECT 1 FROM dashboard_jobs WHERE id=?',(child,)).fetchone() or db.execute('SELECT 1 FROM dashboard_rigs WHERE child=?',(child,)).fetchone():return
            st=out.lstat()
            if not out.is_symlink() and out.is_dir() and (st.st_dev,st.st_ino)==owned:shutil.rmtree(out)
        except Exception:return

    def result(self,parent,child,reused):
        return {'parent_job':parent,'child_job':child,'job':self.d.job(child),'reused':reused,'provider_calls':0,'render_started':False,'publication_ready':False,'human_phonetic':'pending','human_visual':'pending'}

    def guard(self,job):
        with self.d.revision_lock:
            row=self.d.job(job);self.d.assert_provenance(row);b=row['payload'].get('rig_revision')
            if not b:return
            with self.d.connection() as db:
                head=db.execute('SELECT child FROM dashboard_rig_heads WHERE parent=?',(b['parent_job'],)).fetchone();record=db.execute('SELECT binding_sha256 FROM dashboard_rigs WHERE child=?',(job,)).fetchone()
            if not head or head[0]!=job or not record or record[0]!=digest(b) or digest(row['payload'])[:24]!=job:raise WorkflowError('RIG_SUPERSEDED_OR_CHANGED: Eski rig/QA/export geçersiz')
            parent,source=self.source(b['parent_job']);video=row['payload']['template']['template']['video'];expected=self.video(source,video['rig'])
            if digest(parent['payload'])!=b['parent_payload_sha256'] or digest(source)!=b['parent_video_sha256'] or expected!=video or digest(video)!=b['video_sha256'] or digest(video['rig'])!=b['rig_sha256']:
                raise WorkflowError('RIG_SOURCE_BINDING_CHANGED')
            from .raster_revision import pinned_path
            out=self.d.output(job)
            for name,value in [('rig.json',video['rig']),('rig-binding.json',b),('audio-timing.json',video['audio_timing'])]:
                if json.loads(pinned_path(out,name).read_text())!=value:raise WorkflowError('RIG_STORED_MANIFEST_CHANGED')
            if file_hash(pinned_path(out,video['audio']['file']))!=b['audio_sha256']:raise WorkflowError('RIG_STORED_AUDIO_CHANGED')
            return copy.deepcopy(video)

    def render_input(self,row):return self.guard(row['id'])
