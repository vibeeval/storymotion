"""Template numeric/price claim guard for all 91 IDs; caller-scoped claims only."""
import copy
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pack_fixture_case import PackFixtureCase
from storymotion import template_intake
from storymotion.claims import numeric_tokens
from storymotion.dashboard import Dashboard, Handler
from storymotion.engine import prepare_input
from storymotion.security import WorkflowError, digest
from storymotion.template_families import FAMILIES, capabilities, compile_scene, make_brief, svg_markup, validate_spec
from storymotion.template_intake import surface
from storymotion.writing_context import snapshot, sources
from tools.harness_fixtures import template_fixture_brief
from test_catalog_integration import MemoryConnection, issued_cookie

ROOT = Path(__file__).resolve().parents[1]
CASES = [(f['id'], e['name'], e['spec']) for f in capabilities()['families'] for e in f['examples']]
SOURCE = {'caller-source': {'url': 'https://example.org/caller-source', 'title': 'Caller registered source',
                            'locator': 'Section 1', 'excerpt': 'Caller supplied excerpt for traceability tests only.',
                            'rights_note': 'Synthetic caller declaration for tests; not a factual verification.'}}


def binding(account, rows=SOURCE):
    value = {'schema_version': 1, 'account': account, 'sources': snapshot('sources', account, sources(rows), None), 'canon': None}
    value['binding_sha256'] = digest(value)
    return value


DECLARATION = json.loads((ROOT/'catalog/template-claim-surface.json').read_text())


def declared_leaves(spec):
    """Independent of template_intake: declaration file plus raw parameter leaves."""
    row = DECLARATION['families'][spec['id']];hidden = set(DECLARATION['common']['hidden_strings']) | set(row['hidden_strings'])
    strings, numbers = [], []
    for path, value in leaves(spec['parameters']):
        pattern = re.sub(r'\.\[\]', '[]', '.'.join('[]' if isinstance(k, int) else k for k in path))
        if isinstance(value, str) and pattern not in hidden:strings.append((pattern, value))
        elif type(value) in (int, float) and pattern in row['guarded_numbers']:
            numbers.append((pattern, str(int(value)) if isinstance(value, float) and value.is_integer() else repr(value) if isinstance(value, float) else str(value)))
    return strings, numbers


def covering_claims(spec):
    strings, numbers = declared_leaves(validate_spec(spec))
    tokens = numeric_tokens(' '.join(text for _, text in strings + numbers))
    return [{'text': 'Caller values: ' + ' '.join(sorted(tokens)), 'source': 'caller-source',
             'scope': 'Only these caller supplied template values; traceability, not truth approval.'}]


def visible_string_paths(spec):
    return list(dict.fromkeys(path for path, _ in declared_leaves(validate_spec(spec))[0]))


def replace_first(spec, pattern, text):
    value = copy.deepcopy(spec);parts = re.findall(r'[a-z][a-z0-9_]*|\[\]', pattern);node = value['parameters']
    for i, part in enumerate(parts):
        key = 0 if part == '[]' else part
        if part == '[]' and (not isinstance(node, list) or not node):raise LookupError(pattern)
        if i == len(parts) - 1:node[key] = text
        else:node = node[key]
    return value


class TemplateClaimGuardTests(unittest.TestCase):
    def test_every_family_example_validates_only_with_scoped_caller_claims(self):
        self.assertEqual(len({family for family, _, _ in CASES}), 91);self.assertEqual(len(CASES), 182)
        needs_claims = set()
        for family, name, spec in CASES:
            with self.subTest(family=family, example=name):
                brief = template_fixture_brief('neutral', spec);prepared, _ = prepare_input(copy.deepcopy(brief))
                audit = prepared['template_audit'];self.assertEqual(audit['status'], 'incomplete')
                self.assertEqual(audit['numeric_price_guard'], 'pass');self.assertEqual(audit['source_truth'], 'pending_human_review')
                self.assertTrue(all(link['source_truth'] == 'pending_human_review' for link in audit['source_links']))
                strings, guarded = declared_leaves(validate_spec(spec))
                if numeric_tokens(' '.join(text for _, text in strings + guarded)):
                    needs_claims.add(family)
                    with self.assertRaisesRegex(WorkflowError, 'unsourced displayed number'):make_brief('neutral', spec)
                else:
                    self.assertEqual(make_brief('neutral', spec)['template_audit']['source_links'], [])
        # Numeric diagrams and the 120-point shape label are not exempt demo copy.
        self.assertTrue({'shape-morph', 'scale-morph-charts', 'bead-transfer-counts', 'isometric-process',
                         'spotlight-product-reveal', 'georeferenced-footage-track'} <= needs_claims)

    def test_price_and_number_in_every_visible_string_field_require_a_registered_claim(self):
        injected = {}
        for family in FAMILIES:
            spec = next(s for f, _, s in CASES if f == family)
            for path in visible_string_paths(spec):
                if path == 'narration' or path.startswith('cues'): continue
                try:
                    bad = replace_first(spec, path, 'Fiyat 99 TL')
                    validate_spec(bad)
                except (LookupError, WorkflowError):
                    continue
                injected.setdefault(family, []).append(path)
                with self.subTest(family=family, path=path):
                    with self.assertRaisesRegex(WorkflowError, 'unsourced displayed number'):
                        make_brief('neutral', bad, claims=covering_claims(spec), production_context=binding('neutral'))
                    accepted = make_brief('neutral', bad, claims=covering_claims(bad), production_context=binding('neutral'))
                    self.assertEqual(accepted['template_audit']['source_links'][0]['source_id'], 'caller-source')
        self.assertEqual(set(injected), set(FAMILIES))
        self.assertGreater(sum(len(v) for v in injected.values()), 91)

    def test_price_word_without_digits_still_requires_a_claim(self):
        spec = copy.deepcopy(next(s for f, _, s in CASES if f == 'contour-trace'));spec['parameters']['label'] = 'Bugün ücretsiz deneme mevcut.'
        with self.assertRaisesRegex(WorkflowError, 'Unsourced number or price'):make_brief('neutral', spec)
        self.assertTrue(make_brief('neutral', spec, claims=covering_claims(spec), production_context=binding('neutral')))

    def test_guarded_number_must_appear_in_claim_text_and_hidden_fields_do_not(self):
        checked = 0
        for family in sorted(FAMILIES):
            spec = next(s for f, _, s in CASES if f == family);strings, numeric = declared_leaves(validate_spec(spec))
            if not numeric: continue
            checked += 1
            with self.subTest(family=family):
                path, text = numeric[0];missing = numeric_tokens(text)
                tokens = numeric_tokens(' '.join(t for _, t in strings + numeric)) - missing
                claims = [{'text': 'Caller values: ' + ' '.join(sorted(tokens)), 'source': 'caller-source', 'scope': 'Partial coverage test.'}]
                with self.assertRaisesRegex(WorkflowError, 'unsourced displayed number'):
                    make_brief('neutral', spec, claims=claims, production_context=binding('neutral'))
        self.assertEqual(checked, sum(1 for row in DECLARATION['families'].values() if row['guarded_numbers']))
        media = copy.deepcopy(next(s for f, _, s in CASES if f == 'media-evidence-compare'))
        claims = covering_claims(media)
        media['parameters']['media'][0]['rights']['license'] = 'CC BY 4.0, ücretsiz değil, 99 TL'
        self.assertTrue(make_brief('neutral', media, claims=claims, production_context=binding('neutral')))

    def test_caption_brief_claim_and_audit_edits_are_rechecked_before_engine_input(self):
        spec = next(s for f, _, s in CASES if f == 'dimension-construction')
        brief = make_brief('neutral', spec, claims=covering_claims(spec), production_context=binding('neutral'))
        self.assertTrue(prepare_input(copy.deepcopy(brief)))
        edited = copy.deepcopy(brief);edited['caption'] = 'Yeni açıklama metni.';self.assertTrue(prepare_input(edited))
        for mutate in (lambda b: b.__setitem__('caption', b['caption'] + ' Şimdi 99 TL.'),
                       lambda b: b.__setitem__('caption', b['caption'] + ' Sadece 7 gün.'),
                       lambda b: b['template_audit'].__setitem__('status', 'accepted'),
                       lambda b: b.__setitem__('claims', []),
                       lambda b: b['claims'][0].__setitem__('text', 'Caller values without the displayed numbers'),
                       lambda b: b.__setitem__('production_context', None),
                       lambda b: b['template_family']['parameters']['dimension_values'].__setitem__('width', 260)):
            bad = copy.deepcopy(brief);mutate(bad)
            with self.subTest(mutation=mutate), self.assertRaises(WorkflowError):prepare_input(bad)

    def test_forged_stale_cross_account_unregistered_and_malformed_bindings_are_refused(self):
        spec = next(s for f, _, s in CASES if f == 'scale-morph-charts');claims = covering_claims(spec)
        forged = binding('neutral');forged['binding_sha256'] = '0' * 64
        content = binding('neutral');content['sources']['data']['caller-source']['excerpt'] = 'Changed after hashing.'
        foreign = binding('neutral');foreign['account'] = 'another-account'
        for value in (forged, content, foreign, None, {}, {'schema_version': 1}):
            with self.subTest(binding=value), self.assertRaises(WorkflowError):
                make_brief('neutral', spec, claims=claims, production_context=value)
        unregistered = [dict(claims[0], source='not-registered')]
        with self.assertRaisesRegex(WorkflowError, 'caller-owned registry'):
            make_brief('neutral', spec, claims=unregistered, production_context=binding('neutral'))
        for value in ('Caller values', {'text': 'x'}, [{'text': '1', 'source': 'caller-source'}],
                      [dict(claims[0], extra='x')], [dict(claims[0], text=' ')], [dict(claims[0], text='9' * 2001)],
                      [claims[0]] * 31, [dict(claims[0], source=7)]):
            with self.subTest(claims=str(value)[:40]), self.assertRaises(WorkflowError):
                make_brief('neutral', spec, claims=value, production_context=binding('neutral'))
        with self.assertRaises(WorkflowError):binding('neutral', {'caller-source': dict(SOURCE['caller-source'], url='http://example.org/x')})

    def test_claim_surface_declaration_is_pinned_complete_and_tamper_evident(self):
        self.assertEqual(set(surface()), set(FAMILIES));self.assertEqual(len(surface()), 91)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve();(root/'catalog').mkdir()
            raw = json.loads((ROOT/'catalog/template-claim-surface.json').read_text())
            raw['families']['scale-morph-charts']['guarded_numbers'] = []
            (root/'catalog/template-claim-surface.json').write_text(json.dumps(raw, ensure_ascii=False, indent=1) + '\n')
            with patch.object(template_intake, 'ROOT', root), self.assertRaisesRegex(WorkflowError, 'TEMPLATE_CLAIM_SURFACE_INVALID'):surface()
            (root/'catalog/template-claim-surface.json').unlink();(root/'catalog/template-claim-surface.json').symlink_to(ROOT/'catalog/template-claim-surface.json')
            with patch.object(template_intake, 'ROOT', root), self.assertRaises(WorkflowError):surface()


class CertaintyGuardTemplateTests(PackFixtureCase):
    def test_certainty_guard_pack_checks_template_parameter_copy(self):
        spec = copy.deepcopy(next(s for f, _, s in CASES if f == 'contour-trace'))
        self.assertTrue(make_brief('sample-reflection', spec))
        spec['parameters']['label'] = 'Bu çizim yorgunluğun kesin nedeni gösterir.'
        with self.assertRaisesRegex(WorkflowError, 'certainty'):make_brief('sample-reflection', spec)


class ClaimSurfaceRenderTests(unittest.TestCase):
    def test_development_declaration_matches_rendered_text_for_all_168_fixtures(self):
        declaration = json.loads((ROOT/'catalog/template-claim-surface.json').read_text())
        cases = [{'family': json.loads(p.read_text())['family_id'], 'spec': c['spec']}
                 for p in sorted((ROOT/'fixtures/development-templates').glob('*.json')) for c in json.loads(p.read_text())['cases']]
        result = subprocess.run(['node', str(ROOT/'tests/template_claim_surface_probe.mjs')], cwd=ROOT, capture_output=True, text=True, timeout=900,
                                input=json.dumps({'declaration': declaration, 'cases': cases, 'frames': 24}), env={'PATH': os.environ.get('PATH', ''), 'DO_NOT_TRACK': '1'})
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        value = json.loads(result.stdout)
        self.assertEqual(value['families'], 84);self.assertEqual(value['violations'], [])
        self.assertGreater(value['coverage']['numeric_checked'], 1500);self.assertGreater(value['coverage']['hidden_checked'], 1500)

    def test_baseline_declaration_matches_rendered_text(self):
        examples = json.loads((ROOT/'fixtures/template-families.json').read_text())['families']
        def rendered(spec):
            scene = compile_scene(make_brief_unchecked(spec));texts = set()
            for i in range(25):
                svg = ET.fromstring(svg_markup(scene, scene['duration'] * i / 24))
                texts.update(''.join(node.itertext()) for node in svg.iter('{http://www.w3.org/2000/svg}text'))
            return texts
        for family in list(FAMILIES)[:7]:
            row = surface()[family]
            for case in examples[family]:
                spec = validate_spec(case['spec']);base = rendered(spec);digits = {t for s in base for t in numeric_tokens(s)}
                for path, value in leaves(spec['parameters']):
                    pattern = re.sub(r'\.\[\]', '[]', '.'.join('[]' if isinstance(k, int) else k for k in path))
                    with self.subTest(family=family, path=pattern):
                        if isinstance(value, str) and pattern in row['hidden']:
                            word = re.compile(r'(?<!\w)' + re.escape(value) + r'(?!\w)', re.I)
                            self.assertFalse(any(word.search(text) for text in base))
                        elif type(value) in (int, float) and pattern not in row['guarded'] and pattern not in ('duration', 'cues[].start', 'cues[].end'):
                            for candidate in (value + 1, value - 1, value * 1.5):
                                changed = copy.deepcopy(spec);set_at(changed['parameters'], path, candidate)
                                try:changed = validate_spec(changed)
                                except WorkflowError:continue
                                self.assertEqual({t for s in rendered(changed) for t in numeric_tokens(s)}, digits)


def make_brief_unchecked(spec):
    return {'template_family': spec}


def leaves(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():yield from leaves(child, path + (key,))
    elif isinstance(value, list):
        for i, child in enumerate(value):yield from leaves(child, path + (i,))
    else:yield path, value


def set_at(value, path, item):
    for key in path[:-1]:value = value[key]
    value[path[-1]] = item


class TemplateClaimHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.d = Dashboard(Path(self.tmp.name).resolve());self.addCleanup(self.d.clear_keys);self.addCleanup(self.d.renders.close);self.addCleanup(self.d.close_local_log)
        self.server = SimpleNamespace(server_address=('127.0.0.1', 43333), dashboard=self.d);self.cookie = issued_cookie(self.server)
        self.spec = next(s for f, _, s in CASES if f == 'dimension-construction')

    def call(self, path, body=None):
        method = 'POST' if body is not None else 'GET';data = json.dumps(body).encode() if body is not None else b''
        lines = [method + ' ' + path + ' HTTP/1.0', 'Host: 127.0.0.1:43333', 'Cookie: ' + self.cookie]
        if body is not None:lines += ['Origin: http://127.0.0.1:43333', 'X-Storymotion-Local: 1', 'Content-Type: application/json', 'Content-Length: ' + str(len(data))]
        connection = MemoryConnection(('\r\n'.join(lines) + '\r\n\r\n').encode() + data);Handler(connection, ('127.0.0.1', 1), self.server)
        head, raw = bytes(connection.output).split(b'\r\n\r\n', 1);return int(head.split()[1]), json.loads(raw)

    def save_sources(self, rows, expected):
        code, value = self.call('/api/writing-context/save-sources', {'account': 'neutral', 'expected_revision': expected, 'sources': rows, 'rights_confirmed': True})
        self.assertEqual(code, 200, value);return value['sources']['revision']

    def prepare(self, **extra):
        return self.call('/api/template-families/prepare', {'account': 'neutral', 'engine': 'hyperframes', 'spec': self.spec, **extra})

    def test_scoped_claims_bind_current_caller_sources_and_reject_missing_stale_or_unregistered(self):
        with patch('storymotion.engine.checked_process', side_effect=AssertionError('No native process')):
            code, value = self.prepare();self.assertEqual(code, 400);self.assertIn('unsourced displayed number', value['error'])
            claims = covering_claims(self.spec)
            code, value = self.prepare(claims=claims);self.assertEqual(code, 400);self.assertIn('caller-owned registry', value['error'])
            revision = self.save_sources(SOURCE, None)
            for stale in ('0' * 64, 'abc', None):
                code, value = self.prepare(claims=claims, source_revision=stale);self.assertEqual(code, 400, stale)
            code, value = self.prepare(claims=[dict(claims[0], source='not-registered')], source_revision=revision);self.assertEqual(code, 400)
            code, value = self.prepare(claims=claims, source_revision=revision);self.assertEqual(code, 200, value)
            out = self.d.workspace/'family-renders'/value['job'];context = json.loads((out/'writing-context.json').read_text())
            self.assertEqual(context['binding']['sources']['revision'], revision);self.assertEqual(context['source_truth'], 'pending_human_review')
            self.assertEqual(context['claim_traceability']['source_links'][0]['source_id'], 'caller-source')
            self.assertIn('writing-context.json', value['manifest']);self.assertIn('source-brief.json', value['manifest'])
            newer = self.save_sources({'caller-source': dict(SOURCE['caller-source'], locator='Section 2')}, revision)
            code, value = self.prepare(claims=claims, source_revision=revision);self.assertEqual(code, 400)
            self.assertEqual(self.prepare(claims=claims, source_revision=newer)[0], 200)

    def test_context_change_between_binding_and_prepare_lock_creates_no_job(self):
        revision = self.save_sources(SOURCE, None);claims = covering_claims(self.spec)
        with patch.object(self.d.llm.contexts, 'assert_current', side_effect=WorkflowError('Writing context changed; new preview required')), \
             patch('storymotion.template_studio.Engine', side_effect=AssertionError('No engine job after a stale binding')):
            code, value = self.prepare(claims=claims, source_revision=revision)
        self.assertEqual(code, 400);self.assertIn('Writing context changed', value['error'])
        self.assertFalse((self.d.workspace/'family-renders').exists() and any((self.d.workspace/'family-renders').iterdir()))


if __name__ == '__main__':
    unittest.main()
