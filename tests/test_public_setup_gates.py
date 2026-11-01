"""Public setup entrypoints use real admission checks and mocked execution only."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from storymotion import __main__ as cli
from storymotion.security import WorkflowError
from tools import first_run


class PublicSetupGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        contents = {
            'LICENSE': 'MIT License\n\nSynthetic source identity fixture.\n',
            'THIRD-PARTY-NOTICES.md': 'Third-party terms remain separate.\n',
            'assets-lock.json': '{}\n',
            'package.json': '{}\n',
            'package-lock.json': '{}\n',
            'install.sh': '# Synthetic fixture, never executed.\n',
            'tools/first_run.py': '# Synthetic fixture, never executed.\n',
            'storymotion/install_policy.py': '# Synthetic fixture, never executed.\n',
        }
        hashes = {}
        for relative, text in contents.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = text.encode('utf-8')
            path.write_bytes(raw)
            hashes[relative] = hashlib.sha256(raw).hexdigest()
        self.license_hash = hashes['LICENSE']
        self.manifest = {
            'version': '0.14.1', 'source_distribution_schema': 1,
            'status': 'installable_source_distribution', 'source_commit': 'f' * 40,
            'customer_release_ready': False, 'rights_pending': True,
            'publication_ready': False, 'native_acceptance': 'unverified',
            'browser_acceptance': 'unverified', 'independent_review': 'pending',
            'files': hashes,
        }
        self.write_manifest(self.manifest)
        self.plan = {'dependency_graph_ready': True, 'blockers': []}
        self.preflight = self.start_patch(patch.object(
            first_run, 'preflight',
            return_value={'ok': False, 'prerequisites': {'ok': True}}))
        self.start_patch(patch.object(first_run, 'ROOT', self.root))
        self.dependency_plan = self.start_patch(patch(
            'storymotion.install_policy.dependency_plan', return_value=self.plan))
        # An install command must not create the ordinary job Engine/workspace.
        self.engine = self.start_patch(patch.object(
            cli, 'Engine', side_effect=AssertionError('No job Engine during setup')))
        self.setup = self.start_patch(patch(
            'storymotion.runtime.setup',
            return_value={'ok': True, 'setup': 'mocked_execution_boundary'}))

    def start_patch(self, patcher):
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def write_manifest(self, value):
        (self.root / 'SOURCE-MANIFEST.json').write_text(json.dumps(value), encoding='utf-8')

    def call(self, arguments):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = cli.main(['setup', *arguments])
        self.engine.assert_not_called()
        return status, json.loads(output.getvalue())

    def valid_arguments(self, flag='--license-sha256'):
        return ['--allow-downloads', flag, self.license_hash]

    def assert_blocked(self, arguments, error):
        status, result = self.call(arguments)
        self.assertEqual(status, 2)
        self.assertFalse(result['ok'])
        self.assertIn(error, result['error'])
        self.setup.assert_not_called()

    def test_legacy_setup_without_flags_stops_before_execution(self):
        self.assert_blocked([], 'INSTALL_PERMISSION_REQUIRED')
        self.preflight.assert_called_once_with('hyperframes')

    def test_new_and_legacy_license_flags_reach_same_guarded_default_engine(self):
        for flag in ('--license-sha256', '--accept-eula-sha256'):
            with self.subTest(flag=flag):
                self.setup.reset_mock()
                status, result = self.call(self.valid_arguments(flag))
                self.assertEqual(status, 0)
                self.assertTrue(result['ok'])
                self.assertEqual(result['owner_terms']['license_sha256'], self.license_hash)
                self.setup.assert_called_once_with(if_needed=True, engine='hyperframes')

    def test_explicit_engine_and_skip_npm_reach_existing_receipt_gate(self):
        for engine in ('hyperframes', 'remotion', 'all'):
            with self.subTest(engine=engine):
                self.setup.reset_mock()
                status, result = self.call([
                    *self.valid_arguments(), '--engine', engine, '--skip-npm'])
                self.assertEqual(status, 0)
                self.assertTrue(result['ok'])
                self.setup.assert_called_once_with(
                    if_needed=True, engine=engine, skip_npm=True)

    def test_license_hash_does_not_authorize_downloads(self):
        self.assert_blocked(['--license-sha256', self.license_hash],
                            'INSTALL_PERMISSION_REQUIRED')

    def test_skip_npm_is_not_a_download_permission_bypass(self):
        self.assert_blocked(['--skip-npm', '--license-sha256', self.license_hash],
                            'INSTALL_PERMISSION_REQUIRED')

    def test_missing_license_hash_is_rejected(self):
        self.assert_blocked(['--allow-downloads'], 'EULA_ACCEPTANCE_REQUIRED')

    def test_mismatched_license_hash_is_rejected(self):
        self.assert_blocked(['--allow-downloads', '--license-sha256', '0' * 64],
                            'EULA_ACCEPTANCE_REQUIRED')

    def test_missing_source_manifest_is_rejected(self):
        (self.root / 'SOURCE-MANIFEST.json').rename(self.root / 'fixture-manifest.json')
        self.assert_blocked(self.valid_arguments(), 'OWNER_RELEASE_PENDING')

    def test_unqualified_manifest_is_rejected(self):
        self.write_manifest(dict(self.manifest, status='private_source_review_candidate'))
        self.assert_blocked(self.valid_arguments(), 'OWNER_RELEASE_PENDING')

    def test_changed_manifested_source_is_rejected(self):
        (self.root / 'tools/first_run.py').write_text('# changed source\n', encoding='utf-8')
        self.assert_blocked(self.valid_arguments(), 'INSTALL_SOURCE_HASH_MISMATCH')

    def test_blocked_dependency_plan_is_rejected(self):
        self.dependency_plan.return_value = {
            'dependency_graph_ready': False, 'blockers': ['SYNTHETIC_BLOCKER']}
        self.assert_blocked(self.valid_arguments(), 'DEPENDENCY_PLAN_BLOCKED')

    def test_existing_skip_npm_receipt_failure_is_preserved(self):
        self.setup.side_effect = WorkflowError('RUNTIME_NPM_RECEIPT_REQUIRED')
        status, result = self.call([*self.valid_arguments(), '--skip-npm'])
        self.assertEqual(status, 2)
        self.assertIn('RUNTIME_NPM_RECEIPT_REQUIRED', result['error'])
        self.setup.assert_called_once_with(
            if_needed=True, engine='hyperframes', skip_npm=True)

    def test_npm_setup_uses_the_same_guarded_public_command(self):
        package = json.loads((Path(__file__).resolve().parents[1] / 'package.json').read_text())
        self.assertEqual(package['scripts']['setup'], 'python3 -m storymotion setup')
        self.assert_blocked([], 'INSTALL_PERMISSION_REQUIRED')


if __name__ == '__main__':
    unittest.main()
