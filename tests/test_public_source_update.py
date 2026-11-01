"""A manifested common source tree stages without dropping its public tests."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

from storymotion import __version__
from storymotion import source_update as update
from storymotion.security import WorkflowError

ROOT = Path(__file__).resolve().parents[1]


class PublicSourceUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
        cls.payload = {n: (ROOT/n).read_bytes() for n in names
                       if n and n != 'SOURCE-MANIFEST.json' and (ROOT/n).is_file()}

    def archive(self, parent, extra=None):
        payload = dict(self.payload)
        payload.update(extra or {})
        manifest = {'version': __version__, 'source_distribution_schema': 1,
                    'status': 'installable_source_distribution', 'source_commit': 'a'*40,
                    'customer_release_ready': False, 'rights_pending': True,
                    'publication_ready': False, 'native_acceptance': 'unverified',
                    'browser_acceptance': 'unverified', 'independent_review': 'pending',
                    'files': {n: hashlib.sha256(raw).hexdigest() for n, raw in payload.items()}}
        payload['SOURCE-MANIFEST.json'] = json.dumps(manifest).encode()
        archive = parent/'source.zip';prefix = 'storymotion-'+__version__
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for name, raw in payload.items():
                z.writestr(prefix+'/'+name, raw)
        return archive, hashlib.sha256(archive.read_bytes()).hexdigest(), payload, prefix

    def test_full_tracked_tree_stage_verify_and_tamper_preserve_old_work(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp).resolve()
            work = parent/'existing-work';work.mkdir();(work/'keep.txt').write_text('Keep original work')
            archive, digest, payload, prefix = self.archive(parent)
            target = parent/'new-source'
            result = update.stage_update(archive, target, digest, active_root=ROOT, protected_workspaces=[work])
            self.assertTrue(result['ok']);self.assertFalse(result['downloads'])
            self.assertEqual(result['provider_calls'], 0);self.assertFalse(result['eula_accepted'])
            self.assertGreater(sum(n.startswith('tests/') for n in payload), 100)
            for name, raw in payload.items():
                self.assertEqual((target/prefix/name).read_bytes(), raw)
            self.assertTrue(update.verify_update(archive, target, digest, active_root=ROOT, protected_workspaces=[work])['ok'])
            test_name = next(n for n in payload if n.startswith('tests/') and n.endswith('.py'))
            (target/prefix/test_name).write_text('Changed test source')
            with self.assertRaisesRegex(WorkflowError, 'UPDATE_TARGET_INCOMPLETE_OR_CHANGED'):
                update.verify_update(archive, target, digest, active_root=ROOT, protected_workspaces=[work])
            self.assertEqual((work/'keep.txt').read_text(), 'Keep original work')

    def test_test_support_is_bounded_and_private_or_runtime_paths_fail_before_writes(self):
        for name in ('tests/helper.py', 'tests/probe.mjs', 'tests/fixtures/example.json'):
            self.assertEqual(update._relative(name), name)
        for name in ('tests/.env', 'tests/private/customer.json', 'tests/node_modules/a.js',
                     'tests/credentials/key.json', 'tests/fixture.bin', 'tests/../outside.py'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                parent = Path(temp).resolve();archive,digest,_,_ = self.archive(parent, {name:b'synthetic unsafe entry'})
                target = parent/'refused'
                with self.assertRaises(WorkflowError):
                    update.stage_update(archive, target, digest, active_root=ROOT)
                self.assertFalse(target.exists())
