from .local_state import private_directory, write_private, copy_private
from .account_packs import capability
"""Explicit local customer raster -> immutable review child. No URL/code inputs."""
import base64,binascii,copy,hashlib,json,os,re,shutil,tempfile
from pathlib import Path
from .security import WorkflowError,canonical,digest,file_hash,within,write_json
from .store import now

MAX_IMAGE=8*1024*1024
MAX_RASTER_BODY=12*1024*1024
FIELDS={'image_base64','container','expected_source_sha256','approved_by','rights_note','rights_confirmed','views'}

def pinned_path(root,relative):
 root=Path(root)
 for parent in (root,*root.parents):
  if parent.is_symlink():raise WorkflowError('Raster workspace must not contain symlinks')
 root=root.resolve();parts=Path(relative).parts
 if not parts or Path(relative).is_absolute() or '..' in parts:raise WorkflowError('Raster path is outside the pinned workspace')
 for i in range(1,len(parts)+1):
  if (root/Path(*parts[:i])).is_symlink():raise WorkflowError('Raster paths must not contain symlinks')
 return within(root,relative)

def validate_stored_raster(video,out):
 from .raster_view import validate_raster
 from .raster_io import validate_normalized
 spec=validate_raster(video['raster'],video);path=pinned_path(out,spec['asset']['file'])
 validate_normalized(path,spec['asset']['sha256'],spec['asset']['width'],spec['asset']['height'])
 record=pinned_path(out,'raster.json')
 if not record.is_file() or json.loads(record.read_text())!=spec:raise WorkflowError('Immutable raster manifest changed')
 return spec

class RasterRevisions:
 def __init__(self,dashboard):
  self.d=dashboard
  with self.d.connection() as db:db.executescript('''CREATE TABLE IF NOT EXISTS dashboard_raster_revisions(parent TEXT,child TEXT PRIMARY KEY,binding_sha256 TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS dashboard_raster_heads(parent TEXT PRIMARY KEY,child TEXT NOT NULL);''')
 def base(self,job):
  row=self.d.job(job);self.d.assert_provenance(row);p=row['payload']
  if not capability(p['account']['id'], 'raster') or p['format']['adapter']!='account-pack':raise WorkflowError('Raster annotation supports only the raster-capable topic profile')
  if p.get('edit_revision') or p.get('raster_revision'):raise WorkflowError('Choose this raster revision source job to replace the image or crop')
  self.d.audio.guard(job);self.d.eleven.guard_old_timing(job)
  return row,self.d.renders.video_input(row)
 def video(self,source,spec):
  from .engine import prepare_input
  from .raster_view import validate_raster
  video=copy.deepcopy(source);video.pop('revision_context',None);video['raster']=copy.deepcopy(spec)
  if not isinstance(spec.get('views'),list) or len(spec['views'])!=len(video['scenes']):raise WorkflowError('One raster view per source scene required')
  for scene,view in zip(video['scenes'],spec['views']):
   if not isinstance(view,dict) or view.get('scene_id')!=scene['id']:raise WorkflowError('Raster scene order changed')
   scene['camera']=view.get('camera')
  if video.get('audio_timing'):video['audio_timing']['scene_sha256']=digest(video['scenes'])
  validate_raster(spec,video)
  return prepare_input(video)[0]
 def import_local(self,job,data):
  if not isinstance(data,dict) or set(data)!=FIELDS:raise WorkflowError('Exact raster upload fields required;paths/URLs are not accepted')
  row,source_video=self.base(job);metadata={k:v for k,v in data.items() if k!='image_base64'}
  try:self.d.clean(metadata)
  except (ValueError,TypeError):raise WorkflowError('Raster metadata must be finite bounded JSON') from None
  if data['rights_confirmed'] is not True:raise WorkflowError('Explicit image rights confirmation required')
  for field,maximum in [('approved_by',200),('rights_note',1000)]:
   if not isinstance(data[field],str) or not 1<=len(data[field].strip())<=maximum:raise WorkflowError('Bounded raster rights notes required')
  if not isinstance(data['container'],str) or data['container'] not in {'png','jpeg'} or not isinstance(data['expected_source_sha256'],str) or not re.fullmatch('[a-f0-9]{64}',data['expected_source_sha256']):raise WorkflowError('PNG/JPEG and exact source SHA256 required')
  raw=data['image_base64']
  if not isinstance(raw,str) or not raw or len(raw)>4*((MAX_IMAGE+2)//3):raise WorkflowError('Raster upload is empty or above8MiB')
  try:binary=base64.b64decode(raw,validate=True)
  except (ValueError,binascii.Error):raise WorkflowError('Strict raster base64 required') from None
  if not binary or len(binary)>MAX_IMAGE:raise WorkflowError('Raster upload is empty or above8MiB')
  if hashlib.sha256(binary).hexdigest()!=data['expected_source_sha256']:raise WorkflowError('Raster bytes differ from selected source hash')
  from .raster_io import normalize_raster
  with tempfile.TemporaryDirectory(prefix='raster-import-',dir=self.d.workspace) as temporary:
   normalized=normalize_raster(binary,data['container'],Path(temporary))
   spec={'schema_version':1,'recipe':'customer-raster-annotation-1','asset':{'file':'raster/image.png','sha256':normalized['sha256'],'source_sha256':normalized['source_sha256'],
    'width':normalized['width'],'height':normalized['height'],'container':'png','approved_by':data['approved_by'].strip(),'rights_note':data['rights_note'].strip(),'rights_confirmed':True},'views':copy.deepcopy(data['views'])}
   video=self.video(source_video,spec)
   binding={'schema_version':1,'parent_job':job,'parent_payload_sha256':digest(row['payload']),'parent_video_sha256':digest(source_video),
    'video_sha256':digest(video),'raster_sha256':digest(spec),'asset_sha256':spec['asset']['sha256'],'source_image_sha256':spec['asset']['source_sha256'],
    'execution_fingerprint':self.d.runtime_execution,'publication_ready':False}
   payload=copy.deepcopy(row['payload']);payload.pop('audio_revision',None);payload['raster_revision']=binding;payload['template']['template']['video']=video;self.d.clean(payload)
   child=digest(payload)[:24];out=self.d.output(child)
   # All validation and copying stays under this call's unique temporary root.
   # Never infer cleanup ownership from out.exists() before a DB/lock wait.
   stage=Path(temporary)/'child';stage.mkdir(mode=0o700);target=pinned_path(stage,'raster/image.png');private_directory(target.parent)
   copy_private(normalized['file'],target)
   if file_hash(target)!=spec['asset']['sha256']:raise WorkflowError('Raster changed while snapshotting')
   write_json(stage/'raster.json',spec)
   if video.get('audio'):
    audio=pinned_path(self.d.output(job),video['audio']['file']);dest=pinned_path(stage,video['audio']['file']);private_directory(dest.parent)
    if file_hash(audio)!=video['audio']['sha256']:raise WorkflowError('Bound source audio changed')
    copy_private(audio,dest)
    if file_hash(dest)!=video['audio']['sha256']:raise WorkflowError('Raster audio snapshot changed during copy')
    write_json(stage/'audio-timing.json',video['audio_timing'])
   validate_stored_raster(video,stage)
   owned=None;committed=False
   try:
    with self.d.revision_lock,self.d.connection() as db:
     db.execute('BEGIN IMMEDIATE');self.d.assert_runtime_current();self.d.audio.guard(job)
     if digest(self.d.job(job)['payload'])!=binding['parent_payload_sha256'] or digest(self.d.renders.video_input(self.d.job(job)))!=binding['parent_video_sha256']:raise WorkflowError('Raster source changed during import')
     head=db.execute('SELECT child FROM dashboard_raster_heads WHERE parent=?',(job,)).fetchone();known=db.execute('SELECT child FROM dashboard_raster_revisions WHERE child=?',(child,)).fetchone()
     if known and head and head[0]!=child:raise WorkflowError('Previously superseded raster cannot silently reactivate;use a new source revision')
     if known:
      self.guard(child)
      return {'parent_job':job,'child_job':child,'job':self.d.job(child),'provider_calls':0,'render_started':False,'publication_ready':False,'reused':True}
     # SQLite BEGIN IMMEDIATE serializes publishers across direct service instances.
     # A completed/unknown existing directory is never overwritten or cleaned.
     out=self.d.output(child)
     if out.exists() or out.is_symlink():raise WorkflowError('Unexpected raster child files exist;inspect before retry')
     private_directory(out.parent)
     st=stage.stat();owned=(st.st_dev,st.st_ino)
     os.rename(stage,out)
     db.execute('INSERT INTO dashboard_jobs(id,payload,status,created) VALUES(?,?,?,?)',(child,canonical(payload),'queued',now()))
     db.execute('INSERT INTO dashboard_raster_revisions VALUES(?,?,?)',(job,child,digest(binding)))
     db.execute('INSERT INTO dashboard_raster_heads VALUES(?,?) ON CONFLICT(parent) DO UPDATE SET child=excluded.child',(job,child))
     db.execute('INSERT INTO dashboard_events(job,event,created) VALUES(?,?,?)',(child,'explicit_customer_raster_import',now()))
    committed=True
   except Exception:
    if not committed:self._cleanup_owned_uncommitted(out,owned,child)
    raise
  self.guard(child)
  return {'parent_job':job,'child_job':child,'job':self.d.job(child),'provider_calls':0,'render_started':False,'publication_ready':False,'reused':False}
 def _cleanup_owned_uncommitted(self,out,owned,child):
  if owned is None:return
  try:
   # A commit exception may be ambiguous. A durable record, or an unreadable DB,
   # preserves files for inspection rather than risking another call's success.
   with self.d.connection() as db:
    if db.execute('SELECT 1 FROM dashboard_jobs WHERE id=?',(child,)).fetchone() or db.execute('SELECT 1 FROM dashboard_raster_revisions WHERE child=?',(child,)).fetchone():return
   st=out.lstat()
   if not out.is_symlink() and out.is_dir() and (st.st_dev,st.st_ino)==owned:shutil.rmtree(out)
  except Exception:return
 def guard(self,job):
  try:return self._guard(job)
  except (OSError,KeyError,ValueError,TypeError):raise WorkflowError('Raster revision bytes/manifest missing or changed;downstream invalidated') from None
 def _guard(self,job):
  row=self.d.job(job);binding=row['payload']['raster_revision'];self.d.assert_provenance(row)
  with self.d.connection() as db:
   head=db.execute('SELECT child FROM dashboard_raster_heads WHERE parent=?',(binding['parent_job'],)).fetchone();record=db.execute('SELECT binding_sha256 FROM dashboard_raster_revisions WHERE child=?',(job,)).fetchone()
  if not head or head[0]!=job or not record or record[0]!=digest(binding):raise WorkflowError('Raster revision superseded or binding changed')
  parent=self.d.job(binding['parent_job'])
  if parent['payload'].get('raster_revision') or parent['payload'].get('edit_revision'):raise WorkflowError('Raster source must be an original or current audio revision')
  self.d.audio.guard(parent['id']);self.d.eleven.guard_old_timing(parent['id'])
  source=self.d.renders.video_input(parent);spec=validate_stored_raster(row['payload']['template']['template']['video'],self.d.output(job));video=self.video(source,spec)
  if (digest(parent['payload'])!=binding['parent_payload_sha256'] or digest(source)!=binding['parent_video_sha256'] or digest(video)!=binding['video_sha256'] or
   digest(spec)!=binding['raster_sha256'] or spec['asset']['sha256']!=binding['asset_sha256'] or spec['asset']['source_sha256']!=binding['source_image_sha256'] or
   row['payload']['template']['template']['video']!=video or digest(row['payload'])[:24]!=job):raise WorkflowError('Immutable raster source/child identity changed')
  if video.get('audio'):
   audio=pinned_path(self.d.output(job),video['audio']['file'])
   if file_hash(audio)!=video['audio']['sha256'] or json.loads((self.d.output(job)/'audio-timing.json').read_text())!=video['audio_timing']:raise WorkflowError('Raster child audio/timing changed')
  return copy.deepcopy(video)
 def render_input(self,row):return self.guard(row['id'])
