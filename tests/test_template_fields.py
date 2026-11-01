"""Actual authenticated, side-effect-free editor routes and declared coverage."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import sqlite3
import shutil
import unittest
from unittest.mock import patch

from storymotion import template_fields as fields
from storymotion.template_families import capabilities, validate_spec
from storymotion.security import WorkflowError, canonical
import test_taxonomy
from test_template_intake import SOURCE, covering_claims
from test_template_credential_intake import LLM_OPAQUE, VOICE_OPAQUE, patterned

ROOT = Path(__file__).resolve().parents[1]


class FieldContractTests(unittest.TestCase):
    def test_actual_baseline_file_mutation_still_refuses_the_current_generated_binding(self):
        metadata=json.loads((ROOT/'catalog/template-field-contracts.json').read_text())
        manifest=fields.development_templates.manifest()
        names=set(metadata['baseline_sources'])|set(manifest['files'])|{'catalog/template-field-contracts.json','renderers/template-registry/source-manifest.json'}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            for name in names:
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
            with patch.object(fields.development_templates,'ROOT',root):
                self.assertEqual(fields.declarations()['baseline_sources'],metadata['baseline_sources'])
                source=root/'storymotion/template_families.py';original=source.read_bytes();source.write_bytes(original+b'\n# synthetic changed generator\n')
                before={name:(root/name).read_bytes() for name in names}
                with self.assertRaisesRegex(WorkflowError,'baseline declaration source changed'):fields.declarations()
                self.assertEqual(before,{name:(root/name).read_bytes() for name in names})
                source.write_bytes(original)
                self.assertEqual(fields.declarations()['declarations'],metadata['declarations'])

    def test_exact_91_identity_182_example_coverage_and_authoritative_roundtrip(self):
        rows = capabilities()['families']
        self.assertEqual(len(rows), 91)
        count = 0
        for family in rows:
            for example in family['examples']:
                value = fields.contract('neutral', family['id'], family['version'], example['name'])
                self.assertEqual(value['example_sha256'], fields.digest(example['spec']))
                self.assertFalse(value['coverage']['fully_typed'])
                self.assertFalse(value['coverage']['exhaustive_contract_coverage'])
                normalized = validate_spec(example['spec'])
                self.assertEqual(normalized, validate_spec(normalized))
                count += 1
        self.assertEqual(count, 182)

    def test_public_schema_snapshot_exactly_matches_fixed_registry_exports(self):
        script = "import {ENTRIES} from './renderers/template-registry/registry.mjs'; process.stdout.write(JSON.stringify(Object.fromEntries(ENTRIES.map(e=>[e.family_id,e.module.PARAMETER_SCHEMA]))));"
        result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT,
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = json.loads(result.stdout)
        declared = fields.declarations()['declarations']
        self.assertEqual({k: declared[k] for k in actual}, actual)
        self.assertEqual(len(actual), 84)

    def test_missing_metadata_and_ambiguous_array_shapes_are_explicit_fallbacks(self):
        value = fields.contract('neutral', 'glass-section-orbit', '1.0.0', fields.examples('glass-section-orbit')[0]['name'])
        paths = value['coverage']['observed_paths']
        self.assertEqual(paths['title'], 'JSON_fallback')
        self.assertEqual(paths['ior'], 'declared_supported')
        self.assertEqual(paths['light_angles/*'], 'JSON_fallback')
        self.assertNotIn('minItems', value['parameters']['properties']['light_angles'])

    def test_unsupported_dynamic_constraints_never_get_invented_limits(self):
        value = fields.descriptor({'minimum': 1, 'maximum': 'source amount'})
        self.assertEqual(value['minimum'], 1)
        self.assertNotIn('maximum', value)
        self.assertIn('dynamic bounds', ' '.join(value['notes']))
        for declaration in ({'normalized': True, 'minimumSpan': .3}, {'permutation': 'all indices'}):
            self.assertEqual(fields.descriptor(declaration)['type'], 'unknown')
        self.assertEqual(fields.descriptor({'type': 'array'})['items']['type'], 'unknown')

    def test_declared_bounds_enums_permutation_and_optional_defaults(self):
        chart = fields.contract('neutral', 'scale-morph-charts', '1.0.0', 'A')['parameters']['properties']
        self.assertEqual(chart['domain_bounds']['minItems'], 2)
        self.assertEqual(chart['domain_bounds']['maxItems'], 2)
        self.assertEqual(chart['chart_sequence']['first'], 'dots')
        self.assertTrue(chart['chart_sequence']['unique'])
        base = fields.contract('neutral', 'bauhaus-modules', '1.0.0', 'short-silent')['parameters']
        self.assertNotIn('turns', base['required'])
        self.assertEqual(base['properties']['turns']['default'], 1)

    def test_raw_json_rejects_duplicate_unsafe_deep_and_unrepresentable_data(self):
        for raw in ('{"a":1,"a":2}', '{"nested":{"constructor":0}}', '{"__proto__":{}}',
                    '{"prototype":0}', '[NaN]', '[Infinity]', '[1e999]', '[1e-999]',
                    '[9007199254740992]', '[9.007199254740992e15]', '[' * 26 + '0' + ']' * 26,
                    'x' * 100001, ''):
            with self.subTest(raw=raw[:60]), self.assertRaises(WorkflowError):
                fields.parse_raw(raw)
        for value in (160.12345678901234, 1.5234567890123398):
            self.assertEqual(fields.parse_raw(json.dumps(value)), value)

    def test_integral_decimal_and_exponent_lexemes_match_browser_Number(self):
        for token in ('1.0', '1e0', '1.0000000000000000001'):
            self.assertIs(type(fields.parse_raw(token)), int)
            spec = copy.deepcopy(fields.examples('bauhaus-modules')[0]['spec'])
            spec['parameters']['turns'] = 1
            raw = json.dumps(spec).replace('"turns": 1', '"turns": ' + token)
            self.assertEqual(validate_spec(fields.parse_raw(raw)), validate_spec(spec))

    def test_contract_rejects_unknown_versions_examples_hashes_and_source_tamper(self):
        for args in [('neutral', 'unknown', '1.0.0', 'A'), ('neutral', 'kinetic-grid', '2', 'A'),
                     ('neutral', 'kinetic-grid', '1.0.0', 'unknown')]:
            with self.assertRaises(WorkflowError): fields.contract(*args)
        with patch.object(fields, 'CONTRACT_SHA256', '0' * 64):
            with self.assertRaises(WorkflowError): fields.declarations()
        with patch.object(fields, 'file_hash', return_value='0' * 64):
            with self.assertRaisesRegex(WorkflowError, 'source changed'): fields.declarations()
        with self.assertRaises(WorkflowError): fields.descriptor({'type': 'object', 'properties': {'constructor': {}}})
        with self.assertRaises(WorkflowError): fields.descriptor({'type': 'object', 'properties': {}, 'required': ['missing']})

    def test_baseline_fixture_links_and_changed_bytes_are_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve();(root/'fixtures').mkdir()
            target = root/'fixtures/template-families.json'
            target.symlink_to(ROOT/'fixtures/template-families.json')
            with patch.object(fields.development_templates, 'ROOT', root):
                with self.assertRaises(WorkflowError): fields.examples('kinetic-grid')
                target.unlink();target.write_text('{}')
                with self.assertRaises(WorkflowError): fields.examples('kinetic-grid')
                target.write_bytes((ROOT/'fixtures/template-families.json').read_bytes())
                self.assertEqual(len(fields.examples('kinetic-grid')), 2)


class FieldHttpTests(unittest.TestCase):
    setUp = test_taxonomy.TaxonomyHttpTests.setUp
    request = test_taxonomy.TaxonomyHttpTests.request

    def endpoint(self, operation, data, **kwargs):
        return self.request('', data, path='/api/template-families/' + operation, **kwargs)

    def snapshot(self):
        return {str(p.relative_to(self.d.workspace)): (p.read_bytes(), p.stat().st_mtime_ns) if p.is_file() else None
                for p in self.d.workspace.rglob('*')}

    def payload(self, family='kinetic-grid', example=None):
        if example is None: example = fields.examples(family)[0]['name']
        request = {'account': 'neutral', 'family': family, 'version': '1.0.0', 'example': example}
        code, contract, _ = self.endpoint('fields', request)
        self.assertEqual(code, 200, contract)
        spec = next(v['spec'] for v in fields.examples(family) if v['name'] == example)
        return {**request, 'engine': 'hyperframes', 'raw_spec': json.dumps(spec), 'contract_digest': contract['digest']}

    def sources(self):
        code, value, _ = self.request('', {'account': 'neutral', 'expected_revision': None,
                                        'sources': SOURCE, 'rights_confirmed': True},
                                       path='/api/writing-context/save-sources')
        self.assertEqual(code, 200, value)
        return value['sources']['revision']

    def test_fields_and_validate_require_session_host_origin_and_marker(self):
        for operation in ('fields', 'validate'):
            data = self.payload()
            for args, status in [({'cookie': False}, 401), ({'host': 'evil.local'}, 403),
                                 ({'origin': 'http://evil.local'}, 403), ({'marker': '0'}, 403)]:
                with self.subTest(operation=operation, args=args):
                    self.assertEqual(self.endpoint(operation, data, **args)[0], status)

    def test_all_182_examples_validate_without_files_jobs_events_or_provider(self):
        revision = self.sources()
        before = self.snapshot()
        with patch('storymotion.template_studio.Engine', side_effect=AssertionError('No Engine')):
            for row in capabilities()['families']:
                for example in row['examples']:
                    with self.subTest(family=row['id'], example=example['name']):
                        data = self.payload(row['id'], example['name'])
                        data.update(claims=covering_claims(example['spec']), source_revision=revision)
                        code, result, _ = self.endpoint('validate', data)
                        self.assertEqual(code, 200, result)
                        self.assertEqual(result['normalized_spec'], validate_spec(example['spec']))
                        self.assertEqual(result['raw_sha256'], hashlib.sha256(data['raw_spec'].encode()).hexdigest())
                        self.assertFalse(result['authorization'])
                        self.assertFalse(result['actual_render'])
                        self.assertEqual(result['provider_calls'], 0)
        self.assertEqual(self.snapshot(), before)

    def test_malformed_raw_and_stale_contract_never_write(self):
        data = self.payload()
        before = self.snapshot()
        bad = [dict(data, contract_digest='0' * 64), dict(data, account='studio-b'),
               dict(data, version='2'), dict(data, engine='unknown')]
        for raw in ('null', '[]', '{', '{"id":"kinetic-grid","id":"contour-trace"}',
                    '{"id":"kinetic-grid","version":"1.0.0","parameters":{"constructor":1}}'):
            bad.append(dict(data, raw_spec=raw))
        for value in bad:
            self.assertEqual(self.endpoint('validate', value)[0], 400)
        self.assertEqual(self.snapshot(), before)

    def test_raw_parsed_and_normalized_credentials_cannot_echo_or_persist(self):
        self.d.llm.broker.put('openai', 'job', 'request', LLM_OPAQUE, synthetic=True)
        self.d.eleven.broker.put('elevenlabs', 'job', 'request', VOICE_OPAQUE, synthetic=True)
        data = self.payload()
        before = self.snapshot()
        for key in (LLM_OPAQUE, VOICE_OPAQUE, patterned()):
            spec = fields.parse_raw(data['raw_spec']);spec['parameters']['title'] = key
            for raw in (json.dumps(spec), json.dumps(spec).replace('F', '\\u0046')):
                code, result, response = self.endpoint('validate', dict(data, raw_spec=raw))
                self.assertEqual(code, 400, result)
                self.assertNotIn(key.encode(), response)
                self.assertNotIn(canonical(key).encode(), response)
        original = fields.template_families.make_brief
        def forged(*args, **kwargs):
            value = original(*args, **kwargs);value['caption'] = LLM_OPAQUE;return value
        with patch.object(fields.template_families, 'make_brief', side_effect=forged):
            self.assertEqual(self.endpoint('validate', data)[0], 400)
        self.assertEqual(self.snapshot(), before)

    def test_precise_numbers_chart_domain_and_normalization_are_not_rounded(self):
        revision = self.sources()
        for family, path, value in [('dimension-construction', ['dimension_values', 'width'], 160.12345678901234),
                                    ('glass-section-orbit', ['ior'], 1.5234567890123398),
                                    ('scale-morph-charts', ['domain_bounds'], [0, 110])]:
            data = self.payload(family);spec = fields.parse_raw(data['raw_spec']);target = spec['parameters']
            for key in path[:-1]:target = target[key]
            target[path[-1]] = value
            data.update(raw_spec=json.dumps(spec), claims=covering_claims(spec), source_revision=revision)
            code, result, _ = self.endpoint('validate', data)
            self.assertEqual(code, 200, result)
            target = result['normalized_spec']['parameters']
            for key in path: target = target[key]
            self.assertEqual(target, value)

    def test_coupled_bounds_enums_collections_and_current_context_reject(self):
        data = self.payload()
        spec = fields.parse_raw(data['raw_spec'])
        edits = []
        for value in (None, True, '', '3', 2.999, 45.001):
            p = copy.deepcopy(spec);p['parameters']['duration'] = value;edits.append(p)
        for value in ([], spec['parameters']['phrases'] * 3):
            p = copy.deepcopy(spec);p['parameters']['phrases'] = value;edits.append(p)
        p = copy.deepcopy(spec);p['parameters']['cues'][0]['end'] = 50;edits.append(p)
        p = copy.deepcopy(spec);p['parameters']['cues'][0]['text'] = 'Different narration';edits.append(p)
        before = self.snapshot()
        for p in edits:
            self.assertEqual(self.endpoint('validate', dict(data, raw_spec=json.dumps(p)))[0], 400)
        self.assertEqual(self.snapshot(), before)
        revision = self.sources()
        data.update(source_revision='0' * 64, claims=covering_claims(spec))
        self.assertEqual(self.endpoint('validate', data)[0], 400)
        data.update(source_revision=revision, planning={'revision':'0' * 64, 'niche':'bad', 'topic':'bad'})
        self.assertEqual(self.endpoint('validate', data)[0], 400)

    def test_validation_never_relaxes_independent_prepare_revalidation(self):
        data = self.payload()
        code, result, _ = self.endpoint('validate', data)
        self.assertEqual(code, 200, result)
        spec = result['normalized_spec'];spec['parameters']['duration'] = None
        before = self.snapshot()
        code, _, _ = self.request('', {'account':'neutral','engine':'hyperframes','spec':spec}, path='/api/template-families/prepare')
        self.assertEqual(code, 400)
        self.assertEqual(self.snapshot(), before)

    def test_local_read_errors_do_not_write_diagnostics_or_echo_inputs(self):
        data = self.payload()
        before = self.snapshot()
        for error in (OSError('TEST_ONLY_READ_DETAIL'), sqlite3.DatabaseError('TEST_ONLY_READ_DETAIL')):
            with patch.object(fields, 'contract', side_effect=error):
                code, result, response = self.endpoint('validate', data)
                self.assertEqual(code, 400)
                self.assertNotIn(b'TEST_ONLY_READ_DETAIL', response)
        self.assertEqual(self.snapshot(), before)

    def test_missing_claims_wrong_parent_and_late_source_conflict_never_write(self):
        revision = self.sources()
        data = self.payload('dimension-construction')
        spec = fields.parse_raw(data['raw_spec'])
        data.update(claims=covering_claims(spec), source_revision=revision)
        state = self.d.taxonomy.action('state', {'account':'neutral'})
        topic = state['topics'][0]
        selected = self.d.taxonomy.action('select', {'account':'neutral','niche':topic['niche'],
            'topic':topic['id'],'expected_revision':state['revision']})
        data['planning'] = {'revision':selected['revision'],'niche':topic['niche'],'topic':topic['id']}
        before = self.snapshot()
        self.assertEqual(self.endpoint('validate', data)[0], 200)
        self.assertEqual(self.endpoint('validate', dict(data, claims=[]))[0], 400)
        self.assertEqual(self.endpoint('validate', dict(data, claims={}))[0], 400)
        bad = copy.deepcopy(data);bad['planning']['niche'] = 'unknown'
        self.assertEqual(self.endpoint('validate', bad)[0], 400)
        with patch.object(self.d.llm.contexts, 'assert_current', side_effect=WorkflowError('TEST_ONLY_CHANGED')):
            self.assertEqual(self.endpoint('validate', data)[0], 400)
        self.assertEqual(self.snapshot(), before)

    def test_graph_permutation_enum_and_collection_contracts_stay_authoritative(self):
        for family, edit in [
                ('causal-path', lambda p:p['edges'][0].update({'from':p['nodes'][-1]['id'],'to':p['nodes'][0]['id']})),
                ('dimension-construction', lambda p:p.update(construction_order=['outline','outline','dimension'])),
                ('scale-morph-charts', lambda p:p.update(chart_sequence=['invalid','line'])),
                ('shape-morph', lambda p:p.update(shapes=p['shapes'] * 3))]:
            data = self.payload(family);spec = fields.parse_raw(data['raw_spec']);edit(spec['parameters'])
            before = self.snapshot()
            self.assertEqual(self.endpoint('validate', dict(data, raw_spec=json.dumps(spec)))[0], 400)
            self.assertEqual(self.snapshot(), before)
