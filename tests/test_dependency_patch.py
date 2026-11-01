"""Real graph pins, security override and coherent inventory; no network."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import unittest
from storymotion.install_policy import dependency_plan,owner_terms
ROOT=Path(__file__).resolve().parents[1]
class DependencyPatchTests(unittest.TestCase):
    def setUp(self):
        self.graphs={g:(p,json.loads((ROOT/p/'package.json').read_text()),json.loads((ROOT/p/'package-lock.json').read_text())) for g,p in [('core',Path('.')),('remotion',Path('optional/remotion'))]}
    def test_override_covers_every_zod_instance_above_reviewed_advisory_minimum(self):
        found=[]
        for graph,(path,package,lock) in self.graphs.items():
            self.assertEqual(package['overrides'],{'zod':'4.6.7'})
            for name,entry in lock['packages'].items():
                if name.endswith('/zod'):
                    found.append(name);self.assertGreaterEqual(tuple(map(int,entry['version'].split('.'))),(4,6,6))
                    self.assertEqual(entry['version'],package['overrides']['zod']);self.assertEqual(entry['resolved'],'https://registry.npmjs.org/zod/-/zod-'+entry['version']+'.tgz');self.assertTrue(entry['integrity'].startswith('sha512-'))
        self.assertTrue(found)
    def test_inventory_hash_and_exact_versions_sources_integrities_follow_generated_lock(self):
        inventory=json.loads((ROOT/'docs/DEPENDENCY-LOCK.json').read_text());rows={(r['graph'],r['package_path']):r for r in inventory['packages']}
        self.assertEqual(len(rows),len(inventory['packages']))
        expected={(g,n) for g,(_,_,lock) in self.graphs.items() for n in lock['packages'] if n};self.assertEqual(set(rows),expected)
        for (graph,name),row in rows.items():
            entry=self.graphs[graph][2]['packages'][name];self.assertEqual((row['version'],row['integrity'],row['registry_source']),(entry.get('version'),entry.get('integrity'),entry.get('resolved')))
        self.assertEqual(dict(Counter(r['license'] for r in rows.values())),inventory['license_counts'])
    def test_root_and_docs_manifests_both_bind_each_actual_lock_and_manifest_digest(self):
        root=json.loads((ROOT/'DEPENDENCIES.json').read_text());docs=json.loads((ROOT/'docs/DEPENDENCY-LOCK.json').read_text())
        self.assertEqual(root['graphs'],docs['graphs']);self.assertEqual(root['package_lock_sha256'],docs['lock_sha256'])
        for g in root['graphs']:
            self.assertEqual(g['lock_sha256'],hashlib.sha256((ROOT/g['lockfile']).read_bytes()).hexdigest());self.assertEqual(g['package_json_sha256'],hashlib.sha256((ROOT/g['manifest']).read_bytes()).hexdigest())
            self.assertEqual(g['direct_dependencies'],self.graphs[g['graph']][1]['dependencies']);self.assertEqual(g['locked_packages'],len(self.graphs[g['graph']][2]['packages'])-1)
        self.assertEqual(root['direct_dependencies'],self.graphs['core'][1]['dependencies'])
    def test_remotion_pins_stay_on_reviewed_version_and_core_has_no_remotion(self):
        pin=json.loads((ROOT/'renderers/versions.json').read_text())['remotion'];self.assertEqual(pin,'4.0.537');counts={}
        for graph,(_,_,lock) in self.graphs.items():
            count=0
            for name,entry in lock['packages'].items():
                n=name.rsplit('node_modules/',1)[-1]
                if n.startswith('@remotion/') or n=='remotion':count+=1;self.assertEqual(entry['version'],pin,name)
                if graph=='core':self.assertNotIn(n,{'react','react-dom'})
            counts[graph]=count
        self.assertEqual(counts,{'core':0,'remotion':29})
    def test_graph_separation_does_not_clear_release_native_or_commercial_gates(self):
        terms=owner_terms();self.assertTrue(terms['text_ready']);self.assertFalse(terms.get('customer_release_ready',False))
        plan=dependency_plan();self.assertTrue(plan['dependency_graph_ready']);self.assertEqual(plan['root_remotion_dependencies'],[]);self.assertEqual(plan['independent_ffprobe']['binary_redistributed'],False)
        self.assertEqual(json.loads((ROOT/'assets-lock.json').read_text())['status'],'pending_commercial_terms')
        self.assertIn('pending',(ROOT/'THIRD-PARTY-NOTICES.md').read_text().lower())
