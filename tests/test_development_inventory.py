"""Observed npm 10 inventory regression, using metadata-only offline fixtures."""
import copy
import json
import subprocess
from unittest.mock import patch

import test_development_policy as fixture
from storymotion import development_policy as dev, development_setup as setup
from storymotion.local_state import private_directory, write_private
from storymotion.security import WorkflowError, canonical


EXTRAS = {'node_modules/@emnapi/runtime':('1.11.3','MIT'),
          'node_modules/@img/sharp-wasm32':('0.35.5','Apache-2.0 AND LGPL-3.0-or-later AND MIT')}


class DevelopmentInventoryTests(fixture.FixtureCase):
    def js_ready(self,platform=('darwin','arm64')):
        # FixtureCase already mocks Python's platform. Match only this pure JS
        # receipt inspection; None preserves the child process's actual target.
        return self.node_eval('(()=>{if(x.platform){Object.defineProperty(process,"platform",{value:x.platform[0]});'
                              'Object.defineProperty(process,"arch",{value:x.platform[1]});}return d.npmReady(x.root);})()',
                              {'root':str(self.root),'platform':platform})

    def js_accepts(self):
        return self.node_eval('(()=>{try{d.installedPackages(x);return true;}catch{return false;}})()',str(self.root))

    def refused(self):
        with self.assertRaises(WorkflowError):setup.installed_packages(self.root)
        self.assertFalse(self.js_accepts())

    def test_platform_unrestricted_optional_entries_complete_the_observed_94(self):
        rows = dev.installation_artifacts(self.root)
        self.assertEqual(len(rows),94)
        self.assertEqual(self.node_eval('d.installationArtifacts(x)',str(self.root)),rows)
        lock = json.loads((self.root/'package-lock.json').read_text())['packages']
        for path,(version,license_name) in EXTRAS.items():
            self.assertEqual(rows[path]['version'],version);self.assertEqual(rows[path]['license'],license_name)
            self.assertIs(lock[path]['optional'],True)
            self.assertNotIn('os',lock[path]);self.assertNotIn('cpu',lock[path])
        self.assertNotIn('node_modules/@img/sharp-freebsd-wasm32',rows)
        self.assertNotIn('node_modules/@img/sharp-webcontainers-wasm32',rows)
        self.packages()
        self.assertEqual(set(setup.installed_packages(self.root)),set(rows));self.assertTrue(self.js_accepts())

    def test_observed_mock_npm_install_mints_exact_ignored_scripts_receipt(self):
        def npm(argv,**kw):
            self.assertNotIn('NODE_OPTIONS',kw['env']);self.assertNotIn('NPM_TOKEN',kw['env'])
            if argv[-1]=='--version':return subprocess.CompletedProcess(argv,0,(self.node_version+'\n').encode(),b'')
            self.assertEqual(argv[:4],['npm','ci','--ignore-scripts','--include=optional'])
            self.packages()
            for path,(version,_) in EXTRAS.items():
                self.assertEqual(json.loads((self.root/path/'package.json').read_text())['version'],version)
            return subprocess.CompletedProcess(argv,0,b'added 94 packages in 8s\n',b'')
        with patch.object(setup,'run_process',side_effect=npm) as run:
            value = setup.install_npm(self.root,self.approval('npm'))
        self.assertEqual(run.call_count,2);self.assertEqual(value['lifecycle_scripts_executed'],[])
        receipt = json.loads((self.root/'.runtime/npm-core.json').read_text())
        self.assertEqual(len(receipt['installed_packages']),94);self.assertEqual(receipt['schema_version'],4)
        self.assertEqual(receipt['lifecycle_allowlist'],[]);self.assertEqual(receipt['npm_mode'],'ignore_scripts')
        self.assertTrue(setup.npm_ready(self.root));self.assertTrue(self.js_ready())
        self.assertTrue(all(value[name] is False for name in dev.FLAGS))

    def test_missing_new_optional_or_required_native_artifact_fails_closed(self):
        self.packages()
        for path in (*EXTRAS,'node_modules/@img/sharp-darwin-arm64'):
            with self.subTest(path=path):
                folder = self.root/path;raw = (folder/'package.json').read_bytes()
                (folder/'package.json').unlink();folder.rmdir()
                self.refused()
                private_directory(folder);write_private(folder/'package.json',raw)

    def test_foreign_platform_remotion_and_unknown_additions_are_never_allowed(self):
        self.packages()
        for name,version in (('@img/sharp-darwin-x64','0.35.5'),('@img/sharp-webcontainers-wasm32','0.35.5'),
                             ('@esbuild/linux-arm64','0.25.12'),('@remotion/renderer','4.0.0'),('unlisted-package','1.0.0')):
            with self.subTest(name=name):
                folder = self.root/'node_modules'/name;private_directory(folder)
                write_private(folder/'package.json',canonical({'name':name,'version':version}))
                self.refused()
                (folder/'package.json').unlink();folder.rmdir()

    def test_wrong_names_versions_and_malformed_extra_package_metadata_fail(self):
        self.packages()
        for path,(version,_) in EXTRAS.items():
            name = path[len('node_modules/'):];file = self.root/path/'package.json'
            valid = {'name':name,'version':version}
            for bad in (None,[],dict(valid,name='foreign'),dict(valid,version='1.0.0'),dict(valid,version=True)):
                with self.subTest(path=path,bad=bad):
                    write_private(file,canonical(bad));self.refused()
            write_private(file,canonical(valid))

    def test_modified_lock_or_evidence_cannot_expand_the_install_inventory(self):
        self.packages()
        for name in ('package-lock.json',dev.EVIDENCE_PATH):
            path = self.root/name;raw = path.read_bytes();value = json.loads(raw)
            rows = value['packages'] if name=='package-lock.json' else value['artifacts']
            for field,replacement in (('version','99.0.0'),('integrity','sha512-untrusted'),('resolved','https://example.invalid/package.tgz')):
                changed = copy.deepcopy(value);changed_rows = changed['packages'] if name=='package-lock.json' else changed['artifacts']
                changed_rows['node_modules/@img/sharp-wasm32'][field]=replacement
                path.write_text(canonical(changed));self.refused();path.write_bytes(raw)
            changed = copy.deepcopy(value)
            (changed['packages'] if name=='package-lock.json' else changed['artifacts'])['node_modules/new-extra']=rows['node_modules/@emnapi/runtime']
            path.write_text(canonical(changed));self.refused();path.write_bytes(raw)

    def test_extra_payload_bytes_remain_bound_to_complete_tree_receipt(self):
        self.installed()
        self.assertTrue(setup.npm_ready(self.root));self.assertTrue(self.js_ready())
        write_private(self.root/'node_modules/@img/sharp-wasm32/changed.js','synthetic changed bytes; never executed')
        self.assertFalse(setup.npm_ready(self.root));self.assertFalse(self.js_ready())

    def test_matching_receipt_still_refuses_unsupported_actual_and_simulated_platforms(self):
        self.installed();self.assertTrue(self.js_ready())
        actual = self.node_eval('[process.platform,process.arch]')
        self.assertEqual(self.js_ready(None),actual==['darwin','arm64'])
        for target in (('linux','x64'),('linux','arm64'),('darwin','x64'),('win32','arm64')):
            with self.subTest(target=target):self.assertFalse(self.js_ready(target))

    def test_old_92_package_receipt_and_static_binary_cannot_pass(self):
        value = self.installed();receipt = self.root/'.runtime/npm-core.json'
        value['installed_packages']=[path for path in value['installed_packages'] if path not in EXTRAS]
        self.assertEqual(len(value['installed_packages']),92)
        write_private(receipt,canonical(value));self.assertFalse(setup.npm_ready(self.root))
        self.assertFalse(self.js_ready())
        write_private(self.root/'node_modules/ffmpeg-static/ffmpeg','synthetic excluded binary; never executed')
        self.refused()

    def test_wrong_extra_version_after_npm_cannot_mint_success_receipt(self):
        def npm(argv,**kw):
            if argv[-1]=='--version':return subprocess.CompletedProcess(argv,0,(self.node_version+'\n').encode(),b'')
            self.packages();path = 'node_modules/@img/sharp-wasm32/package.json'
            write_private(self.root/path,canonical({'name':'@img/sharp-wasm32','version':'0.35.4'}))
            return subprocess.CompletedProcess(argv,0,b'added 94 packages\n',b'')
        with patch.object(setup,'run_process',side_effect=npm),self.assertRaisesRegex(WorkflowError,'INSTALLED_ARTIFACT_CHANGED'):
            setup.install_npm(self.root,self.approval('npm'))
        self.assertFalse((self.root/'.runtime/npm-core.json').exists());self.assertFalse(setup.npm_ready(self.root))
