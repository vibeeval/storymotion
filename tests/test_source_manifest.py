"""Source packaging never grants runtime/rights acceptance or includes private data."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import build_source_manifest as builder
from storymotion.install_policy import owner_terms
from storymotion.security import WorkflowError


class SourceManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / '.git').mkdir()
        self.names = ['LICENSE', 'THIRD-PARTY-NOTICES.md', 'assets-lock.json',
                      'package.json', 'package-lock.json', 'install.sh',
                      'tools/first_run.py', 'storymotion/install_policy.py']
        for name in self.names:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Synthetic source fixture; not an agreement or actual rights grant.\n')
        self.dirty = ''

    def git(self, *args):
        if args == ('rev-parse', 'HEAD'):
            return 'a' * 40 + '\n'
        if args == ('ls-files', '-z'):
            return '\0'.join(self.names + [builder.MANIFEST]) + '\0'
        return self.dirty

    def build(self):
        with patch.object(builder, 'ROOT', self.root), patch.object(builder, 'git', self.git):
            return builder.build()

    def test_manifest_binds_payload_and_never_promotes_acceptance(self):
        result = self.build()
        value = json.loads((self.root / builder.MANIFEST).read_text())
        self.assertNotIn(builder.MANIFEST, value['files'])
        self.assertEqual(value['source_commit'], 'a' * 40)
        self.assertEqual(value['files']['LICENSE'], hashlib.sha256((self.root / 'LICENSE').read_bytes()).hexdigest())
        self.assertFalse(value['publication_ready'])
        self.assertFalse(value['customer_release_ready'])
        self.assertTrue(value['rights_pending'])
        self.assertEqual(value['native_acceptance'], 'unverified')
        self.assertTrue(owner_terms(self.root)['ready'])
        self.assertEqual(result['downloads'], 0)

    def test_uncommitted_payload_refused_without_creating_manifest(self):
        self.dirty = ' M package.json\n'
        with self.assertRaisesRegex(WorkflowError, 'SOURCE_PAYLOAD_MUST_BE_COMMITTED'):
            self.build()
        self.assertFalse((self.root / builder.MANIFEST).exists())

    def test_changed_manifest_alone_does_not_require_self_hash(self):
        self.dirty = '?? SOURCE-MANIFEST.json\n'
        self.assertEqual(self.build()['files'], len(self.names))

    def test_private_work_or_media_refused(self):
        for name in ('work/customer.json', '.env', 'voice.mp4', 'private/key.json'):
            with self.subTest(name=name):
                self.names.append(name)
                with self.assertRaisesRegex(WorkflowError, 'SOURCE_PRIVATE_OR_GENERATED_PATH_REFUSED'):
                    self.build()
                self.names.pop()

    def test_symlink_source_refused(self):
        outside = self.root / 'outside.txt'
        outside.write_text('synthetic outside source')
        (self.root / 'linked.txt').symlink_to(outside)
        self.names.append('linked.txt')
        with self.assertRaisesRegex(WorkflowError, 'SOURCE_LINK_OR_NONFILE_REFUSED'):
            self.build()
