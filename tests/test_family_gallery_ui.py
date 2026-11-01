"""Actual gallery script and HTML in an offline DOM model; no browser QA claim."""
import json
import os
from pathlib import Path
import subprocess
import unittest
from html.parser import HTMLParser
import sys
from storymotion.template_families import capabilities

ROOT = Path(__file__).resolve().parents[1]


class FamilyGalleryUiTests(unittest.TestCase):
    def test_gallery_is_a_full_width_shell_child_and_security_stays_in_connections(self):
        class Structure(HTMLParser):
            def __init__(self):super().__init__();self.stack=[];self.ancestors={}
            def handle_starttag(self,tag,attrs):
                attrs=dict(attrs)
                if attrs.get('id') in ('family-studio','connection-security'):
                    self.ancestors[attrs['id']]=list(self.stack)
                if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):
                    self.stack.append((tag,attrs))
            def handle_endtag(self,tag):
                if self.stack and self.stack[-1][0]==tag:self.stack.pop()
                else:raise AssertionError('Unbalanced HTML around '+tag)
        parsed=Structure();parsed.feed((ROOT/'dashboard/index.html').read_text())
        self.assertEqual(parsed.stack,[])
        gallery=parsed.ancestors['family-studio']
        self.assertEqual(gallery[-1][1].get('class'),'shell')
        self.assertFalse(any('connections' in attrs.get('class','').split() for _,attrs in gallery))
        self.assertTrue(any('connections' in attrs.get('class','').split() for _,attrs in parsed.ancestors['connection-security']))
        import re
        css=(ROOT/'dashboard/style.css').read_text()
        rule=re.search(r'#family-studio\s*\{([^}]+)\}',css).group(1)
        self.assertRegex(rule,r'grid-column\s*:\s*1\s*/\s*-1')
        self.assertRegex(rule,r'width\s*:\s*100%')
        self.assertIn('min-width:0',rule)

    def probe(self, groups):
        data = {'catalog':capabilities(),'html':(ROOT/'dashboard/index.html').read_text(),
                'source':(ROOT/'dashboard/template-families.js').read_text(),'groups':groups}
        result = subprocess.run(['node',str(ROOT/'tests/family_gallery_probe.mjs')],input=json.dumps(data),
            capture_output=True,text=True,cwd=ROOT,timeout=120,env={'PATH':os.environ.get('PATH',''),'DO_NOT_TRACK':'1'})
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        value=json.loads(result.stdout);self.assertEqual(value['passed'],groups);self.assertEqual(value['failures'],[])
        if value['metrics']:print('Gallery DOM metrics: '+json.dumps(value['metrics'],sort_keys=True),file=sys.stderr)

    def test_edited_draft_survives_filter_reset_and_reload(self):self.probe(['draft'])
    def test_zero_results_block_prepare_and_reset_recovers_selection(self):self.probe(['empty'])
    def test_template_example_and_account_drafts_are_isolated(self):self.probe(['variants','accountDrafts'])
    def test_malformed_json_and_mismatched_selection_never_dispatch(self):self.probe(['malformed'])
    def test_exact_91_id_182_example_defaults(self):self.probe(['allExamples'])
    def test_metadata_is_complete_truthful_and_text_only(self):self.probe(['metadata'])
    def test_filter_combinations_and_91_topic_searches(self):self.probe(['searchAndFilters'])
    def test_seven_inflight_context_changes_keep_original_receipt(self):self.probe(['stale'])
    def test_source_lookup_uses_immutable_original_snapshot(self):self.probe(['sourceSnapshot'])
    def test_duplicate_submit_and_error_retry_have_no_automatic_replay(self):self.probe(['duplicateAndRetry'])
    def test_reload_error_recovery_example_change_and_keyboard_focus(self):self.probe(['reloadErrorsAndFocus'])
    def test_loading_failure_retry_and_malformed_catalog_preserve_drafts(self):self.probe(['loadStates','malformedCatalog'])
    def test_malformed_api_response_retry_and_mismatched_receipt_remain_separate(self):self.probe(['malformedResponse','mismatch'])
    def test_saved_history_detail_downloads_and_receipt_link_do_not_replace_drafts(self):self.probe(['history'])
    def test_history_account_changes_errors_and_forged_links_are_isolated(self):self.probe(['historySafety'])
    def test_catalog_account_removal_invalidates_loaded_and_pending_history(self):self.probe(['historyAccountReload'])

    def test_actual_html_labels_live_regions_native_controls_and_scoped_mobile_rules(self):
        class Tags(HTMLParser):
            def __init__(self):super().__init__();self.ids={};self.labels=[]
            def handle_starttag(self,tag,attrs):
                values=dict(attrs)
                if 'id' in values:
                    self.assert_unique=values['id'] not in self.ids
                    if not self.assert_unique:raise AssertionError('Duplicate HTML ID')
                    self.ids[values['id']]=(tag,values)
                if tag=='label' and 'for' in values:self.labels.append(values['for'])
        html=(ROOT/'dashboard/index.html').read_text();parsed=Tags();parsed.feed(html)
        for name in ('family-search','family-filter-niche','family-filter-type','family-filter-media','family-filter-engine','family-filter-state','family-account','family-select','family-example','family-engine','family-spec','family-claims'):
            self.assertIn(name,parsed.labels);self.assertIn(name,parsed.ids)
        for name in ('family-count','family-status','family-result'):
            self.assertEqual(parsed.ids[name][1]['aria-live'],'polite');self.assertEqual(parsed.ids[name][1]['role'],'status')
        self.assertIn('disabled',parsed.ids['family-prepare'][1]);self.assertIn('required',parsed.ids['family-select'][1])
        for _,attrs in parsed.ids.values():
            for name in ('aria-describedby','aria-labelledby','aria-controls'):
                for target in attrs.get(name,'').split():self.assertIn(target,parsed.ids)
        css=(ROOT/'dashboard/style.css').read_text();gallery=css.split('/* Gallery controls',1)[1]
        for rule in ('min-width:0','overflow-wrap:anywhere','white-space:pre-wrap','@media (max-width:40rem)','grid-template-columns:minmax(0,1fr)','[hidden] { display:none !important; }'):
            self.assertIn(rule,gallery)
        source=(ROOT/'dashboard/template-families.js').read_text()
        for sink in ('innerHTML','outerHTML','insertAdjacentHTML','localStorage','sessionStorage','eval(','new Function'):
            self.assertNotIn(sink,source)
