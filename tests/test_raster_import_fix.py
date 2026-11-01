from pack_fixture_case import PackFixtureCase
"""Small valid files and real SQLite/thread fault regression;no native/provider calls."""
import base64,contextlib,hashlib,json,sqlite3,struct,threading,unittest,zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from storymotion.dashboard import Dashboard
from storymotion.security import WorkflowError,file_hash
import test_raster_revision as revision
import test_raster_ui as ui


def tiny_png():
 def chunk(k,v):return struct.pack('>I',len(v))+k+v+struct.pack('>I',zlib.crc32(k+v)&0xffffffff)
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',64,64,2,0,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0'*(17*64),1))+chunk(b'IEND',b'')

class RasterImportFix(PackFixtureCase):
 def setUp(self):self.h=revision.RasterRevisionTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
 def test_valid_79_byte_64x64_png_reaches_decode_and_pins_original_hash(self):
  raw=tiny_png();self.assertEqual(len(raw),79);data=self.h.body();data.update(image_base64=base64.b64encode(raw).decode(),expected_source_sha256=hashlib.sha256(raw).hexdigest())
  child=self.h.image(body=data)['child_job'];video=self.h.d.raster.guard(child);self.assertEqual(video['raster']['asset']['source_sha256'],hashlib.sha256(raw).hexdigest());self.assertEqual(video['raster']['asset']['width'],64)
 def test_short_malformed_or_bad_hash_still_has_zero_persistent_change(self):
  before=self.h.state()
  for raw,sha in [(b'bad',hashlib.sha256(b'bad').hexdigest()),(tiny_png(),'0'*64),(b'',hashlib.sha256(b'').hexdigest())]:
   data=self.h.body();data.update(image_base64=base64.b64encode(raw).decode(),expected_source_sha256=sha)
   with self.subTest(length=len(raw)),self.assertRaises(WorkflowError):self.h.image(body=data)
   self.assertEqual(self.h.state(),before)
 def test_failed_waiting_import_cannot_delete_other_instances_completed_files(self):
  # Same real SQLite workspace, independent service locks.Only loser BEGIN fails.
  d=self.h.d;other=Dashboard(d.workspace);self.addCleanup(other.clear_keys);original=other.connection;waiting=threading.Event();winner_done=threading.Event();body=self.h.body();injected=[]
  class Fault:
   def __init__(self,db):self.db=db
   def __getattr__(self,key):return getattr(self.db,key)
   def execute(self,sql,*args):
    if sql=='BEGIN IMMEDIATE' and not injected:
     injected.append(True);waiting.set()
     if not winner_done.wait(5):raise AssertionError('Winner did not finish')
     raise sqlite3.OperationalError('synthetic temporary DB failure before claim')
    return self.db.execute(sql,*args)
  @contextlib.contextmanager
  def connection():
   with original() as db:yield Fault(db)
  with patch.object(other,'connection',connection),patch('storymotion.engine.checked_process',side_effect=self.h.decoder),ThreadPoolExecutor(max_workers=2) as pool:
   losing=pool.submit(other.raster.import_local,self.h.parent,body);self.assertTrue(waiting.wait(5))
   try:winner=d.raster.import_local(self.h.parent,body);out=d.output(winner['child_job']);snapshot={str(p.relative_to(out)):file_hash(p) for p in out.rglob('*') if p.is_file()}
   finally:winner_done.set()
   with self.assertRaises(sqlite3.OperationalError):losing.result(timeout=5)
  d.raster.guard(winner['child_job']);self.assertEqual(snapshot,{str(p.relative_to(out)):file_hash(p) for p in out.rglob('*') if p.is_file()});self.assertEqual(len(d.jobs()),2);self.assertFalse(list(d.workspace.glob('raster-import-*')))
 def test_same_input_parallel_service_instances_reuse_one_complete_child(self):
  other=Dashboard(self.h.d.workspace);self.addCleanup(other.clear_keys);barrier=threading.Barrier(2);data=self.h.body()
  def run(d):barrier.wait(timeout=5);return d.raster.import_local(self.h.parent,data)
  with patch('storymotion.engine.checked_process',side_effect=self.h.decoder),ThreadPoolExecutor(max_workers=2) as pool:
   futures=[pool.submit(run,d) for d in (self.h.d,other)];a,b=[f.result(timeout=10) for f in futures]
  self.assertEqual(a['child_job'],b['child_job']);self.assertEqual({a['reused'],b['reused']},{False,True});self.assertEqual(len(self.h.d.jobs()),2);self.h.d.raster.guard(a['child_job'])
 def test_rollback_after_publish_removes_only_own_uncommitted_output(self):
  d=self.h.d;original=d.connection;before=self.h.state()
  class Fault:
   def __init__(self,db):self.db=db
   def __getattr__(self,key):return getattr(self.db,key)
   def execute(self,sql,*args):
    if sql.startswith('INSERT INTO dashboard_events'):raise sqlite3.OperationalError('synthetic rollback after publication')
    return self.db.execute(sql,*args)
  @contextlib.contextmanager
  def connection():
   with original() as db:yield Fault(db)
  with patch.object(d,'connection',connection),self.assertRaises(sqlite3.OperationalError):self.h.image()
  self.assertEqual(self.h.state(),before);self.assertFalse(list(d.workspace.glob('raster-import-*')))
 def test_exception_after_real_commit_preserves_committed_child(self):
  d=self.h.d;original=d.connection;finished=[]
  @contextlib.contextmanager
  def connection():
   with original() as db:
    yield db
    # Only the connection holding this transaction has made changes.
    publish=db.in_transaction and db.total_changes>0
   if publish and not finished:finished.append(True);raise sqlite3.OperationalError('synthetic acknowledgement failure after commit')
  with patch.object(d,'connection',connection),self.assertRaises(sqlite3.OperationalError):self.h.image()
  children=[j for j in d.jobs() if j['id']!=self.h.parent];self.assertEqual(len(children),1);d.raster.guard(children[0]['id']);self.assertTrue((d.output(children[0]['id'])/'raster/image.png').is_file())
 def test_cleanup_does_not_remove_replaced_directory_or_unreadable_db_result(self):
  d=self.h.d;child='f'*24;out=d.output(child);out.mkdir(parents=True);p=out/'keep.txt';p.write_text('own neutral test');st=out.stat()
  d.raster._cleanup_owned_uncommitted(out,(st.st_dev,st.st_ino+1),child);self.assertEqual(p.read_text(),'own neutral test')
  with patch.object(d,'connection',side_effect=sqlite3.OperationalError('synthetic unreadable DB')):d.raster._cleanup_owned_uncommitted(out,(st.st_dev,st.st_ino),child)
  self.assertEqual(p.read_text(),'own neutral test')
 def test_ui_allows_79_byte_file_but_zero_byte_selection_stays_disabled(self):
  ui.RasterUI().dom(r'''file.size=79;run('rasterControls()');assert.equal($('raster-submit').disabled,false);file.size=0;run('rasterControls()');assert.equal($('raster-submit').disabled,true);''')

if __name__=='__main__':unittest.main()
