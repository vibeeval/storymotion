from .local_state import private_directory, write_private, copy_private
from .account_packs import capability, is_serial
"""Explicit manual scene plans as immutable, source-bound review jobs."""
import copy,json,os,re,shutil,tempfile
from pathlib import Path
from .security import WorkflowError,canonical,digest,file_hash,write_json
from .store import now
from .raster_revision import pinned_path


def validate_stored_plan(video,out):
 from .scene_plan import validate_scene_plan
 spec=validate_scene_plan(video['scene_plan'],video);path=pinned_path(out,'manual-plan.json')
 if not path.is_file() or json.loads(path.read_text())!=spec:raise WorkflowError('Immutable manual scene plan missing or changed')
 return spec

class ManualSceneRevisions:
 def __init__(self,dashboard):
  self.d=dashboard
  with self.d.connection() as db:db.executescript('''CREATE TABLE IF NOT EXISTS dashboard_scene_plans(parent TEXT,child TEXT PRIMARY KEY,binding_sha256 TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS dashboard_scene_plan_heads(parent TEXT PRIMARY KEY,child TEXT NOT NULL);''')
 def base(self,job):
  row=self.d.job(job);self.d.assert_provenance(row);p=row['payload']
  if not capability(p['account']['id'], 'manual_scene_kinds') or p['format']['adapter']!='account-pack':raise WorkflowError('Manual scenes require an AccountPack with declared manual_scene_kinds and an account-pack source job')
  if any(p.get(k) for k in ('edit_revision','raster_revision','scene_plan_revision','rig_revision')):raise WorkflowError('Choose the original or current audio source job to replace its scene plan before rig binding')
  self.d.audio.guard(job);self.d.eleven.guard_old_timing(job)
  return row,self.d.renders.video_input(row)
 def video(self,source,plan):
  from .engine import prepare_input
  from .scene_plan import validate_scene_plan
  video=copy.deepcopy(source);video.pop('revision_context',None);video['scene_plan']=copy.deepcopy(plan)
  if not isinstance(plan,dict) or not isinstance(plan.get('scenes'),list) or len(plan['scenes'])!=len(video['scenes']):raise WorkflowError('One manual item per source scene required')
  for scene,item in zip(video['scenes'],plan['scenes']):
   if not isinstance(item,dict) or item.get('scene_id')!=scene['id']:raise WorkflowError('Manual scene order changed')
   scene['camera']=item.get('camera')
  if video.get('audio_timing'):video['audio_timing']['scene_sha256']=digest(video['scenes'])
  validate_scene_plan(plan,video)
  return prepare_input(video)[0]
 def template(self,job):
  from .scene_plan import KINDS
  row,video=self.base(job);account=video['brand'];context=video.get('production_context') or {};accepted=context.get('canon')
  if is_serial(account) and not accepted:raise WorkflowError('Add an explicit accepted-reference canon snapshot before planning serial scenes; drafts cannot become canon')
  allowed=set(KINDS[account])
  # Preserve existing paired defaults, but never invent an undeclared kind.
  kind=next((k for k in ('possibility-branches','process-route','object-transform','observation','clue-inspect','canon-board') if k in allowed),None)
  if kind is None:raise WorkflowError('AccountPack declares no supported manual scene kind')
  if kind in {'clue-inspect','canon-board'} and not accepted:raise WorkflowError('Canon scene kinds require an explicit accepted-reference snapshot; no clue IDs were invented')
  rows=[]
  for i,s in enumerate(video['scenes']):
   if kind=='possibility-branches':content={'left':'Bir olasılık olabilir.','right':'Başka bir olasılık olabilir.','question':'Hangi ayrıntıyı gözleyebilirim?'}
   elif kind=='observation':content={'object':'clock','prompt':'Hangi ayrıntıyı görüyorum?','observation':'Gördüğüm ayrıntıyı not ediyorum.'}
   elif kind=='process-route':content={'nodes':['Girdi','İşlem','Sonuç'],'from_node':0,'to_node':2}
   elif kind=='object-transform':content={'object':'document','before':'Önceki durum','after':'Sonraki durum'}
   else:
    clues=[c['id'] for c in accepted['data']['open_clues'] if c['object_id']==s['object_id']]
    if not clues:raise WorkflowError('No accepted open clue belongs to this exact scene object')
    content={'clue_id':clues[0],'note':'Kabul edilmiş aynı nesne izini inceliyorum.'} if kind=='clue-inspect' else {'clue_ids':clues[:3],'note':'Kabul edilmiş aynı nesne izlerini karşılaştırıyorum.'}
   rows.append({'scene_id':s['id'],'kind':kind,'content':content,'claim_indexes':[],
    'cue_indexes':[n for n,c in enumerate(video['cues']) if c['start']<s['end'] and c['end']>s['start']], 'object_id':s['object_id'],'camera':s['camera']})
  return {'expected_video_sha256':digest(video),'plan':{'schema_version':1,'recipe':'manual-account-scenes-1','account':account,'canon_revision':accepted['revision'] if accepted else None,'scenes':rows},
   'supported_kinds':sorted(KINDS[account]),'claims':copy.deepcopy(video['claims']),'source_binding_sha256':context.get('binding_sha256'),
   'semantic_mapping':'manual_required_not_inferred','publication_ready':False,'review_status':'incomplete'}
 def create(self,job,data):
  if not isinstance(data,dict) or set(data)!={'plan','expected_video_sha256','approved_by','review_pending'}:raise WorkflowError('Exact manual plan fields required')
  self.d.clean(data)
  if data['review_pending'] is not True:raise WorkflowError('Acknowledge manual source/visual review is pending')
  if not isinstance(data['approved_by'],str) or not 1<=len(data['approved_by'].strip())<=200 or any(ord(c)<32 for c in data['approved_by']):raise WorkflowError('Bounded manual plan operator required')
  row,source=self.base(job)
  if data['expected_video_sha256']!=digest(source):raise WorkflowError('Source video changed; reload the manual plan')
  video=self.video(source,data['plan']);spec=video['scene_plan']
  binding={'schema_version':1,'parent_job':job,'parent_payload_sha256':digest(row['payload']),'parent_video_sha256':digest(source),
   'video_sha256':digest(video),'scene_plan_sha256':digest(spec),'source_binding_sha256':video.get('production_context',{}).get('binding_sha256'),
   'script_sha256':digest(video['script']),'cues_sha256':digest(video['cues']),'audio_sha256':video.get('audio',{}).get('sha256') if video.get('audio') else None,
   'audio_timing_sha256':digest(video['audio_timing']) if video.get('audio_timing') else None,
   'approved_by':data['approved_by'].strip(),'review_status':'incomplete','execution_fingerprint':self.d.runtime_execution,'publication_ready':False}
  payload=copy.deepcopy(row['payload']);payload.pop('audio_revision',None);payload['scene_plan_revision']=binding;payload['template']['template']['video']=video;self.d.clean(payload)
  child=digest(payload)[:24];out=self.d.output(child)
  with tempfile.TemporaryDirectory(prefix='manual-plan-',dir=self.d.workspace) as temporary:
   stage=Path(temporary)/'child';stage.mkdir(mode=0o700);write_json(stage/'manual-plan.json',spec)
   if video.get('audio'):
    audio=pinned_path(self.d.output(job),video['audio']['file']);dest=pinned_path(stage,video['audio']['file']);private_directory(dest.parent)
    if file_hash(audio)!=video['audio']['sha256']:raise WorkflowError('Bound source audio changed')
    copy_private(audio,dest)
    if file_hash(dest)!=video['audio']['sha256']:raise WorkflowError('Manual scene audio changed during copy')
    write_json(stage/'audio-timing.json',video['audio_timing'])
   validate_stored_plan(video,stage);owned=None;committed=False
   try:
    with self.d.revision_lock,self.d.connection() as db:
     db.execute('BEGIN IMMEDIATE');self.d.assert_runtime_current();self.d.audio.guard(job);self.d.eleven.guard_old_timing(job)
     if digest(self.d.job(job)['payload'])!=binding['parent_payload_sha256'] or digest(self.d.renders.video_input(self.d.job(job)))!=binding['parent_video_sha256']:raise WorkflowError('Manual scene source changed during save')
     head=db.execute('SELECT child FROM dashboard_scene_plan_heads WHERE parent=?',(job,)).fetchone();known=db.execute('SELECT child FROM dashboard_scene_plans WHERE child=?',(child,)).fetchone()
     if known and head and head[0]!=child:raise WorkflowError('Superseded scene plan cannot silently reactivate')
     if known:
      self.guard(child)
      return {'parent_job':job,'child_job':child,'job':self.d.job(child),'provider_calls':0,'render_started':False,'publication_ready':False,'reused':True}
     if out.exists() or out.is_symlink():raise WorkflowError('Unexpected scene plan child files exist; inspect before retry')
     private_directory(out.parent);st=stage.stat();owned=(st.st_dev,st.st_ino);os.rename(stage,out)
     db.execute('INSERT INTO dashboard_jobs(id,payload,status,created) VALUES(?,?,?,?)',(child,canonical(payload),'queued',now()))
     db.execute('INSERT INTO dashboard_scene_plans VALUES(?,?,?)',(job,child,digest(binding)))
     db.execute('INSERT INTO dashboard_scene_plan_heads VALUES(?,?) ON CONFLICT(parent) DO UPDATE SET child=excluded.child',(job,child))
     db.execute('INSERT INTO dashboard_events(job,event,created) VALUES(?,?,?)',(child,'explicit_manual_scene_plan',now()))
    committed=True
   except Exception:
    if not committed:self._cleanup(out,owned,child)
    raise
  self.guard(child)
  return {'parent_job':job,'child_job':child,'job':self.d.job(child),'provider_calls':0,'render_started':False,'publication_ready':False,'reused':False}
 def _cleanup(self,out,owned,child):
  if owned is None:return
  try:
   with self.d.connection() as db:
    if db.execute('SELECT 1 FROM dashboard_jobs WHERE id=?',(child,)).fetchone() or db.execute('SELECT 1 FROM dashboard_scene_plans WHERE child=?',(child,)).fetchone():return
   st=out.lstat()
   if not out.is_symlink() and out.is_dir() and (st.st_dev,st.st_ino)==owned:shutil.rmtree(out)
  except Exception:return
 def guard(self,job):
  try:return self._guard(job)
  except (OSError,KeyError,ValueError,TypeError):raise WorkflowError('Manual scene revision missing/changed; downstream invalidated') from None
 def _guard(self,job):
  row=self.d.job(job);b=row['payload']['scene_plan_revision'];self.d.assert_provenance(row)
  with self.d.connection() as db:
   head=db.execute('SELECT child FROM dashboard_scene_plan_heads WHERE parent=?',(b['parent_job'],)).fetchone();record=db.execute('SELECT binding_sha256 FROM dashboard_scene_plans WHERE child=?',(job,)).fetchone()
  if not head or head[0]!=job or not record or record[0]!=digest(b):raise WorkflowError('Manual scene revision superseded or binding changed')
  parent,source=self.base(b['parent_job']);spec=validate_stored_plan(row['payload']['template']['template']['video'],self.d.output(job));video=self.video(source,spec)
  if (digest(parent['payload'])!=b['parent_payload_sha256'] or digest(source)!=b['parent_video_sha256'] or digest(video)!=b['video_sha256'] or digest(spec)!=b['scene_plan_sha256'] or
   row['payload']['template']['template']['video']!=video or digest(row['payload'])[:24]!=job):raise WorkflowError('Immutable manual scene identity changed')
  if video.get('audio'):
   if file_hash(pinned_path(self.d.output(job),video['audio']['file']))!=b['audio_sha256'] or json.loads(pinned_path(self.d.output(job),'audio-timing.json').read_text())!=video['audio_timing']:raise WorkflowError('Manual scene audio/timing changed')
  return copy.deepcopy(video)
 def render_input(self,row):return self.guard(row['id'])
