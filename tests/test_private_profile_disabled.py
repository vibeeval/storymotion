"""Source-only refusal of the excluded historical private profile; no downloads."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from storymotion import development_policy as dev
from storymotion import runtime
from storymotion.security import WorkflowError

ROOT = Path(__file__).resolve().parents[1]
REASON = 'PRIVATE_PROFILE_NOT_DISTRIBUTED'


class PrivateProfileDisabledTests(unittest.TestCase):
    def test_private_authorization_fails_before_excluded_files_are_read(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(dev, 'strict_json', side_effect=AssertionError('excluded file must not be read')):
                for action in (lambda: dev.policy(root), lambda: dev.recipe(root),
                               lambda: dev.gate(root), lambda: dev.installation_artifacts(root),
                               lambda: dev.authorize(root, 'setup', True, dev.POLICY_SHA),
                               lambda: dev.require_approval(root, None, 'setup')):
                    with self.subTest(action=action), self.assertRaisesRegex(WorkflowError, REASON):
                        action()
            self.assertEqual(list(root.iterdir()), [])
            self.assertFalse(dev.PRIVATE_PROFILE_AVAILABLE)

    def test_stale_namespaces_are_detected_and_do_not_fall_back_to_customer_runtime(self):
        for relative in ('.runtime/development', '.runtime/ffmpeg'):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                self.assertFalse(dev.development_mode(root))
                (root / relative).mkdir(parents=True)
                self.assertTrue(dev.development_mode(root))
                with patch.object(runtime, 'ROOT', root), patch.object(
                        runtime.subprocess, 'run', side_effect=AssertionError('no runtime subprocess')):
                    with self.assertRaisesRegex(WorkflowError, REASON):
                        runtime.media_binary('ffmpeg', 'hyperframes')
                    with self.assertRaisesRegex(WorkflowError, REASON):
                        runtime.process_env('hyperframes')
                    self.assertFalse(runtime.doctor('hyperframes')['ok'])
                    with self.assertRaisesRegex(WorkflowError, 'DEVELOPMENT_LEGACY_SETUP_REFUSED'):
                        runtime.setup()

    def test_broken_private_namespace_link_remains_detectable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.runtime').mkdir()
            (root / '.runtime/development').symlink_to(root / 'absent')
            self.assertTrue(dev.development_mode(root))
            with self.assertRaisesRegex(WorkflowError, REASON):
                dev.assert_process_scope(root)

    @unittest.skipUnless(shutil.which('node'), 'Node is not installed; no download attempted')
    def test_javascript_private_entry_points_refuse_before_reading_policy_or_receipts(self):
        script = r"""
const d=await import(process.argv[1]);
const names=['processEnvironment','policy','sourceBinding','sourceRecipe','mode',
 'installationArtifacts','installedPackages','installedTree','npmReceiptMatches',
 'npmReady','sourceFFmpeg','probeReceiptMatches','privateProbe','inspectDevelopment'];
const refused=[];
for(const name of names){
 try{d[name]('/nonexistent-private-root');throw new Error('private entry accepted: '+name);}
 catch(error){if(error.message!=='PRIVATE_PROFILE_NOT_DISTRIBUTED')throw error;refused.push(name);}
}
if(d.PRIVATE_PROFILE_AVAILABLE!==false||!d.developmentMode(process.argv[2]))throw Error('private namespace detection changed');
process.stdout.write(JSON.stringify({refused,available:d.PRIVATE_PROFILE_AVAILABLE}));
"""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.runtime/ffmpeg').mkdir(parents=True)
            result = subprocess.run([shutil.which('node'), '--input-type=module', '-e', script,
                                     (ROOT / 'tools/development-runtime.mjs').as_uri(), str(root)],
                                    capture_output=True, text=True, timeout=20, check=True)
            value = json.loads(result.stdout)
            self.assertEqual(len(value['refused']), 14)
            self.assertFalse(value['available'])


if __name__ == '__main__':
    unittest.main()
