from pack_fixture_case import PackFixtureCase
"""Synthetic declarations only; these tests do not claim capture/OCR/human QA."""
import copy
import unittest
from storymotion.qa_contract import build_sampling_plan,report_template,validate_report,REQUIRED_CHECKS,optional_import_policy
from storymotion.security import WorkflowError,digest


def complete_fixture():
    brief={'duration':3,'scenes':[{'id':'first','start':0,'end':1.5,'heading':'Işık ve gölge'},{'id':'second','start':1.5,'end':3,'heading':'İki ayrı iz'}],
        'cues':[{'start':0,'end':3,'text':'Çığ, ışık, İpek, öğüt ve şüphe.'}]}
    plan=build_sampling_plan(brief,'a'*64,{'assets/drawing.svg':'b'*64},scene_keyframes={'first':[0,15,44],'second':[45,60,89]},source_fingerprint='c'*64,board_capacity=4)
    report=report_template(plan);manifest={}
    def add(ident,kind,frame=None,width=None,height=None,bounds=None,parent=None,pixel=None):
        path='qa/'+ident+('.png' if kind in {'frame','crop','board'} else '.json');sha=digest(ident)
        item={'id':ident,'kind':kind,'path':path,'sha256':sha,'pixel_sha256':pixel,'render_sha256':plan['render_sha256'],'frame':frame,'bounds':bounds,'parent_id':parent}
        report['evidence'].append(item);manifest[path]={'sha256':sha,'pixel_sha256':pixel,'width':width,'height':height};return ident
    for order,ids in plan['seek_orders'].items():
        captures=[]
        for ident in ids:
            frame=next(s['frame'] for s in plan['samples'] if s['id']==ident)
            evid=add(order+'-'+ident,'frame',frame,1080,1920,pixel=digest(frame))
            captures.append({'sample_id':ident,'frame':frame,'seed':plan['seed'],'asset_hashes':plan['asset_hashes'],'evidence_id':evid})
            if order=='forward':report['coverage']['samples'].append({'sample_id':ident,'evidence_id':evid})
        report['coverage']['seek_runs'].append({'id':'run-'+order,'renderer_instance':'instance-'+order,'order':order,'sample_ids':ids,'captures':captures})
    covered={s['sample_id']:s['evidence_id'] for s in report['coverage']['samples']}
    for page in plan['boards']:
        evid=add('board-'+str(page['page']),'board',width=page['width'],height=page['height'],pixel=digest(page))
        report['coverage']['board_pages'].append({'page':page['page'],'evidence_id':evid,'slots':[dict(slot,frame_evidence_id=covered[slot['sample_id']]) for slot in page['slots']]})
    measurement=add('measurement','measurement');human=add('human-proof','human')
    report['checks']=[{'id':ident,'status':'pass','render_sha256':plan['render_sha256'],'evidence_ids':[measurement],'note':'synthetic contract fixture only'} for ident in REQUIRED_CHECKS]
    report['ocr'].update(status='pass',unicode_verified=True,observations=[{'expectation_id':e['id'],'evidence_id':covered[e['sample_id']],'observed_text':e['text']} for e in plan['text_expectations']])
    report['human_reviews']=[{'kind':kind,'status':'pass','reviewer':'synthetic-test-not-a-person','render_sha256':plan['render_sha256'],'evidence_ids':[human]} for kind in ['listening','final_watch']]
    return brief,plan,report,manifest,add


class QAContractTests(PackFixtureCase):
    def result(self,plan,report,manifest,render=None):return validate_report(report,expected_plan=plan,current_render_sha256=render or plan['render_sha256'],artifact_manifest=manifest)
    def test_plan_has_keyframes_boundary_triples_paginated_exact_coverage(self):
        brief,plan,report,manifest,_=complete_fixture()
        self.assertEqual(self.result(plan,report,manifest)['status'],'pass')
        roles={r for s in plan['samples'] for r in s['roles']}
        self.assertTrue({'transition:first-to-second:before','transition:first-to-second:mid','transition:first-to-second:after'}<=roles)
        self.assertEqual([s['sample_id'] for p in plan['boards'] for s in p['slots']],plan['seek_orders']['forward'])
        again=build_sampling_plan(brief,'a'*64,{'assets/drawing.svg':'b'*64},scene_keyframes={'first':[0,15,44],'second':[45,60,89]},source_fingerprint='c'*64,board_capacity=4)
        self.assertEqual(plan,again)

    def test_exit_zero_or_score_eight_never_fills_missing_checks(self):
        _,plan,_,_,_=complete_fixture();report=report_template(plan)
        report['upstream'].update(name='sagecut',commit='549f745959d29e0452b238ac23d98b1cc2cdcfb3',mode='saved_local_measurements',exit_code=0,score=8)
        self.assertEqual(self.result(plan,report,{})['status'],'incomplete')

    def test_final_render_replacement_invalidates_approval(self):
        _,plan,report,manifest,_=complete_fixture();result=self.result(plan,report,manifest,'d'*64)
        self.assertEqual(result['status'],'fail');self.assertIsNone(result['approval_fingerprint'])

    def test_missing_human_ocr_or_board_is_incomplete(self):
        for missing in ['human','ocr','page','samples']:
            _,plan,r,m,_=complete_fixture()
            if missing=='human':r['human_reviews']=[]
            if missing=='ocr':r['ocr']['status']='skipped'
            if missing=='page':r['coverage']['board_pages'].pop()
            if missing=='samples':r['coverage']['samples'].pop()
            with self.subTest(missing=missing):self.assertEqual(self.result(plan,r,m)['status'],'incomplete')

    def test_turkish_unicode_difference_fails_instead_of_ascii_folding(self):
        _,plan,r,m,_=complete_fixture();r['ocr']['observations'][0]['observed_text']='Isik ve golge'
        self.assertEqual(self.result(plan,r,m)['status'],'fail')

    def test_hash_and_seek_context_mismatch_fail(self):
        for field in ['hash','frame','seed','assets','pixels']:
            _,plan,r,m,_=complete_fixture();capture=r['coverage']['seek_runs'][1]['captures'][0]
            if field=='hash':m[r['evidence'][0]['path']]['sha256']='d'*64
            if field=='frame':capture['frame']+=1
            if field=='seed':capture['seed']+=1
            if field=='assets':capture['asset_hashes']={'assets/drawing.svg':'d'*64}
            if field=='pixels':
                ev=next(e for e in r['evidence'] if e['id']==capture['evidence_id']);ev['pixel_sha256']='d'*64;m[ev['path']]['pixel_sha256']='d'*64
            with self.subTest(field=field):self.assertEqual(self.result(plan,r,m)['status'],'fail')

    def test_critical_issue_requires_crop_and_exact_scene_recheck(self):
        _,plan,r,m,add=complete_fixture();sample=plan['samples'][0]
        crop=add('issue-crop','crop',sample['frame'],100,100,{'x':0,'y':0,'width':100,'height':100},'forward-'+sample['id'],pixel='e'*64)
        issue={'id':'issue-1','frame':sample['frame'],'scene_id':'first','severity':'critical','status':'open','description':'Synthetic clipping issue',
            'local_fix':'','crop_evidence_id':crop,'affected_scene_ids':['first'],'affected_check_ids':['visual_review'],'recheck':None};r['issues']=[issue]
        self.assertEqual(self.result(plan,r,m)['status'],'fail')
        issue.update(status='fixed',local_fix='Synthetic fix note')
        self.assertEqual(self.result(plan,r,m)['status'],'incomplete')
        issue['recheck']={'status':'pass','render_sha256':plan['render_sha256'],'seed':plan['seed'],'asset_hashes':plan['asset_hashes'],
            'sample_ids':[s['id'] for s in plan['samples'] if 'first' in s['scene_ids']],'check_ids':['visual_review'],'evidence_ids':[crop]}
        self.assertEqual(self.result(plan,r,m)['status'],'pass')
        next(e for e in r['evidence'] if e['id']==crop)['bounds']['x']=1080
        self.assertEqual(self.result(plan,r,m)['status'],'fail')

    def test_strict_data_paths_and_no_upstream_executor(self):
        _,plan,r,m,_=complete_fixture();r['evidence'][0]['path']='../../private.png'
        with self.assertRaises(WorkflowError):self.result(plan,r,m)
        self.assertFalse(optional_import_policy('saved_local_measurements')['execution_enabled'])
        with self.assertRaises(WorkflowError):optional_import_policy('gate --no-sage')
        r=report_template(plan);r['score']=8
        with self.assertRaises(WorkflowError):self.result(plan,r,{})


if __name__=='__main__':unittest.main()
