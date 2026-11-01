"""Exact numeric readouts: validation, source/bundle rendering and HTTP side effects."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from storymotion.dashboard import Dashboard, Handler
from storymotion import development_templates
from storymotion.security import WorkflowError
from test_catalog_integration import MemoryConnection, issued_cookie

ROOT = Path(__file__).resolve().parents[1]
ENV = {'PATH': os.environ.get('PATH', ''), 'DO_NOT_TRACK': '1'}


def case(family, path, value, *, valid=True, ticks=None):
    spec = json.loads((ROOT / ('fixtures/development-templates/' + family + '.json')).read_text())['cases'][0]['spec']
    target = spec['parameters']
    for key in path[:-1]:target = target[key]
    target[path[-1]] = value
    return {'name': family + '/' + '.'.join(path) + '/' + str(value), 'spec': spec, 'valid': valid, 'ticks': ticks}


def positives():
    rows = []
    for key, values in {'width': [160, 360, 160.12345678901234], 'height': [140, 280, 140.12345678901235],
                        'depth': [80, 150, 80.12345678901235]}.items():
        rows += [case('dimension-construction', ['dimension_values', key], v) for v in values]
    for key, values in {'wall_thickness': [8, 28, 8.123456789012345], 'height': [320, 520, 320.1234567890123],
                        'outer_radius': [100, 190, 100.12345678901235], 'ior': [1.1, 1.6, 1.5234567890123398]}.items():
        rows += [case('glass-section-orbit', [key], v) for v in values]
    for bounds, ticks in [([0, 110], ['0','27.5','55','82.5','110']),
                           ([0, 119], ['0','29.75','59.5','89.25','119']),
                           ([.2,110.1], ['0.2','27.675','55.15','82.625','110.1']),
                           ([.1,110.1], ['0.1','27.6','55.1','82.6','110.1']),
                           ([1,111], ['1','28.5','56','83.5','111']),
                           ([10,120], ['10','37.5','65','92.5','120'])]:
        rows.append(case('scale-morph-charts', ['domain_bounds'], bounds, ticks=ticks))
    return rows


class NumericContractTests(unittest.TestCase):
    def probe(self, rows, bundle=False):
        result = subprocess.run(['node', str(ROOT / 'tests/numeric_contract_probe.mjs')],
            input=json.dumps({'cases': rows, 'bundle': bundle}), cwd=ROOT, text=True,
            capture_output=True, timeout=60, env=ENV)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        values = json.loads(result.stdout);self.assertEqual(len(values), len(rows))
        return values

    def test_exact_minimal_reproductions_render_all_seeks(self):
        rows = [case('dimension-construction', ['dimension_values','width'], 160.12345678901234),
                positives()[-6], case('glass-section-orbit', ['ior'], 1.5234567890123398)]
        for result in self.probe(rows):
            with self.subTest(case=result['name']):self.assertTrue(result.get('ok'), result)

    def test_three_exact_inputs_prepare_and_execute_generated_gsap_program(self):
        from test_template_clock import GeneratedTemplateClockTests
        probe = GeneratedTemplateClockTests()
        for row in [positives()[2], positives()[-6], positives()[20]]:
            duration = row['spec']['parameters']['duration']
            with self.subTest(case=row['name']):probe.probe(row['spec'], [0,duration/2,duration,duration/2,0,duration])

    def test_bounded_numeric_variants_preserve_full_values_in_source_and_bundle(self):
        for bundle in (False, True):
            for result in self.probe(positives(), bundle):
                self.assertTrue(result.get('ok'), result);self.assertEqual(result['frames'], 7)

    def test_invalid_types_bounds_and_unrepresentable_domains_reject_during_validation(self):
        rows = []
        fields = [('dimension-construction',['dimension_values',k],lo,hi) for k,lo,hi in [('width',160,360),('height',140,280),('depth',80,150)]]
        fields += [('glass-section-orbit',[k],lo,hi) for k,lo,hi in [('wall_thickness',8,28),('height',320,520),('outer_radius',100,190),('ior',1.1,1.6)]]
        for family, path, low, high in fields:
            for value in (True, None, '170', {}, [], low - 1, high + 1):rows.append(case(family, path, value, valid=False))
            for native in ('nan', 'infinity', 'negativeInfinity'):
                row = case(family, path, low, valid=False);row.update(nativeValue=native, path=path);rows.append(row)
        for bounds in ([0,121],[-1,100],[90,80],[0,1],[1e-16,110],[.1234567890123456,110.12345678901234]):
            rows.append(case('scale-morph-charts',['domain_bounds'],bounds,valid=False))
        for bundle in (False, True):
            for result in self.probe(rows, bundle):
                self.assertIn('TEMPLATE_INPUT:',result.get('error',''),result)

    def test_precision_rejection_is_actionable_before_http_prepare_persistence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve();d = Dashboard(root)
            self.addCleanup(d.clear_keys);self.addCleanup(d.renders.close);self.addCleanup(d.reviews.close);self.addCleanup(d.close_local_log)
            server = SimpleNamespace(server_address=('127.0.0.1',43333),dashboard=d);cookie = issued_cookie(server)
            before = {str(p.relative_to(root)):(p.read_bytes(),p.stat().st_mtime_ns) if p.is_file() else None for p in root.rglob('*')}
            data = {'account':'neutral','engine':'hyperframes','spec':case('scale-morph-charts',['domain_bounds'],[1e-16,110])['spec']}
            body = json.dumps(data).encode();head = ['POST /api/template-families/prepare HTTP/1.0','Host: 127.0.0.1:43333','Origin: http://127.0.0.1:43333','X-Storymotion-Local: 1','Cookie: '+cookie,'Content-Type: application/json','Content-Length: '+str(len(body))]
            connection = MemoryConnection(('\r\n'.join(head)+'\r\n\r\n').encode()+body)
            with patch('storymotion.template_studio.Engine',side_effect=AssertionError('No Engine for unrepresentable numeric labels')):
                Handler(connection,('127.0.0.1',1),server)
            response, raw = bytes(connection.output).split(b'\r\n\r\n',1)
            self.assertEqual(int(response.split()[1]),400)
            self.assertIn('domain_bounds',json.loads(raw)['error'])
            after = {str(p.relative_to(root)):(p.read_bytes(),p.stat().st_mtime_ns) if p.is_file() else None for p in root.rglob('*')}
            self.assertTrue(before==after,'Numeric rejection mutated persisted state')

    def test_bridge_only_exposes_the_fixed_numeric_code_and_never_unknown_error_text(self):
        for stderr in ('TEMPLATE_NUMERIC_DOMAIN_LABELS_INVALID\nFAKE_NUMERIC_INPUT',
                       'TEMPLATE_NUMERIC_DOMAIN_LABELS_INVALID', 'FAKE_NUMERIC_INPUT'):
            with self.subTest(stderr_kind=stderr.split('\n')[0]), \
                 patch.object(development_templates.subprocess,'run',return_value=SimpleNamespace(returncode=2,stdout='',stderr=stderr)):
                with self.assertRaisesRegex(WorkflowError,'^TEMPLATE_REGISTRY_INPUT_INVALID$'):
                    development_templates.bridge({'op':'validate','spec':positives()[0]['spec']})
