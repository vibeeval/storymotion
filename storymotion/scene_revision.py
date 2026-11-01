"""Explicit immutable visual revisions. Existing bounded geometry, no provider calls."""
from .local_state import private_directory, write_private, copy_private
import copy,json,re,shutil,tempfile,os
from pathlib import Path
from .security import WorkflowError,canonical,digest,file_hash,within,write_json
from .store import now


class SceneRevisions:
 def __init__(self,dashboard):self.d=dashboard
 def mutate(self,video,scene_id,prop,value):
  if prop not in {'heading','camera'}:raise WorkflowError('Bu dilim yalnız sahne başlığı/kamera destekler; anlatım veya süre için yeni ses/retime gerekir')
  if not isinstance(scene_id,str) or not isinstance(value,str):raise WorkflowError('Sahne ve değer metin olmalı')
  before=video;video=copy.deepcopy(video);video.pop('revision_context',None)
  found=[s for s in video['scenes'] if s['id']==scene_id]
  if len(found)!=1:raise WorkflowError('Seçili sahne bulunamadı')
  if found[0][prop]==value:raise WorkflowError('Revizyon değeri mevcut sahneyle aynı')
  found[0][prop]=value
  if video.get('raster') and prop=='camera':next(v for v in video['raster']['views'] if v['scene_id']==scene_id)['camera']=value
  if video.get('scene_plan') and prop=='camera':next(v for v in video['scene_plan']['scenes'] if v['scene_id']==scene_id)['camera']=value
  if video.get('audio_timing'):video['audio_timing']['scene_sha256']=digest(video['scenes'])
  from .rig_revision import rebind_visual_rig
  rebind_visual_rig(before,video)
  from .engine import prepare_input
  return prepare_input(video)[0]
 def create(self,job,data):
  if not isinstance(data,dict) or set(data)!={'engine','expected_plan_sha256','scene_id','property','value'}:raise WorkflowError('Revizyon alanları geçersiz')
  self.d.clean(data)
  with self.d.revision_lock:
   row=self.d.renders.validate(job,data['engine']);self.d.eleven.guard_old_timing(job)
   if row['payload']['format']['adapter']!='account-pack':raise WorkflowError('Revizyon sürümlü account-pack işi gerektirir')
   plan=self.d.renders.edit_plan(job,data['engine'])['edit_plan']
   if data['expected_plan_sha256']!=plan['plan_sha256']:raise WorkflowError('Kurgu planı değişti; güncel planı yeniden okuyun')
   original=self.d.renders.video_input(row);video=self.mutate(original,data['scene_id'],data['property'],data['value'])
   depth=row['payload'].get('edit_revision',{}).get('depth',0)+1
   if depth>8:raise WorkflowError('Bu dilimde en fazla sekiz görsel revizyon zinciri desteklenir')
   binding={'schema_version':1,'parent_job':job,'parent_payload_sha256':digest(row['payload']),'parent_video_sha256':digest(original),'parent_plan_sha256':plan['plan_sha256'],
    'depth':depth,'scene_id':data['scene_id'],'property':data['property'],'before':next(s for s in original['scenes'] if s['id']==data['scene_id'])[data['property']],'after':data['value'],
    'video_sha256':digest(video),'source_binding_sha256':video.get('production_context',{}).get('binding_sha256'),
    'script_sha256':digest(video['script']),'cues_sha256':digest(video['cues']),'audio_sha256':video.get('audio',{}).get('sha256') if video.get('audio') else None,
    'audio_timing_sha256':digest(video['audio_timing']) if video.get('audio_timing') else None,
    'impact':{'geometry':'selected raster annotation' if video.get('raster') else 'same bounded family','script':'unchanged','source_snapshot':'unchanged;semantic review pending','audio_bytes':'unchanged' if video.get('audio') else 'none',
     'word_times':'unchanged','subtitles':'unchanged','viseme':'same explicit annotations rebound to scene metadata; human review pending' if video.get('rig') else 'not_applicable_no_articulated_mouth','timing_manifest':'scene hash refreshed' if video.get('audio_timing') else 'provisional',
     'QA_export_approval':'new child only; no parent receipt or approval inherited','publication_ready':False}}
   binding['binding_sha256']=digest(binding);video['revision_context']=binding
   payload=copy.deepcopy(row['payload']);payload.pop('audio_revision',None);payload['edit_revision']=binding;payload['template']['template']['video']=video;self.d.clean(payload)
   child=digest(payload)[:24];out=self.d.output(child)
   # New manual scene descendants use the same call-owned atomic publication
   # boundary as raster imports. Failed/ambiguous commits never clean a winner.
   with tempfile.TemporaryDirectory(prefix='scene-revision-',dir=self.d.workspace) as temporary:
    stage=Path(temporary)/'child';stage.mkdir(mode=0o700)
    if video.get('scene_plan'):
     from .manual_scene_revision import validate_stored_plan
     validate_stored_plan(original,self.d.output(job));write_json(stage/'manual-plan.json',video['scene_plan']);validate_stored_plan(video,stage)
    if video.get('raster'):
     from .raster_revision import validate_stored_raster,pinned_path
     validate_stored_raster(original,self.d.output(job));a=video['raster']['asset'];source=pinned_path(self.d.output(job),a['file']);target=pinned_path(stage,a['file']);private_directory(target.parent)
     copy_private(source,target);write_json(stage/'raster.json',video['raster']);validate_stored_raster(video,stage)
    if video.get('audio'):
     from .raster_revision import pinned_path
     source=pinned_path(self.d.output(job),video['audio']['file']);target=pinned_path(stage,video['audio']['file']);private_directory(target.parent)
     if file_hash(source)!=binding['audio_sha256']:raise WorkflowError('Onaylı ses değişti')
     copy_private(source,target)
     if file_hash(target)!=binding['audio_sha256']:raise WorkflowError('Revizyon sesi değişti')
     write_json(stage/'audio-timing.json',video['audio_timing'])
    if video.get('rig'):write_json(stage/'rig.json',video['rig'])
    write_json(stage/'revision.json',binding);owned=None;committed=False
    try:
     with self.d.connection() as db:
      db.execute('BEGIN IMMEDIATE')
      if db.execute('SELECT id FROM dashboard_jobs WHERE id=?',(child,)).fetchone():
       self.guard(child)
       return {'child_job':child,'parent_job':job,'revision':binding,'provider_calls':0,'render_started':False,'publication_ready':False}
      if digest(self.d.job(job)['payload'])!=binding['parent_payload_sha256']:raise WorkflowError('Kaynak iş değişti; revizyon oluşturulmadı')
      self.d.audio.guard(job);self.d.assert_runtime_current()
      if out.exists() or out.is_symlink():raise WorkflowError('Unexpected revision child files exist; inspect before retry')
      private_directory(out.parent);st=stage.stat();owned=(st.st_dev,st.st_ino);os.rename(stage,out)
      db.execute('INSERT INTO dashboard_jobs(id,payload,status,created) VALUES(?,?,?,?)',(child,canonical(payload),'queued',now()))
      db.execute('INSERT INTO dashboard_events(job,event,created) VALUES(?,?,?)',(child,'explicit_scene_visual_revision',now()))
     committed=True
    except Exception:
     if not committed:self.d.plans._cleanup(out,owned,child)
     raise
   self.guard(child)
   return {'child_job':child,'parent_job':job,'revision':binding,'provider_calls':0,'render_started':False,'publication_ready':False}
 def guard(self,job):
  try:return self._validated(job,set())
  except (OSError,ValueError,KeyError,TypeError):raise WorkflowError('Görsel revizyon bağı veya dosyası değişti; çıktı geçersiz') from None
 def _validated(self,job,seen):
  if job in seen or len(seen)>=8:raise WorkflowError('Görsel revizyon zinciri geçersiz')
  seen.add(job);row=self.d.job(job);self.d.assert_provenance(row);b=row['payload']['edit_revision'];parent=self.d.job(b['parent_job'])
  if b['depth']!=parent['payload'].get('edit_revision',{}).get('depth',0)+1 or digest(parent['payload'])!=b['parent_payload_sha256']:raise WorkflowError('Revizyon kaynak işi değişti')
  if parent['payload'].get('edit_revision'):original=self._validated(parent['id'],seen)
  else:
   self.d.audio.guard(parent['id']);self.d.eleven.guard_old_timing(parent['id']);original=self.d.renders.video_input(parent)
  if digest(original)!=b['parent_video_sha256']:raise WorkflowError('Revizyon kaynak videosu değişti')
  expected=self.mutate(original,b['scene_id'],b['property'],b['after'])
  if digest(expected)!=b['video_sha256'] or digest({k:v for k,v in b.items() if k!='binding_sha256'})!=b['binding_sha256']:raise WorkflowError('Revizyon manifesti değişti')
  expected['revision_context']=b
  if row['payload']['template']['template']['video']!=expected or digest(row['payload'])[:24]!=job:raise WorkflowError('Revizyon iş kimliği değişti')
  out=self.d.output(job)
  if expected.get('scene_plan'):
   from .manual_scene_revision import validate_stored_plan
   validate_stored_plan(expected,out)
  if expected.get('raster'):
   from .raster_revision import validate_stored_raster
   validate_stored_raster(expected,out)
  if json.loads((out/'revision.json').read_text())!=b:raise WorkflowError('Revizyon dosyası değişti')
  if expected.get('rig'):
   from .raster_revision import pinned_path
   if json.loads(pinned_path(out,'rig.json').read_text())!=expected['rig']:raise WorkflowError('Revizyon rig dosyası değişti')
  if expected.get('audio'):
   source=within(out,expected['audio']['file'])
   if source.is_symlink() or file_hash(source)!=b['audio_sha256'] or json.loads((out/'audio-timing.json').read_text())!=expected['audio_timing']:raise WorkflowError('Revizyon ses/timing dosyası değişti')
  return copy.deepcopy(expected)
 def render_input(self,row):return self.guard(row['id'])
