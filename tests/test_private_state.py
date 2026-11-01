"""Owner-only state creation/rejection over isolated owned fixtures only."""
import contextlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from storymotion.local_state import guard_workspace, guard_control, private_directory, private_database, write_private, copy_private
from storymotion.security import WorkflowError
from storymotion.store import Store
from storymotion.dashboard import Dashboard
from storymotion.llm_service import LLMService
from storymotion.elevenlabs import ElevenService
from storymotion.qa_review import ReviewService

ROOT = Path(__file__).resolve().parents[1]


def modes(root):
    return {str(p.relative_to(root)):stat.S_IMODE(p.stat().st_mode) for p in root.rglob('*')}


@contextlib.contextmanager
def fixture_umask(mask):
    """Test-process setting only; restore the producer's original mask."""
    previous=os.umask(mask)
    try:yield
    finally:os.umask(previous)


class PrivateStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_umask_022_and_077_leave_new_db_sidecars_locks_and_user_text_private(self):
        script = '''import json,os,stat,sys
from pathlib import Path
from storymotion.store import Store
from storymotion.local_state import write_private
os.umask(int(sys.argv[2],8));root=Path(sys.argv[1])
with Store(root) as store:
 with store.lock():
  store.db.execute('CREATE TABLE mode_probe(value)');store.db.commit()
  store.db.execute('INSERT INTO mode_probe VALUES(1)')
  journal=stat.S_IMODE((root/'jobs.sqlite3-journal').stat().st_mode);store.db.commit()
  store.db.execute('PRAGMA journal_mode=WAL');store.db.execute('INSERT INTO mode_probe VALUES(2)')
  sidecars={n:stat.S_IMODE((root/('jobs.sqlite3'+n)).stat().st_mode) for n in ('-wal','-shm')}
  store.db.commit();write_private(root/'nested'/'draft.txt','Synthetic private text')
  print(json.dumps({'root':stat.S_IMODE(root.stat().st_mode),'db':stat.S_IMODE((root/'jobs.sqlite3').stat().st_mode),'lock':stat.S_IMODE((root/'.workflow.lock').stat().st_mode),'journal':journal,'sidecars':sidecars,'draft':stat.S_IMODE((root/'nested/draft.txt').stat().st_mode),'nested':stat.S_IMODE((root/'nested').stat().st_mode),'umask':os.umask(0)}))
'''
        for mask in ('022','077'):
            result = subprocess.run([sys.executable,'-B','-c',script,str(self.root/mask/'workspace'),mask],cwd=ROOT,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            value = json.loads(result.stdout)
            self.assertEqual(value,{'root':0o700,'db':0o600,'lock':0o600,'journal':0o600,'sidecars':{'-wal':0o600,'-shm':0o600},'draft':0o600,'nested':0o700,'umask':int(mask,8)})
            self.assertEqual(stat.S_IMODE((self.root/mask).stat().st_mode),0o700)

    def test_all_db_services_create_private_state_without_touching_static_parent(self):
        parent = self.root/'source';parent.mkdir(mode=0o755);static = parent/'static.txt';static.write_text('public fixture')
        # Establish the public test fixture explicitly, regardless of caller umask.
        parent.chmod(0o755);static.chmod(0o644)
        before=(parent.stat().st_mode,static.stat().st_mode,static.read_bytes())
        expected = [('jobs.sqlite3',Store),('jobs.sqlite3',Dashboard),('llm-jobs.sqlite3',LLMService),('voice-jobs.sqlite3',ElevenService),('reviews.sqlite3',lambda p:ReviewService(p,media_root=self.root/'media'))]
        for index,(name,service) in enumerate(expected):
            workspace = parent/('state-'+str(index));value = service(workspace)
            try:
                self.assertEqual(stat.S_IMODE(workspace.stat().st_mode),0o700)
                for path in workspace.rglob('*.sqlite3'):self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
                self.assertTrue((workspace/name).exists())
            finally:
                if isinstance(value,Dashboard):value.clear_keys();value.eleven.broker.clear();value.llm.close();value.close_local_log();value.renders.close();value.reviews.close()
                elif hasattr(value,'close'):value.close()
                elif hasattr(value,'broker'):value.broker.clear()
        self.assertEqual(stat.S_IMODE(parent.stat().st_mode),0o755)
        self.assertEqual(stat.S_IMODE(static.stat().st_mode),0o644)
        self.assertEqual(before,(parent.stat().st_mode,static.stat().st_mode,static.read_bytes()))

    def test_existing_permissive_workspace_refuses_without_chmod_or_any_db_open(self):
        for mode in (0o755,0o750,0o770,0o777):
            root = self.root/str(mode);root.mkdir(mode=mode);root.chmod(mode)
            before = root.stat()
            with patch('sqlite3.connect',side_effect=AssertionError('Unsafe mode reached SQLite')),self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_PERMISSIONS') as error:
                Store(root)
            self.assertNotIn(str(root),str(error.exception));self.assertIn('manual',str(error.exception))
            self.assertEqual(stat.S_IMODE(root.stat().st_mode),mode);self.assertEqual(root.stat().st_mtime_ns,before.st_mtime_ns);self.assertEqual(list(root.iterdir()),[])

    def test_db_sidecar_lock_and_control_directory_modes_fail_before_mutation(self):
        for name in ('jobs.sqlite3','jobs.sqlite3-wal','jobs.sqlite3-shm','jobs.sqlite3-journal','.workflow.lock','writing/llm-jobs.sqlite3','family-renders/jobs.sqlite3','family-inputs/input.json','family-receipts/receipt.json'):
            with self.subTest(name=name):
                root=self.root/(name.replace('/','-'));private_directory(root)
                target=root/name;private_directory(target.parent);target.write_bytes(b'Original fixture');target.chmod(0o644)
                before=(target.read_bytes(),target.stat().st_mtime_ns,target.stat().st_mode)
                with patch('sqlite3.connect',side_effect=AssertionError('Unsafe state reached DB')),self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_PERMISSIONS'):Store(root)
                self.assertEqual(before,(target.read_bytes(),target.stat().st_mtime_ns,target.stat().st_mode))
        root=self.root/'bad-directory';private_directory(root);directory=root/'writing';directory.mkdir(mode=0o755)
        directory.chmod(0o755)  # Deliberately unsafe test fixture, not a runtime repair.
        before=(directory.stat().st_mode,directory.stat().st_mtime_ns)
        with patch('sqlite3.connect',side_effect=AssertionError('Unsafe directory reached DB')),self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_PERMISSIONS'):Store(root)
        self.assertEqual(before,(directory.stat().st_mode,directory.stat().st_mtime_ns))
        self.assertEqual(list(directory.iterdir()),[])

    def test_valid_private_state_reopens_and_closes_with_no_mode_repair(self):
        root=self.root/'valid'
        with Store(root) as store:
            store.event(None,'synthetic','one');connection=store.db
        with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')
        before=modes(root)
        with Store(root) as store:self.assertEqual(store.db.execute('SELECT count(*) FROM events').fetchone()[0],1)
        self.assertEqual(modes(root),before)

    def test_owner_type_links_alias_and_pinned_ancestor_gates_remain(self):
        root=self.root/'valid';private_directory(root);external=self.root/'outside';external.write_bytes(b'Keep original');external.chmod(0o600)
        for hardlink in (False,True):
            target=root/'jobs.sqlite3'
            if hardlink:os.link(external,target)
            else:target.symlink_to(external)
            before=(external.read_bytes(),external.stat().st_mtime_ns)
            with self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):Store(root)
            self.assertEqual(before,(external.read_bytes(),external.stat().st_mtime_ns));target.unlink()
        with patch('storymotion.local_state.os.getuid',return_value=os.getuid()+1),self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):Store(root)
        alias=self.root/'alias';alias.symlink_to(root,target_is_directory=True)
        self.assertEqual(guard_workspace(alias),root)
        with self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):guard_workspace(alias,canonical_alias=False)
        (root/'writing').symlink_to(self.root,target_is_directory=True)
        with self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):Store(root)

    def test_private_write_rejects_existing_bad_mode_and_preserves_atomic_failures(self):
        path=self.root/'draft.txt';path.write_text('Old fixture');path.chmod(0o644);before=(path.read_bytes(),path.stat().st_mtime_ns)
        with self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_PERMISSIONS'):write_private(path,'New')
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before);self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o644)
        path.chmod(0o600)  # Test-owned fixture only, never a runtime repair.
        with patch('storymotion.local_state.os.fsync',side_effect=OSError('Synthetic sync failure')):
            with self.assertRaises(OSError):write_private(path,'New')
        self.assertEqual(path.read_bytes(),b'Old fixture');self.assertEqual(list(self.root.glob('.draft.*.tmp')),[])
        # General static/source path checks retain their original public policy.
        static=self.root/'static';static.mkdir(mode=0o755);source=static/'source.py';source.write_text('Original source')
        self.assertEqual(guard_control(static,'source.py'),source)

    def test_actual_temp_copy_modes_sync_and_no_clobber_without_source_mode_changes(self):
        seen=[];real_sync=os.fsync
        def sync(descriptor):
            info=os.fstat(descriptor);seen.append(('dir' if stat.S_ISDIR(info.st_mode) else 'file',stat.S_IMODE(info.st_mode)))
            return real_sync(descriptor)
        with patch('storymotion.local_state.os.fsync',side_effect=sync):write_private(self.root/'private.txt','Synthetic state')
        self.assertEqual(seen,[('file',0o600),('dir',0o700)])
        source=self.root/'source.txt';source.write_text('Original input');source.chmod(0o644)
        target=self.root/'copy.txt';copy_private(source,target)
        self.assertEqual(target.read_bytes(),source.read_bytes());self.assertEqual(stat.S_IMODE(target.stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE(source.stat().st_mode),0o644)
        with self.assertRaisesRegex(WorkflowError,'COPY_TARGET_EXISTS'):copy_private(source,target)
        self.assertEqual(target.read_bytes(),b'Original input')

    def test_prepared_sensitive_sources_are_0600_and_static_vendor_copies_stay_public(self):
        import test_family_history_http as fixtures
        vendor=ROOT/'vendor/gsap.min.js';original=(vendor.read_bytes(),vendor.stat().st_mode)
        for mask in (0o022,0o077):
            with self.subTest(umask=oct(mask)),fixture_umask(mask):
                case=fixtures.FamilyHistoryHttpTests('test_empty_history_is_read_only_and_does_not_create_engine_store')
                case.setUp();self.addCleanup(case.doCleanups)
                _,result=case.prepare();detail=case.detail(result)
                self.assertEqual(detail['artifacts_status'],'verified')
                out=case.root/'family-renders'/result['job']
                for name in ('index.html','cover.svg','cover.html','caption.txt','subtitles.srt','BRIEF.md','profile.json','template-selection.json','writing-context.json'):
                    self.assertEqual(stat.S_IMODE((out/name).stat().st_mode),0o600,name)
                self.assertEqual(stat.S_IMODE(out.stat().st_mode),0o700)
                # copytree preserves the source's mode, including a private checkout.
                copy=out/'assets/gsap.min.js'
                self.assertEqual(stat.S_IMODE(copy.stat().st_mode),stat.S_IMODE(original[1]))
                self.assertEqual(copy.read_bytes(),original[0])
                receipt=case.root/'family-receipts'/(result['job']+'.json')
                self.assertEqual(stat.S_IMODE(receipt.stat().st_mode),0o600)
        self.assertEqual((vendor.read_bytes(),vendor.stat().st_mode),original)

    def test_readonly_history_rejects_bad_root_db_input_and_generated_file_modes_without_repair(self):
        import test_family_history_http as fixtures
        case=fixtures.FamilyHistoryHttpTests('test_empty_history_is_read_only_and_does_not_create_engine_store')
        case.setUp();self.addCleanup(case.doCleanups)
        _,result=case.prepare();detail=case.detail(result);url=detail['files'][0]['download_url']
        inputs=list((case.root/'family-inputs').glob('*.json'));self.assertEqual(len(inputs),1)
        targets=[(case.root,0o755,0o700),(case.root/'family-renders/jobs.sqlite3',0o644,0o600),
                 (inputs[0],0o644,0o600),(case.root/'family-receipts'/(result['job']+'.json'),0o644,0o600),
                 (case.root/'family-renders'/result['job']/'cover.svg',0o644,0o600)]
        for target,bad,good in targets:
            target.chmod(bad)  # All paths belong to this isolated test fixture.
            before=case.snapshot();info=target.stat()
            code,value,raw=case.get(result['detail_url'])
            self.assertTrue(code==400 or value.get('artifacts_status')=='unavailable')
            self.assertEqual(case.get(url)[0],400)
            self.assertNotIn(str(case.root).encode(),raw)
            self.assertEqual(case.snapshot(),before)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode),bad)
            self.assertEqual(target.stat().st_mtime_ns,info.st_mtime_ns)
            target.chmod(good)
            self.assertEqual(case.detail(result)['artifacts_status'],'verified')
