from pack_fixture_case import PackFixtureCase
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from storymotion.engine import Engine,ROOT
from storymotion.security import WorkflowError,file_hash
from storymotion.edit_plan import verify_staged_assets
from storymotion.dashboard import Dashboard
from audio_fixture import no_media
from audio_flow_fixture import seed_final


class StagedAssetTests(PackFixtureCase):
 def test_corrupted_copy_fails_before_html_and_never_completes_prepare_for_both_engines(self):
  import shutil
  original=shutil.copytree
  def corrupt(src,dst,*args,**kwargs):
   r=original(src,dst,*args,**kwargs)
   if Path(src)==ROOT/'vendor':(Path(dst)/'fonts/schibsted-grotesk-latin-ext-wght-normal.woff2').write_bytes(b'corrupt copied font')
   return r
  for engine in ('hyperframes','remotion'):
   with tempfile.TemporaryDirectory() as tmp:
    e=Engine(tmp)
    try:
     job=e.create(ROOT/'tests/fixtures/examples/golden/sample-mechanism.json',render_engine=engine)['job']
     with patch('storymotion.compose.shutil.copytree',side_effect=corrupt):
      with self.assertRaisesRegex(WorkflowError,'Staged required'):e.run(job,'prepare')
     self.assertEqual(e.store.stage(job,'prepare')['status'],'failed');self.assertFalse((e.directory(job)/'index.html').exists())
    finally:e.store.db.close()
 def test_resume_repairs_bad_staging_even_if_stage_manifest_matches_corrupted_bytes(self):
  for engine in ('hyperframes','remotion'):
   with tempfile.TemporaryDirectory() as tmp:
    e=Engine(tmp)
    try:
     job=e.create(ROOT/'tests/fixtures/examples/golden/sample-mechanism.json',render_engine=engine)['job'];e.run(job,'prepare');p=e.directory(job)/'assets/fonts/schibsted-grotesk-latin-ext-wght-normal.woff2';p.write_bytes(b'corrupt staging');manifest=json.loads(e.store.stage(job,'prepare')['manifest']);manifest[str(p.relative_to(e.directory(job)))]=file_hash(p);e.store.set_stage(job,'prepare','complete',manifest)
     self.assertFalse(e.manifest_valid(job,'prepare'));e.run(job,'prepare');self.assertTrue(e.manifest_valid(job,'prepare'));self.assertEqual(file_hash(p),file_hash(ROOT/'vendor/fonts'/p.name))
    finally:e.store.db.close()
 def test_corrupted_staging_or_zip_member_rejects_download_for_both_engines(self):
  import zipfile
  for engine in ('hyperframes','remotion'):
   for kind in ('stage','zip'):
    with self.subTest(engine=engine,kind=kind),tempfile.TemporaryDirectory() as tmp,no_media():
     d=Dashboard(tmp)
     try:
      _,child,_,out,payload=seed_final(d,'sample-mechanism',engine);rel='assets/fonts/schibsted-grotesk-latin-ext-wght-normal.woff2'
      if kind=='stage':(out/rel).write_bytes(b'corrupted staging')
      else:
       path=out/'delivery.zip'
       with zipfile.ZipFile(path) as z:members={n:z.read(n) for n in z.namelist()}
       members[rel]=b'corrupted packaged font'
       with zipfile.ZipFile(path,'w') as z:
        for n,b in members.items():z.writestr(n,b)
      with self.assertRaises(WorkflowError):verify_staged_assets(payload,out,delivery=True)
      self.assertEqual(d.renders.state(child,engine)['status'],'invalidated')
      with self.assertRaises(WorkflowError):d.renders.download(child,engine,'delivery.zip')
     finally:d.clear_keys()

 def test_same_bytes_staging_symlink_and_zip_symlink_or_duplicate_are_refused(self):
  import zipfile,stat
  for engine in ('hyperframes','remotion'):
   with tempfile.TemporaryDirectory() as tmp:
    e=Engine(tmp)
    try:
     job=e.create(ROOT/'tests/fixtures/examples/golden/sample-mechanism.json',render_engine=engine)['job'];e.run(job,'prepare');out=e.directory(job);p=out/'assets/fonts/schibsted-grotesk-latin-ext-wght-normal.woff2';other=out/'same-bytes.woff2';other.write_bytes(p.read_bytes());p.unlink();p.symlink_to(other)
     with self.assertRaises(WorkflowError):verify_staged_assets(e.payload(job),out)
    finally:e.store.db.close()
   for kind in ('symlink','duplicate'):
    with tempfile.TemporaryDirectory() as tmp,no_media():
     d=Dashboard(tmp)
     try:
      _,child,_,out,payload=seed_final(d,'sample-mechanism',engine);rel='assets/fonts/schibsted-grotesk-latin-ext-wght-normal.woff2';path=out/'delivery.zip'
      with zipfile.ZipFile(path) as z:members={n:z.read(n) for n in z.namelist()}
      with zipfile.ZipFile(path,'w') as z:
       for n,b in members.items():
        if n==rel and kind=='symlink':
         info=zipfile.ZipInfo(n);info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(info,b)
        else:z.writestr(n,b)
       if kind=='duplicate':
        import warnings
        with warnings.catch_warnings():warnings.simplefilter('ignore');z.writestr(rel,members[rel])
      with self.assertRaises(WorkflowError):verify_staged_assets(payload,out,delivery=True)
      with self.assertRaises(WorkflowError):d.renders.download(child,engine,'delivery.zip')
     finally:d.clear_keys()

if __name__=='__main__':unittest.main()
