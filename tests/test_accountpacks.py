from pack_fixture_case import PackFixtureCase
from storymotion.account_packs import render_profile
import json
import tempfile
import unittest
from pathlib import Path

from storymotion.creative import ACCOUNTS,load_pack,output_schema,validate_proposal
from storymotion.engine import Engine,ROOT
from storymotion.security import WorkflowError


def fixture(account):return json.loads((ROOT/'tests/fixtures/examples/golden'/f'{account}.json').read_text())


class AccountPackTests(PackFixtureCase):
    def test_four_versioned_source_pins_and_rules(self):
        for account in ACCOUNTS:
            pack=load_pack(account)
            self.assertEqual(pack['version'],'1.0.0');self.assertTrue(pack['source_revision'])
            self.assertEqual(set(pack['rule_ids']),{r['id'] for r in pack['rules']})
            self.assertEqual(set(pack['scene_contract']),set(pack['scene_actions']))
            self.assertFalse(pack['acceptance']['publication_ready'])
            profile=render_profile(account)
            self.assertEqual(profile['palette'],pack['brand']['palette'])

    def test_golden_contracts_and_human_gates(self):
        for account in ACCOUNTS:
            proposal=validate_proposal(account,fixture(account))
            self.assertFalse(proposal['creative']['audit']['publication_ready'])
            self.assertEqual(proposal['creative']['audit']['creative_acceptance'],'pending_human_review')
            self.assertEqual(proposal['alignment'],'provisional_silent');self.assertIsNone(proposal['audio'])
            self.assertEqual(len({s['object_id'] for s in proposal['scenes']}),1)

    def test_schema_is_closed_and_provider_compatible(self):
        def walk(s):
            if s['type']=='object':
                self.assertFalse(s['additionalProperties']);self.assertEqual(set(s['required']),set(s['properties']))
                for item in s['properties'].values():walk(item)
            elif s['type']=='array':walk(s['items'])
        for account in ACCOUNTS:walk(output_schema(account))
        bad=fixture('sample-flow');bad['raw_html']='<svg/>'
        with self.assertRaises(WorkflowError):validate_proposal('sample-flow',bad)

    def test_model_cannot_supply_publication_approval(self):
        p=fixture('sample-flow');p['creative']['audit']={'publication_ready':True,'script_sha256':'invented'}
        normalized=validate_proposal('sample-flow',p)
        self.assertFalse(normalized['creative']['audit']['publication_ready'])
        self.assertNotEqual(normalized['creative']['audit']['script_sha256'],'invented')

    def test_cross_brand_action_is_rejected(self):
        p=fixture('sample-mechanism');p['scenes'][0]['action']='approval-gate'
        with self.assertRaises(WorkflowError):validate_proposal('sample-mechanism',p)

    def test_claims_need_host_source_registry(self):
        p=fixture('sample-mechanism');p['claims']=[{'text':'Yalnız test iddiası','source':'source-1','scope':'Bu mekanik çizim'}]
        with self.assertRaises(WorkflowError):validate_proposal('sample-mechanism',p)
        with self.assertRaises(WorkflowError):validate_proposal('sample-mechanism',p,source_registry={'other':{}})
        n=validate_proposal('sample-mechanism',p,source_registry={'source-1':{'review':'not truth approval','url':'https://example.org/source'}})
        self.assertEqual(n['creative']['audit']['source_truth'],'pending_human_review')

    def test_model_html_urls_secrets_and_nonfinite_are_rejected(self):
        values=['<img src=x onerror=alert(1)>','https://example.test/asset.svg','javascript:alert(1)','sk-'+'synthetic'*5]
        for value in values:
            p=fixture('sample-flow');p['brief']=value
            with self.subTest(value=value[:12]),self.assertRaises(WorkflowError):validate_proposal('sample-flow',p)
        p=fixture('sample-flow');p['duration']=float('nan')
        with self.assertRaises(WorkflowError):validate_proposal('sample-flow',p)

    def test_state_ids_cannot_lie_about_motion(self):
        p=fixture('sample-mechanism');p['scenes'][0]['state_after']='released-open'
        with self.assertRaises(WorkflowError):validate_proposal('sample-mechanism',p)
        p=fixture('sample-mechanism');p['scenes'][0]['action']='lid-rise';p['scenes'][0].update(load_pack('sample-mechanism')['scene_contract']['lid-rise'])
        with self.assertRaises(WorkflowError):validate_proposal('sample-mechanism',p)

    def test_object_identity_and_description_continuity(self):
        for field,value in [('object_id','replacement-02'),('object_before','Önceki sahnede olmayan durum.')]:
            p=fixture('sample-flow');p['scenes'][1][field]=value
            with self.assertRaises(WorkflowError):validate_proposal('sample-flow',p)

    def test_character_wardrobe_and_canon_are_pinned(self):
        for mutate in ['character','wardrobe','canon','continuity']:
            p=fixture('sample-series')
            if mutate=='character':p['scenes'][1]['character_id']='different-person'
            if mutate=='wardrobe':p['creative']['characters'][0]['wardrobe']='cream-tshirt'
            if mutate=='canon':p['creative']['canon_status']='accepted_episode_03'
            if mutate=='continuity':p['continuity']['object_id']='second-envelope'
            with self.subTest(mutate=mutate),self.assertRaises(WorkflowError):validate_proposal('sample-series',p)

    def test_biraz_five_step_sequence_and_no_diagnosis(self):
        p=fixture('sample-reflection')
        self.assertEqual([s['action'] for s in p['scenes']],load_pack('sample-reflection')['scene_actions'])
        p['script']='Bu davranışın kesin nedeni budur.';p['cues']=[{'start':0,'end':16,'text':p['script']}]
        with self.assertRaises(WorkflowError):validate_proposal('sample-reflection',p)

    def test_cues_exact_and_duration_bounded(self):
        p=fixture('sample-flow');p['cues'][0]['text']=p['cues'][0]['text'].lower()
        with self.assertRaises(WorkflowError):validate_proposal('sample-flow',p)
        p=fixture('sample-flow');p['duration']=186.9
        with self.assertRaises(WorkflowError):validate_proposal('sample-flow',p)

    def test_history_renaming_topic_cannot_hide_same_script(self):
        old=validate_proposal('sample-flow',fixture('sample-flow'))
        p=fixture('sample-flow');p['creative']['topic_id']='renamed';p['creative']['visual_motif']='renamed';p['scenes'][0]['camera']='push-in'
        with self.assertRaises(WorkflowError):validate_proposal('sample-flow',p,history=[old])

    def test_history_renaming_ids_cannot_hide_same_compiled_sequence(self):
        old=validate_proposal('sample-flow',fixture('sample-flow'))
        p=fixture('sample-flow');p['creative']['topic_id']='different';p['creative']['visual_motif']='different'
        p['script']=p['script'].replace('geliyor','ulaşıyor');p['cues'][0]['text']=p['cues'][0]['text'].replace('geliyor','ulaşıyor')
        for s in p['scenes']:s['object_id']='new-name'
        with self.assertRaises(WorkflowError):validate_proposal('sample-flow',p,history=[old])

    def test_history_other_account_does_not_block(self):
        old=validate_proposal('sample-series',fixture('sample-series'))
        self.assertEqual(validate_proposal('sample-flow',fixture('sample-flow'),history=[old])['creative']['audit']['history_entries_checked'],0)

    def test_two_engine_prepare_uses_owned_same_subject_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            for account in ACCOUNTS:
                for renderer in ['hyperframes','remotion']:
                    e=Engine(Path(tmp)/account/renderer);job=e.create(ROOT/'tests/fixtures/examples/golden'/f'{account}.json',render_engine=renderer)['job'];e.run(job,'prepare')
                    out=e.directory(job);html=(out/'index.html').read_text()
                    self.assertIn('data-visual-family="'+load_pack(account)['visual_family']+'"',html);self.assertIn('data-object-id="'+fixture(account)['scenes'][0]['object_id']+'"',html)
                    self.assertNotIn('https://cdn.',html)
                    if renderer=='remotion':
                        props=json.loads((out/'remotion-props.json').read_text())
                        for i,scene in enumerate(props['brief']['scenes']):
                            self.assertIn(props['vectors'][f's{i}'],html)
                            self.assertIn(scene['object_id'],props['vectors'][f's{i}'])
                    self.assertIn('data-visual-family="'+load_pack(account)['visual_family']+'"',(out/'cover.svg').read_text())

    def test_legacy_fixtures_still_plan_and_new_accounts_require_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine(Path(tmp)/'work')
            for account in ['sample-mechanism','sample-series']:e.plan(ROOT/'tests/fixtures/examples'/f'{account}.json')
            p=fixture('sample-reflection');p.pop('creative');path=Path(tmp)/'invalid.json';path.write_text(json.dumps(p))
            with self.assertRaises(WorkflowError):e.plan(path)


if __name__=='__main__':unittest.main()
