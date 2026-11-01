from pack_fixture_case import PackFixtureCase
"""Service boundary/DB/tamper tests. Capture execution has a separate real smoke."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from storymotion.qa_contract import build_sampling_plan,report_template
from storymotion.qa_review import ReviewService
from storymotion.security import WorkflowError,digest,file_hash,write_json


class QAReviewTests(PackFixtureCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.media=self.root/'media/job/render-1080.mp4';self.media.parent.mkdir(parents=True);self.media.write_bytes(b'synthetic unit bytes; not a video')
        self.brief={'duration':3,'scenes':[{'id':'first','start':0,'end':3,'heading':'İlk kare'}],'cues':[{'start':0,'end':3,'text':'Işık ve şüphe.'}]}
        self.e=ReviewService(self.root/'qa',media_root=self.root/'media')
        def fake_build(ident,payload,media):
            out=self.e._directory(ident);out.mkdir(parents=True,exist_ok=True)
            plan=build_sampling_plan(self.brief,payload['render_sha256'],payload['asset_hashes'],source_fingerprint=payload['source_fingerprint'])
            report=report_template(plan);path=out/'proof.json';write_json(path,{'unit_fixture':True})
            report['evidence']=[{'id':'unit-proof','kind':'measurement','path':'proof.json','sha256':file_hash(path),'pixel_sha256':None,
                'render_sha256':payload['render_sha256'],'frame':None,'bounds':None,'parent_id':None}]
            manifest={'proof.json':{'sha256':file_hash(path),'pixel_sha256':None,'width':None,'height':None}}
            self.e._persist(ident,payload,plan,report,manifest)
        self.builder=patch.object(self.e,'_build',side_effect=fake_build);self.build=self.builder.start()
        self.successful_build=fake_build
    def tearDown(self):self.builder.stop();self.e.db.close();self.temp.cleanup()
    def create(self):return self.e.create(self.media,self.brief)
    def snapshot(self):
        rows=[self.e.db.execute('SELECT * FROM '+table+' ORDER BY 1,2').fetchall() for table in ['reviews','defects']]
        files={str(p.relative_to(self.root/'qa')):p.read_bytes() for p in (self.root/'qa').rglob('*') if p.is_file()}
        return rows,files,self.e.status(self.e.db.execute('SELECT id FROM reviews').fetchone()[0])

    def issue(self):
        return {'frame':0,'scene_id':'first','severity':'critical','description':'Synthetic local defect','local_fix':'',
            'affected_scene_ids':['first'],'affected_check_ids':['visual_review'],'bounds':{'x':0,'y':0,'width':100,'height':100}}

    def declared_crop(self,out,media,plan,report,manifest,issue):
        """Only synthetic bytes/metadata for transactional tests; no image claim."""
        bounds=issue.pop('_bounds');frame_id='mock-frame-'+issue['id'];crop_id='mock-crop-'+issue['id']
        for ident,kind,rel,width,height,b,parent in [
            (frame_id,'frame','frames/'+frame_id+'.png',1080,1920,None,None),
            (crop_id,'crop','crops/'+crop_id+'.png',bounds['width'],bounds['height'],bounds,frame_id)]:
            path=out/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(('synthetic '+ident).encode());sha=file_hash(path);pixel=digest(ident)
            manifest[rel]={'sha256':sha,'pixel_sha256':pixel,'width':width,'height':height}
            report['evidence'].append({'id':ident,'kind':kind,'path':rel,'sha256':sha,'pixel_sha256':pixel,'render_sha256':plan['render_sha256'],
                'frame':issue['frame'],'bounds':b,'parent_id':parent})
        issue['crop_evidence_id']=crop_id

    def test_create_reuses_completed_capture_and_stays_incomplete(self):
        first=self.create();second=self.create()
        self.assertEqual(first['review_id'],second['review_id']);self.assertEqual(self.build.call_count,1)
        self.assertEqual(first['status'],'incomplete');self.assertIsNone(first['approval_fingerprint'])

    def test_host_media_boundary_fixed_name_and_symlinks(self):
        outside=self.root/'outside/render-1080.mp4';outside.parent.mkdir();outside.write_bytes(b'x')
        with self.assertRaises(WorkflowError):self.e.create(outside,self.brief)
        wrong=self.media.with_name('arbitrary.mp4');wrong.write_bytes(b'x')
        with self.assertRaises(WorkflowError):self.e.create(wrong,self.brief)
        link=self.root/'media/link';link.symlink_to(self.media.parent,target_is_directory=True)
        with self.assertRaises(WorkflowError):self.e.create(link/'render-1080.mp4',self.brief)
        self.build.assert_not_called()

    def test_metadata_tamper_is_pinned_in_sqlite_and_blocks_download(self):
        review=self.create()['review_id'];directory=self.root/'qa'/review
        for name in ['plan.json','report.json','artifact-manifest.json','result.json']:
            path=directory/name;before=path.read_bytes();path.write_bytes(before+b' ')
            with self.subTest(name=name),self.assertRaises(WorkflowError):self.e.file(review,name)
            self.assertEqual(self.e.status(review)['status'],'fail');path.write_bytes(before)
        self.assertEqual(self.e.status(review)['status'],'incomplete')

    def test_frame_or_measurement_tamper_and_unregistered_path_fail_closed(self):
        review=self.create()['review_id'];proof=self.root/'qa'/review/'proof.json';proof.write_text('{}')
        self.assertEqual(self.e.status(review)['status'],'fail')
        for path in ['proof.json','../outside.txt','unregistered.json']:
            with self.subTest(path=path),self.assertRaises(WorkflowError):self.e.file(review,path)

    def test_replaced_final_bytes_invalidate_old_review_durably(self):
        review=self.create()['review_id'];original=self.media.read_bytes();self.media.write_bytes(original+b'changed')
        self.assertEqual(self.e.status(review)['state'],'invalidated')
        self.media.write_bytes(original)
        self.assertEqual(self.e.status(review)['state'],'invalidated')
        with self.assertRaises(WorkflowError):self.e.file(review,'report.json')

    def test_issue_frame_scene_bounds_and_severity_are_bounded(self):
        review=self.create()['review_id'];value={'frame':0,'scene_id':'first','severity':'critical','description':'Kesilme','local_fix':'',
            'affected_scene_ids':['first'],'affected_check_ids':['visual_review'],'bounds':{'x':0,'y':0,'width':100,'height':100}}
        for mutate in ['frame','scene','bounds','severity','extra']:
            row=json.loads(json.dumps(value))
            if mutate=='frame':row['frame']=90
            if mutate=='scene':row['scene_id']='other'
            if mutate=='bounds':row['bounds']['x']=1080
            if mutate=='severity':row['severity']='anything'
            if mutate=='extra':row['shell']='unexpected'
            with self.subTest(mutate=mutate),self.assertRaises(WorkflowError):self.e.record_issue(review,row)

    def test_fix_note_alone_never_marks_qa_pass(self):
        review=self.create()['review_id'];value={'frame':0,'scene_id':'first','severity':'critical','description':'Synthetic issue','local_fix':'',
            'affected_scene_ids':['first'],'affected_check_ids':['visual_review'],'bounds':{'x':0,'y':0,'width':100,'height':100}}
        def fake_crop(out,media,plan,report,manifest,issue):issue.pop('_bounds',None);issue['crop_evidence_id']='absent-unit-crop'
        with patch.object(self.e,'_crop_issue',side_effect=fake_crop):result=self.e.record_issue(review,value)
        self.assertEqual(result['status'],'fail');ident=result['issues'][0]['id']
        fixed=self.e.resolve_issue(review,ident,'Only a declared fix; not actual source editing')
        self.assertEqual(fixed['status'],'incomplete');self.assertIsNone(fixed['approval_fingerprint'])
        self.assertIsNone(fixed['issues'][0]['recheck'])

    def test_initial_failure_retries_same_create_without_metadata(self):
        self.build.side_effect=WorkflowError('Injected initial capture failure')
        with self.assertRaises(WorkflowError):self.create()
        ident=self.e.db.execute('SELECT id FROM reviews').fetchone()[0]
        self.assertEqual(self.e._row(ident)[0],'failed');self.assertFalse((self.root/'qa'/ident/'report.json').exists())
        self.build.side_effect=self.successful_build
        result=self.create()
        self.assertEqual(result['review_id'],ident);self.assertEqual(result['state'],'ready');self.assertEqual(self.build.call_count,2)
        self.assertEqual(self.e._row(ident)[1]['capture_attempts'],2)

    def test_failed_and_crash_capturing_rows_recheck_without_metadata(self):
        for failure in [WorkflowError('Initial failure'),KeyboardInterrupt()]:
            with self.subTest(failure=type(failure).__name__):
                self.e.db.execute('DELETE FROM reviews');self.e.db.commit();self.build.side_effect=failure
                with self.assertRaises(type(failure)):self.create()
                ident=self.e.db.execute('SELECT id FROM reviews').fetchone()[0]
                self.assertIn(self.e._row(ident)[0],{'failed','capturing'})
                self.build.side_effect=self.successful_build
                self.assertEqual(self.e.recheck(ident)['state'],'ready')

    def test_cross_service_active_capture_is_not_dispatched_twice(self):
        entered=threading.Event();release=threading.Event();errors=[];results=[]
        def blocked(ident,payload,media):
            entered.set()
            if not release.wait(3):raise AssertionError('Test release timed out')
            self.successful_build(ident,payload,media)
        self.build.side_effect=blocked
        def create():
            try:results.append(self.create())
            except BaseException as error:errors.append(error)
        thread=threading.Thread(target=create);thread.start()
        self.assertTrue(entered.wait(2))
        second=ReviewService(self.root/'qa',media_root=self.root/'media')
        try:
            result=second.create(self.media,self.brief)
            self.assertEqual(result['state'],'capturing');self.assertEqual(self.build.call_count,1)
        finally:release.set();thread.join(3);second.db.close()
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[]);self.assertEqual(results[0]['state'],'ready')

    def test_expected_receipt_hash_and_binding_are_immutable(self):
        with self.assertRaises(WorkflowError):self.e.create(self.media,self.brief,expected_render_sha256='f'*64)
        self.assertEqual(self.e.db.execute('SELECT count(*) FROM reviews').fetchone()[0],0)
        binding={'job':'synthetic-job','engine':'hyperframes','receipt_sha256':'a'*64};expected=file_hash(self.media)
        result=self.e.create(self.media,self.brief,expected_render_sha256=expected,render_binding=binding)
        binding['engine']='remotion'
        _,stored=self.e._row(result['review_id'])
        self.assertEqual(stored['expected_render_sha256'],expected);self.assertEqual(stored['render_binding']['engine'],'hyperframes')
        alternate=self.e.create(self.media,self.brief,expected_render_sha256=expected,render_binding=binding)
        self.assertNotEqual(alternate['review_id'],result['review_id'])

    def test_capture_end_render_or_asset_change_fails_without_rebinding(self):
        asset=self.media.parent/'assets/drawing.svg';asset.parent.mkdir();asset.write_text('<svg/>')
        original_media=self.media.read_bytes();original_asset=asset.read_bytes();asset_hash=file_hash(asset);expected=file_hash(self.media)
        def changed(ident,payload,media):
            asset.write_text('<svg>changed</svg>');self.successful_build(ident,payload,media)
        self.build.side_effect=changed
        with self.assertRaises(WorkflowError):self.e.create(self.media,self.brief,expected_render_sha256=expected)
        ident=self.e.db.execute('SELECT id FROM reviews').fetchone()[0]
        self.assertEqual(self.e._row(ident)[1]['asset_hashes']['assets/drawing.svg'],asset_hash)
        self.assertEqual(self.e._row(ident)[0],'failed')
        asset.write_bytes(original_asset)
        def changed_media(ident,payload,media):
            media.write_bytes(original_media+b'changed');self.successful_build(ident,payload,media)
        self.build.side_effect=changed_media
        with self.assertRaises(WorkflowError):self.e.recheck(ident)
        self.assertEqual(self.e._row(ident)[1]['expected_render_sha256'],expected)
        self.media.write_bytes(original_media);self.build.side_effect=self.successful_build
        self.assertEqual(self.e.recheck(ident)['state'],'ready')

    def test_invalid_issue_full_schema_never_changes_db_files_or_status(self):
        review=self.create()['review_id'];before=self.snapshot()
        invalid=[dict(self.issue(),affected_scene_ids=['first']*13),dict(self.issue(),description='x'*2001),dict(self.issue(),local_fix='x'*2001)]
        with patch.object(self.e,'_crop_issue') as crop:
            for value in invalid:
                with self.subTest(field=len(value['affected_scene_ids'])),self.assertRaises(WorkflowError):self.e.record_issue(review,value)
                self.assertEqual(self.snapshot(),before)
            crop.assert_not_called()
        self.assertEqual(self.e.db.execute('SELECT count(*) FROM defects').fetchone()[0],0)
        self.assertEqual(self.e.recheck(review)['state'],'ready')

    def test_crop_failure_and_publish_db_failure_leave_no_partial_issue(self):
        review=self.create()['review_id'];before=self.snapshot()
        def failed_crop(out,*args):
            (out/'partial.txt').write_text('only staging');raise WorkflowError('Injected crop failure')
        with patch.object(self.e,'_crop_issue',side_effect=failed_crop),self.assertRaises(WorkflowError):self.e.record_issue(review,self.issue())
        self.assertEqual(self.snapshot(),before)
        with patch.object(self.e,'_crop_issue',side_effect=self.declared_crop),patch.object(self.e,'_write_review_transaction',side_effect=WorkflowError('Injected DB write failure')):
            with self.assertRaises(WorkflowError):self.e.record_issue(review,self.issue())
        self.assertEqual(self.snapshot(),before);self.assertEqual(self.e.db.execute('SELECT count(*) FROM defects').fetchone()[0],0)
        self.assertEqual(self.e.recheck(review)['state'],'ready')

    def test_valid_issue_and_report_commit_together_and_resolve_rolls_back(self):
        review=self.create()['review_id']
        with patch.object(self.e,'_crop_issue',side_effect=self.declared_crop):result=self.e.record_issue(review,self.issue())
        self.assertEqual(result['status'],'fail');self.assertEqual(len(result['issues']),1)
        self.assertEqual(self.e.db.execute('SELECT count(*) FROM defects').fetchone()[0],1)
        before=self.snapshot();ident=result['issues'][0]['id']
        with patch.object(self.e,'_write_review_transaction',side_effect=WorkflowError('Injected resolve DB failure')):
            with self.assertRaises(WorkflowError):self.e.resolve_issue(review,ident,'Declared fix')
        self.assertEqual(self.snapshot(),before)
        fixed=self.e.resolve_issue(review,ident,'Declared fix')
        self.assertEqual(fixed['issues'][0]['status'],'fixed');self.assertEqual(fixed['status'],'incomplete')


if __name__=='__main__':unittest.main()
