"""Synthetic update/recovery regressions; never invoke an installer or renderer."""
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from storymotion import install_policy, source_update as update
from storymotion.security import WorkflowError


class RecoverySecurityAdditions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.old = self.root / 'old'
        (self.old / 'work').mkdir(parents=True)
        (self.old / 'work' / 'customer.txt').write_text('Synthetic preserved work')
        self.archive = self.root / 'release.zip'
        self.prefix = 'storymotion-1.2.3'
        self.files = {
            'LICENSE': b'Synthetic test terms; no actual agreement.\n',
            'THIRD-PARTY-NOTICES.md': b'Synthetic notices.\n',
            'package.json': b'{"name":"storymotion","version":"1.2.3"}',
            'package-lock.json': b'{"lockfileVersion":3}',
            'storymotion/__init__.py': b'__version__="1.2.3"\n',
        }
        self.manifest = {
            'version': '1.2.3', 'customer_release_ready': True,
            'rights_pending': False,
            'files': {n: hashlib.sha256(b).hexdigest() for n, b in self.files.items()},
        }

    def archive_bytes(self, manifest=None):
        with zipfile.ZipFile(self.archive, 'w') as out:
            for name, data in self.files.items():
                out.writestr(self.prefix + '/' + name, data)
            out.writestr(self.prefix + '/SOURCE-MANIFEST.json', manifest or json.dumps(self.manifest))
        return hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def snapshot(self, root):
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def test_interrupted_stage_preserves_partial_and_old_data_then_new_selection_recovers(self):
        digest = self.archive_bytes()
        first = self.root / 'failed'
        old = self.snapshot(self.old)
        with patch('storymotion.archive_safety.os.fsync', side_effect=OSError('synthetic failure')):
            with self.assertRaisesRegex(WorkflowError, 'UPDATE_STAGING_INCOMPLETE'):
                update.stage_update(self.archive, first, digest, active_root=self.old)
        partial = self.snapshot(first)
        self.assertTrue(partial)
        with self.assertRaisesRegex(WorkflowError, 'UPDATE_TARGET_EXISTS'):
            update.stage_update(self.archive, first, digest, active_root=self.old)
        second = self.root / 'explicit-new-target'
        state = update.stage_update(self.archive, second, digest, active_root=self.old)
        self.assertEqual(state['status'], 'staged_no_execution')
        self.assertTrue(update.verify_update(self.archive, second, digest, active_root=self.old)['ok'])
        self.assertEqual(self.snapshot(first), partial)
        self.assertEqual(self.snapshot(self.old), old)

    def test_replaced_archive_path_cannot_replace_already_verified_extraction_bytes(self):
        digest = self.archive_bytes()
        original = update._source
        def swap(*args):
            validated = original(*args)
            self.archive.write_bytes(b'Synthetic replaced archive path')
            return validated
        with patch.object(update, '_source', side_effect=swap):
            state = update.stage_update(self.archive, self.root / 'next', digest, active_root=self.old)
        self.assertEqual(state['status'], 'staged_no_execution')
        self.assertEqual((self.root / 'next' / self.prefix / 'LICENSE').read_bytes(), self.files['LICENSE'])
        self.assertEqual(state['archive_sha256'], digest)

    def test_duplicate_manifest_admission_fields_fail_before_staging(self):
        text = json.dumps(self.manifest).replace(
            '"customer_release_ready": true',
            '"customer_release_ready": false, "customer_release_ready": true',
        )
        self.assertEqual(text.count('"customer_release_ready"'), 2)
        digest = self.archive_bytes(text)
        destination = self.root / 'next'
        with self.assertRaises(WorkflowError):
            update.stage_update(self.archive, destination, digest, active_root=self.old)
        self.assertFalse(destination.exists())

    def test_duplicate_local_manifest_cannot_authorize_eula(self):
        root = self.root / 'synthetic-install'
        root.mkdir()
        raw = self.files['LICENSE']
        (root / 'LICENSE').write_bytes(raw)
        sha = hashlib.sha256(raw).hexdigest()
        text = json.dumps(self.manifest).replace(
            '"customer_release_ready": true',
            '"customer_release_ready": false, "customer_release_ready": true',
        )
        (root / 'SOURCE-MANIFEST.json').write_text(text)
        with self.assertRaises(WorkflowError):
            install_policy.require_owner_terms(root, sha)

    def test_nested_duplicate_and_nonfinite_manifest_refusal_agrees_across_consumers(self):
        raw=json.dumps(self.manifest);sha=hashlib.sha256(self.files['LICENSE']).hexdigest()
        root=self.root/'local';root.mkdir();(root/'LICENSE').write_bytes(self.files['LICENSE'])
        variants=[raw.replace('"LICENSE": ', '"LICENSE":"'+'0'*64+'", "LICENSE": ',1),
                  raw[:-1]+',"qualification":{"scope":{"engine":"remotion","engine":"hyperframes"}}}',
                  raw[:-1]+',"unused":NaN}']
        for index,text in enumerate(variants):
            digest=self.archive_bytes(text);destination=self.root/('next-'+str(index))
            with self.subTest(index=index),self.assertRaises(WorkflowError):
                update.stage_update(self.archive,destination,digest,active_root=self.old)
            self.assertFalse(destination.exists());(root/'SOURCE-MANIFEST.json').write_text(text)
            with self.assertRaises(WorkflowError):install_policy.require_owner_terms(root,sha)

    def test_nested_dependency_and_package_duplicates_are_not_install_or_update_metadata(self):
        root=self.root/'graph';root.mkdir()
        (root/'package.json').write_text('{"dependencies":{"hyperframes":"1","hyperframes":"2"}}')
        (root/'package-lock.json').write_text('{"packages":{}}')
        with self.assertRaisesRegex(WorkflowError,'INSTALL_METADATA_INVALID'):
            install_policy.graph_plan('core',root=root)
        self.files['package.json']=b'{"name":"other","name":"storymotion","version":"1.2.3"}'
        self.manifest['files']['package.json']=hashlib.sha256(self.files['package.json']).hexdigest()
        digest=self.archive_bytes()
        with self.assertRaises(WorkflowError):update.stage_update(self.archive,self.root/'next',digest,active_root=self.old)
        self.assertFalse((self.root/'next').exists())


if __name__ == '__main__':
    unittest.main()
