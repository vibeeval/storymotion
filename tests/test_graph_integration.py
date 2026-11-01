"""Separated namespaces and resume controls over owned offline fixtures."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from storymotion import runtime
from storymotion.install_policy import dependency_plan,graph_plan,graph_receipt
from storymotion.security import WorkflowError
from runtime_fixture import ROOT,copy_metadata,packages,receipts
class GraphIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve();copy_metadata(self.root);packages(self.root)
        (self.root/'.runtime').mkdir()
    def test_hf_only_ignores_unselected_addon_metadata_and_runs_only_core_npm(self):
        (self.root/'optional/remotion/package-lock.json').write_text('malformed unselected addon')
        state=dependency_plan(root=self.root);self.assertTrue(state['dependency_graph_ready']);self.assertEqual([g['graph'] for g in state['graphs']],['core'])
        with patch('storymotion.engine.checked_process',return_value=b'') as run:
            actions=runtime.install_graphs(root=self.root)
        self.assertEqual(actions,[{'graph':'core','action':'installed'}]);self.assertEqual(run.call_count,1);self.assertEqual(run.call_args.args[1],self.root)
        self.assertTrue((self.root/'.runtime/npm-core.json').is_file());self.assertFalse((self.root/'.runtime/npm-remotion.json').exists())
    def test_explicit_addon_reuses_core_and_failure_retains_core_receipt_and_work(self):
        receipts(self.root,'hyperframes');core=self.root/'.runtime/npm-core.json';before=(core.read_bytes(),core.stat().st_mtime_ns)
        work=self.root/'work/original';work.parent.mkdir();work.write_bytes(b'original user work');saved=(work.read_bytes(),work.stat().st_mtime_ns)
        with patch('storymotion.engine.checked_process',side_effect=WorkflowError('synthetic addon interrupted')) as run:
            with self.assertRaisesRegex(WorkflowError,'addon interrupted'):runtime.install_graphs('remotion',root=self.root)
        self.assertEqual(run.call_count,1);self.assertEqual(run.call_args.args[1],self.root/'optional/remotion');self.assertEqual(before,(core.read_bytes(),core.stat().st_mtime_ns));self.assertEqual(saved,(work.read_bytes(),work.stat().st_mtime_ns))
        self.assertTrue(runtime.graph_npm_ready(self.root,graph_plan('core',root=self.root)));self.assertFalse((self.root/'.runtime/npm-remotion.json').exists())
        with patch('storymotion.engine.checked_process',return_value=b'') as retry:actions=runtime.install_graphs('remotion',root=self.root)
        self.assertEqual([a['action'] for a in actions],['reused','installed']);self.assertEqual(retry.call_count,1)
    def test_manifest_change_invalidates_receipt_and_implicit_dual_graph_is_refused(self):
        receipts(self.root);path=self.root/'package.json';value=json.loads(path.read_text());value['description']='synthetic metadata change';path.write_text(json.dumps(value))
        self.assertFalse(runtime.graph_npm_ready(self.root,graph_plan('core',root=self.root)))
        lock=self.root/'package-lock.json';value=json.loads(lock.read_text());value['packages']['node_modules/remotion']={'version':'4.0.537'};lock.write_text(json.dumps(value))
        with patch('storymotion.engine.checked_process') as run:
            with self.assertRaisesRegex(WorkflowError,'CORE_LOCK_REQUIRES_REMOTION'):runtime.install_graphs(root=self.root)
            run.assert_not_called()
    def test_invalid_graph_and_linked_addon_metadata_fail_without_tools(self):
        with self.assertRaisesRegex(WorkflowError,'INSTALL_GRAPH_INVALID'):graph_plan('unknown',root=self.root)
        path=self.root/'optional/remotion/package-lock.json';path.unlink();path.symlink_to(self.root/'package-lock.json')
        with self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):dependency_plan('remotion',root=self.root)
        self.assertTrue(dependency_plan(root=self.root)['dependency_graph_ready'])
    @unittest.skipUnless(shutil.which('node'),'Node required for isolated addon resolution test')
    def test_remotion_tool_loads_addon_modules_and_template_resolver_after_runtime_gate(self):
        # Run real renderer script with synthetic local modules, never a browser.
        tools=self.root/'tools';tools.mkdir();shutil.copyfile(ROOT/'tools/remotion.mjs',tools/'remotion.mjs')
        (self.root/'renderers/remotion').mkdir(parents=True);(self.root/'renderers/remotion/entry.jsx').write_text('synthetic bounded template')
        job=self.root/'job';job.mkdir();(job/'remotion-props.json').write_text('{"brief":{"duration":3}}')
        (tools/'runtime.mjs').write_text("import {fileURLToPath} from 'node:url';import {resolve,dirname,join} from 'node:path';export const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');export const addonRoot=join(root,'optional/remotion');export function requireRuntime(engine){if(engine!=='remotion')throw Error('wrong gate');return {browser:'synthetic-controlled-browser'};}")
        bundler=self.root/'optional/remotion/node_modules/@remotion/bundler';renderer=bundler.parent/'renderer'
        bundler.mkdir(parents=True,exist_ok=True);renderer.mkdir(parents=True,exist_ok=True)
        (bundler/'index.js').write_text("const assert=require('node:assert/strict');exports.bundle=async options=>{const config=options.webpackOverride({resolve:{modules:['node_modules']}});assert.ok(config.resolve.modules[0].endsWith('/optional/remotion/node_modules'));assert.ok(options.entryPoint.endsWith('/renderers/remotion/entry.jsx'));assert.equal(options.enableCaching,false);return 'synthetic-local-bundle';};")
        (renderer/'index.js').write_text("const assert=require('node:assert/strict');exports.openBrowser=async(name,options)=>{assert.equal(options.browserExecutable,'synthetic-controlled-browser');return {close:async()=>{}}};exports.selectComposition=async()=>({width:1080,height:1920,fps:30,durationInFrames:90});exports.renderStill=async()=>{};exports.renderMedia=async()=>{};")
        for folder in (bundler,renderer):(folder/'package.json').write_text('{"main":"index.js"}')
        value=subprocess.run(['node',str(tools/'remotion.mjs'),'check',str(job)],capture_output=True,text=True,timeout=20,env={k:v for k,v in os.environ.items() if k in {'PATH','HOME','TMPDIR'}})
        self.assertEqual(value.returncode,0,value.stderr);result=json.loads(value.stdout);self.assertEqual(result['sample_frames'],[0,45,89]);self.assertEqual(result['paid_provider_calls'],0)
