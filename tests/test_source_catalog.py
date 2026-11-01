"""Pinned clean metadata and real protected Handler fixtures; no native calls."""
import copy
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from storymotion import source_catalog as catalog, development_templates
from storymotion.security import WorkflowError, digest
from storymotion.template_families import capabilities, validate_spec
import test_family_history_http as fixture

ROOT = Path(__file__).resolve().parents[1]


class MetadataTests(unittest.TestCase):
    def test_clean_reference_identity_dedup_urls_and_exact_notice(self):
        rows = catalog.metadata('references')
        self.assertEqual(len(rows), 3)
        self.assertEqual(len({r['id'] for r in rows}), len(rows))
        self.assertEqual(len({url for r in rows for url in r['reference_urls']}), 4)
        for row in rows:
            self.assertIs(row['reference_only'], True)
            self.assertEqual(row['asset_rights'], 'not_assessed')
            self.assertIsNone(row['planning_mapping']);self.assertIsNone(row['preview_url'])
            self.assertEqual(catalog.file_hash(ROOT / row['notice_path']), row['notice_sha256'])
            self.assertTrue(all('/blob/' + row['commit'] + '/' in url for url in row['reference_urls']))
        packed = json.dumps(rows).lower()
        for private in ('libfile_', 'skill://', '/users/', 'private-brand-fixture', 'private-account-fixture', 'prompt'):
            self.assertNotIn(private, packed)

    def test_four_actual_palettes_validate_every_compatible_example_and_reject_exclusions_without_render(self):
        rows = catalog.metadata('styles');self.assertEqual(len(rows), 4)
        for row in rows:
            specs = [copy.deepcopy(e['spec']) for ident in row['family_ids'] for e in development_templates.examples(ident)]
            self.assertEqual(len(specs), 2 * len(row['family_ids']))
            for spec in specs:spec['parameters']['palette'] = copy.deepcopy(row['palette'])
            # Public bridge only. No module-body inspection, frame generation or native execution.
            result = []
            for start in range(0, len(specs), 20):
                result.extend(development_templates.bridge({'op': 'batch', 'specs': specs[start:start+20], 'phases': []}))
            self.assertEqual(len(result), len(specs))
            for item in result:
                self.assertEqual(item['spec']['parameters']['palette'], row['palette'])
                self.assertEqual(item['frames'], [])
            for ident in row['excluded_family_ids']:
                for example in development_templates.examples(ident):
                    spec = copy.deepcopy(example['spec']);spec['parameters']['palette'] = row['palette']
                    with self.assertRaises(WorkflowError):validate_spec(spec)
        executable = capabilities()['families']
        self.assertEqual(len(executable), 91)
        self.assertEqual(sum(len(r['examples']) for r in executable), 182)
        for family in executable:
            if family['id'] not in development_templates.FAMILIES:
                self.assertEqual(len(set(f['id'] for f in executable) - set(development_templates.FAMILIES)), 7)
                spec = copy.deepcopy(family['examples'][0]['spec']);spec['parameters']['palette'] = rows[0]['palette']
                with self.assertRaises(WorkflowError):validate_spec(spec)

    def test_strict_json_duplicates_unsafe_keys_schema_and_duplicates(self):
        for raw in ('{"x":1,"x":2}', '{"constructor":1}', '{"__proto__":{}}'):
            with self.assertRaises(WorkflowError):json.loads(raw, object_pairs_hook=catalog.pairs)
        base = catalog.pinned('catalog/source-catalog.json')
        mutations = []
        for version in (True, 1.0, '1', None):
            bad = copy.deepcopy(base);bad['schema_version'] = version;mutations.append(bad)
        bad = copy.deepcopy(base);bad['references'].append(bad['references'][0]);mutations.append(bad)
        for bad in mutations:
            with self.assertRaises(WorkflowError):catalog.rows(bad, 'references')

    def test_rebound_metadata_still_cannot_invent_urls_rights_preview_or_compatibility(self):
        original = catalog.pinned
        for kind, path, edits in (
                ('references', 'catalog/source-catalog.json', [dict(reference_only=1), dict(asset_rights='cleared'),
                    dict(reference_urls=['javascript:alert(1)']), dict(reference_urls=['https://github.com/other/repo/blob/'+'a'*40+'/x']),
                    dict(preview_url='https://example.test/video.mp4'), dict(planning_mapping={'account':'other'}), dict(extra=True)]),
                ('styles', 'catalog/style-gallery.json', [dict(compatibility='all'), dict(palette={'background':'url(x)'}),
                    dict(origin_family='contour-trace'), dict(planning_mapping={}), dict(extra=True)])):
            for edit in edits:
                bad = original(path);bad[kind][0].update(edit)
                with self.subTest(kind=kind, edit=edit), patch.object(catalog, 'pinned', side_effect=lambda name: bad if name == path else original(name)):
                    with self.assertRaises(WorkflowError):catalog.metadata(kind)

    def test_source_bytes_and_notice_hash_changes_fail_closed(self):
        with patch.object(catalog, 'PINS', {**catalog.PINS, 'catalog/source-catalog.json': '0'*64}):
            with self.assertRaises(WorkflowError):catalog.metadata('references')
        with patch.object(catalog, 'file_hash', return_value='0'*64):
            with self.assertRaises(WorkflowError):catalog.metadata('references')


class MetadataHandlerTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.FamilyHistoryHttpTests();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def test_account_bound_authenticated_readonly_responses_and_revision(self):
        before = self.f.snapshot()
        for prefix, kind in (('reference-catalog', 'references'), ('style-gallery', 'styles')):
            for account in ('neutral', 'second'):
                code, value, raw = self.f.get('/api/' + prefix + '/' + account)
                self.assertEqual(code, 200, value);self.f.assert_no_secret(raw)
                self.assertEqual(value['account'], account);self.assertEqual(value['kind'], kind)
                self.assertEqual(value['revision'], digest({k:v for k,v in value.items() if k != 'revision'}))
                self.assertIs(value['actual_render'], False);self.assertIs(value['planning_supported'], False)
                self.assertIn(b'Cache-Control: no-store', raw)
        self.assertEqual(self.f.snapshot(), before)

    def test_auth_origin_duplicate_origin_closing_unknown_account_and_source_stale(self):
        for prefix in ('reference-catalog', 'style-gallery'):
            path = '/api/' + prefix + '/neutral'
            self.assertEqual(self.f.get(path, cookie=False)[0], 401)
            self.assertEqual(self.f.get(path, headers=['Origin: https://attacker.test'])[0], 403)
            self.assertEqual(self.f.get(path, headers=['Origin: http://127.0.0.1:43333']*2)[0], 403)
            self.assertEqual(self.f.get('/api/' + prefix + '/unknown')[0], 400)
            self.assertEqual(self.f.get(path + '/extra')[0], 400)
            self.server = self.f.server;self.server._closing = True
            self.assertEqual(self.f.get(path)[0], 403);self.server._closing = False
            with patch.object(self.f.d, 'assert_runtime_current', side_effect=WorkflowError('SOURCE_STALE')):
                self.assertEqual(self.f.get(path)[0], 400)
            self.assertEqual(self.f.post(path, {})[0], 404)

    def test_malformed_local_shape_yields_controlled_error_no_metadata(self):
        for raw in ([], {'schema_version':True, 'styles':[]}, {'schema_version':1, 'styles':[{'id': []}]}):
            with patch.object(catalog, 'pinned', return_value=raw):
                code, value, _ = self.f.get('/api/style-gallery/neutral')
                self.assertEqual(code, 400);self.assertEqual(value, {'error':'REFERENCE_CATALOG_INVALID_OR_UNAVAILABLE'})


class GalleryDomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        case = fixture.FamilyHistoryHttpTests();case.setUp()
        try:
            metadata = {}
            for account in ('neutral', 'second'):
                for prefix in ('reference-catalog', 'style-gallery'):
                    path = '/api/' + prefix + '/' + account
                    code, value, _ = case.get(path)
                    if code != 200:raise AssertionError(value)
                    metadata[path] = value
            contract_code,contract_value,_=case.post('/api/template-families/fields', {'account':'neutral','family':'contour-trace','version':'1.0.0','example':'short-silent'})
            if contract_code!=200:raise AssertionError('Fields Handler fixture unavailable: HTTP '+str(contract_code))
            cls.fixture = dict(catalog=capabilities(), html=(ROOT/'dashboard/index.html').read_text(),
                source=(ROOT/'dashboard/template-families.js').read_text(),
                contract=contract_value,
                prependSources=[(ROOT/'dashboard'/name).read_text() for name in ('template-editor.js','reference-gallery.js')], metadata=metadata)
        finally:case.doCleanups()

    def probe(self, group):
        value = dict(self.fixture, group=group)
        result = subprocess.run(['node', str(ROOT/'tests/reference_gallery_probe.mjs')], input=json.dumps(value),
            text=True, capture_output=True, cwd=ROOT, timeout=45, env={'PATH':os.environ.get('PATH',''),'DO_NOT_TRACK':'1'})
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout), {'passed':group})

    def test_browse_search_filter_reset_details_and_safe_external_links(self):self.probe('browse')
    def test_palette_application_exact_context_and_other_raw_lexemes_preserved(self):self.probe('apply')
    def test_stale_success_and_rejection_account_template_example_engine_navigation(self):self.probe('stale')
    def test_malformed_envelopes_metadata_and_failed_load_recovery(self):self.probe('malformed')
    def test_pending_field_edits_filtered_selection_and_prepare_inflight_block_palette(self):self.probe('preserve')

    def test_palette_near_byte_limit_commits_atomically_or_preserves_exact_raw_draft(self):self.probe('bounds')
    def test_sibling_gallery_reload_preserves_keyboard_focus_and_own_card_focus(self):self.probe('focus')

    def test_disabled_palette_action_has_associated_reason_only_for_current_incompatibility(self):self.probe('compatibilityReason')
