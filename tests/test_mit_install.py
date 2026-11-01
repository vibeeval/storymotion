"""Source-license identity and download boundaries; no real install or network."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import first_run
from storymotion import install_policy
from storymotion.security import WorkflowError


class MitInstallTests(unittest.TestCase):
    def test_both_cli_names_forward_the_same_hash(self):
        digest = 'a' * 64
        for flag in ('--license-sha256', '--accept-eula-sha256'):
            with self.subTest(flag=flag), \
                    patch.object(first_run, 'install', return_value={'ok': True}) as install, \
                    contextlib.redirect_stdout(io.StringIO()):
                result = first_run.main([
                    'install', '--engine', 'hyperframes', '--allow-downloads', flag, digest])
                self.assertEqual(result, 0)
                install.assert_called_once_with(True, 'hyperframes', digest)

    def test_missing_and_mismatched_hash_still_fail(self):
        digest = 'a' * 64
        with patch.object(install_policy, 'owner_terms',
                          return_value={'ready': True, 'license_sha256': digest}):
            for value in (None, '', 'b' * 64, 'A' * 64):
                with self.subTest(value=value), \
                        self.assertRaisesRegex(WorkflowError, 'EULA_ACCEPTANCE_REQUIRED'):
                    install_policy.require_owner_terms(accepted_sha256=value)
            result = install_policy.require_owner_terms(accepted_sha256=digest)
            self.assertEqual(result['owner_eula_sha256'], result['license_sha256'])
            self.assertIn('no additional contract', result['scope'])

    def test_alias_does_not_authorize_downloads(self):
        with patch.object(first_run, 'preflight',
                          return_value={'ok': False, 'prerequisites': {'ok': True}}), \
                patch('storymotion.runtime.setup',
                      side_effect=AssertionError('No setup allowed')) as setup:
            with self.assertRaisesRegex(ValueError, 'INSTALL_PERMISSION_REQUIRED'):
                first_run.install(False, accepted_eula_sha256='a' * 64)
            setup.assert_not_called()

    def test_pending_source_manifest_still_blocks_setup(self):
        with patch.object(first_run, 'preflight',
                          return_value={'ok': False, 'prerequisites': {'ok': True}}), \
                patch.object(install_policy, 'owner_terms',
                             return_value={'ready': False, 'reason': 'OWNER_RELEASE_PENDING'}), \
                patch('storymotion.runtime.setup',
                      side_effect=AssertionError('No setup allowed')) as setup:
            with self.assertRaisesRegex(WorkflowError, 'OWNER_RELEASE_PENDING'):
                first_run.install(True, accepted_eula_sha256='a' * 64)
            setup.assert_not_called()

    def synthetic_source(self, root):
        files = {
            'LICENSE': 'MIT License\n\nSynthetic source-license identity fixture.\n',
            'THIRD-PARTY-NOTICES.md': 'Third-party terms remain separate.\n',
            'assets-lock.json': '{}\n',
            'package.json': '{}\n',
            'package-lock.json': '{}\n',
            'install.sh': '# Synthetic fixture, never executed.\n',
            'tools/first_run.py': '# Synthetic fixture, never executed.\n',
            'storymotion/install_policy.py': '# Synthetic fixture, never executed.\n',
        }
        hashes = {}
        for relative, text in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = text.encode('utf-8')
            path.write_bytes(raw)
            hashes[relative] = hashlib.sha256(raw).hexdigest()
        manifest = {
            'version': '0.14.1',
            'source_distribution_schema': 1,
            'status': 'installable_source_distribution',
            'source_commit': 'f' * 40,
            'customer_release_ready': False,
            'rights_pending': True,
            'publication_ready': False,
            'native_acceptance': 'unverified',
            'browser_acceptance': 'unverified',
            'independent_review': 'pending',
            'files': hashes,
        }
        (root / 'SOURCE-MANIFEST.json').write_text(json.dumps(manifest), encoding='utf-8')
        return manifest

    def test_valid_mit_source_manifest_without_git_or_customer_certification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            manifest = self.synthetic_source(root)
            self.assertFalse((root / '.git').exists())
            self.assertNotIn('SOURCE-MANIFEST.json', manifest['files'])
            state = install_policy.owner_terms(root)
            self.assertTrue(state['ready'])
            self.assertFalse(state['customer_release_ready'])
            self.assertTrue(state['rights_pending'])
            result = install_policy.require_owner_terms(root, manifest['files']['LICENSE'])
            self.assertEqual(result['license_sha256'], manifest['files']['LICENSE'])

    def test_changed_manifested_payload_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            self.synthetic_source(root)
            (root / 'tools/first_run.py').write_text('# changed payload\n', encoding='utf-8')
            with self.assertRaisesRegex(WorkflowError, 'INSTALL_SOURCE_HASH_MISMATCH'):
                install_policy.owner_terms(root)

    def test_installable_source_does_not_silently_promote_readiness_flags(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            manifest = self.synthetic_source(root)
            for field, value in (
                    ('publication_ready', True),
                    ('native_acceptance', 'pass'),
                    ('rights_pending', False)):
                with self.subTest(field=field):
                    changed = dict(manifest, **{field: value})
                    (root / 'SOURCE-MANIFEST.json').write_text(
                        json.dumps(changed), encoding='utf-8')
                    state = install_policy.owner_terms(root)
                    self.assertFalse(state['ready'])
                    self.assertEqual(state['reason'], 'OWNER_RELEASE_PENDING')


if __name__ == '__main__':
    unittest.main()
