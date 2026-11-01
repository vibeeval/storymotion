"""Production editor/gallery in an offline DOM, using genuine Handler fixtures.

This verifies source behavior, not browser/mobile/native acceptance.
"""
import json
import os
from pathlib import Path
import subprocess
import unittest

from storymotion.template_families import capabilities
from storymotion.template_fields import contract, examples
import test_template_fields
from test_template_intake import covering_claims

ROOT = Path(__file__).resolve().parents[1]


class TemplateEditorUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = test_template_fields.FieldHttpTests()
        fixture.setUp()
        try:
            catalog = capabilities()
            contracts = {}
            for row in catalog['families']:
                for example in row['examples']:
                    for account in ('neutral', 'studio-b'):
                        value = contract(account, row['id'], row['version'], example['name'])
                        contracts[json.dumps([account, row['id'], example['name']], ensure_ascii=False, separators=(',', ':'))] = value
            validations = []
            for family in ('kinetic-grid', 'exploded-blueprint'):
                data = fixture.payload(family)
                spec = json.loads(data['raw_spec'])
                if family == 'exploded-blueprint':
                    spec['parameters'].pop('separation', None)
                    data['raw_spec'] = json.dumps(spec, ensure_ascii=False, indent=2)
                code, value, _ = fixture.endpoint('validate', data)
                if code != 200: raise AssertionError(value)
                validations.append({'data': data, 'value': value})
            revision = fixture.sources()
            data = fixture.payload('dimension-construction')
            spec = json.loads(data['raw_spec'])
            spec['parameters']['dimension_values']['width'] = 160.12345678901234
            data.update(raw_spec=json.dumps(spec, ensure_ascii=False, indent=2), claims=covering_claims(spec),
                        source_revision=revision, canon_revision=None)
            code, value, _ = fixture.endpoint('validate', data)
            if code != 200: raise AssertionError(value)
            validations.append({'data': data, 'value': value})
            base=validations[0]['data'];spec=json.loads(base['raw_spec'])
            rejected={**base,'raw_spec':json.dumps({**spec,'parameters':{**spec['parameters'],'title':''}})}
            code,value,_=fixture.endpoint('validate',rejected)
            if code!=400 or not value.get('error','').startswith('TEMPLATE_INPUT:'):raise AssertionError(value)
            rejections=[{'data':rejected,'value':value,'status':code}]
            repaired={**base,'raw_spec':base['raw_spec'].replace('"title": '+json.dumps(spec['parameters']['title']),
                '"title": '+json.dumps(spec['parameters']['title'],ensure_ascii=False),1)}
            code,value,_=fixture.endpoint('validate',repaired)
            if code!=200:raise AssertionError(value)
            validations.append({'data':repaired,'value':value})
            cls.data = {'catalog': catalog, 'contracts': contracts, 'validations': validations, 'rejections':rejections,
                        'refs': {'account':'neutral', 'sources':{'revision':revision}, 'canon':None},
                        'html': (ROOT/'dashboard/index.html').read_text(),
                        'source': (ROOT/'dashboard/template-families.js').read_text(),
                        'prependSources': [(ROOT/'dashboard/template-editor.js').read_text()]}
        finally:
            fixture.doCleanups()

    def probe(self, groups):
        result = subprocess.run(['node', str(ROOT/'tests/template_editor_probe.mjs')],
            input=json.dumps({**self.data, 'groups': groups}), text=True, capture_output=True,
            cwd=ROOT, timeout=120, env={'PATH':os.environ.get('PATH',''),'DO_NOT_TRACK':'1'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value['passed'], groups)
        self.assertEqual(value['failures'], [])
        if value.get('metrics'): print('Editor metrics: '+json.dumps(value['metrics'], sort_keys=True))

    def test_all_91_templates_182_examples_declared_controls_and_fallback_roundtrips(self): self.probe(['allExamples'])
    def test_exact_precision_and_incomplete_numeric_drafts_never_become_zero(self): self.probe(['numbers'])
    def test_collection_bounds_optional_defaults_and_unknown_items(self): self.probe(['collections'])
    def test_enums_strings_booleans_and_extra_keys_remain_lossless(self): self.probe(['scalars'])
    def test_duplicate_unsafe_deep_and_malformed_json_never_prepares(self): self.probe(['malformed'])
    def test_raw_json_conflicts_and_mode_switch_retain_pending_fields(self): self.probe(['conflicts'])
    def test_per_account_template_example_ram_drafts_survive_filter_reset_reload(self): self.probe(['drafts'])
    def test_real_handler_validation_shows_normalization_without_auto_applying(self): self.probe(['validation'])
    def test_late_contract_reply_cannot_override_selection_or_unlock_new_request(self): self.probe(['schemaRaces'])
    def test_late_validation_replies_preserve_newer_spec_claims_engine_account_and_plan(self): self.probe(['validationRaces'])
    def test_source_lookup_and_normalization_application_recheck_bound_heads(self): self.probe(['sourceRaces'])
    def test_malformed_replies_retry_and_duplicate_clicks_have_no_automatic_replay(self): self.probe(['malformedReplies'])
    def test_semantic_rejection_blocks_prepare_until_exact_current_draft_is_valid(self): self.probe(['semanticGate'])
    def test_semantic_rejection_gate_is_per_draft_and_survives_in_page_refresh(self): self.probe(['semanticIsolation'])
    def test_stale_semantic_failure_cannot_block_a_new_selection(self): self.probe(['semanticStale'])
    def test_old_normalization_source_lookup_preserves_new_result_and_status(self): self.probe(['normalizeLateReject','normalizeLateSuccess','normalizeLateChangedHeads'])
    def test_coverage_is_unavailable_without_a_schema_bound_to_the_current_selection(self): self.probe(['coverageScope'])
    def test_labels_status_mobile_scope_and_no_dynamic_code_or_browser_storage(self):
        source=(ROOT/'dashboard/template-editor.js').read_text()
        for sink in ('innerHTML','outerHTML','insertAdjacentHTML','localStorage','sessionStorage','eval(','new Function','toFixed(', 'parseInt('):
            self.assertNotIn(sink, source)
        html=(ROOT/'dashboard/index.html').read_text()
        for name in ('load','toggle','apply','discard','validate','normalize'):
            self.assertIn('id="family-editor-'+name+'" type="button"', html)
        self.assertIn('id="family-editor-status" role="status" aria-live="polite"', html)
        self.assertLess(html.index('/template-editor.js'), html.index('/template-families.js'))
        self.assertIn('#family-editor-fields', (ROOT/'dashboard/style.css').read_text())
