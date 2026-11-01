from pack_fixture_case import PackFixtureCase
"""Direct backend receipt gates. Synthetic bytes, no renderer/provider/install."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from storymotion.dashboard import Dashboard
from storymotion.engine import Engine
from storymotion.security import WorkflowError,canonical,file_hash,write_json
from storymotion.local_state import private_directory,write_private


class DashboardReviewBinding(PackFixtureCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.d=Dashboard(self.tmp.name)
        self.job=self.new_job('First selected job')
        self.engine='hyperframes';self.seed(self.job)
        self.fake=Mock()
        self.fake.create.return_value={'review_id':'1'*24}
        self.fake.status.return_value={'review_id':'1'*24,'status':'incomplete','state':'ready'}
        self.fake.files.return_value=[]
        self.d.reviews.service=self.fake
    def tearDown(self):self.d.renders.close();self.d.clear_keys();self.tmp.cleanup()
    def new_job(self,title):
        t=self.d.template('sample-mechanism','short-explainer')['template']['video']
        job=self.d.enqueue(dict(account='sample-mechanism',format='short-explainer',title=title,
            brief=t['brief'],content=t['script'],caption=t['caption'],provider='local',model='manual',task='text',template_revision=0))['id']
        return job
    def seed(self,job):
        source=self.d.output(job)/('render-input-'+self.engine+'.json')
        private_directory(source.parent)
        write_json(source,self.d.renders.video_input(self.d.job(job)))
        self.assertEqual(source.parent.stat().st_mode&0o777,0o700);self.assertEqual(source.stat().st_mode&0o777,0o600)
        e=Engine(self.d.workspace/'renders')
        try:
            ident=e.create(source,render_engine=self.engine)['job'];out=e.directory(ident);private_directory(out)
            write_private(out/'render-1080.mp4',b'SYNTHETIC gate bytes; not a decoded video')
            self.assertEqual(out.stat().st_mode&0o777,0o700);self.assertEqual((out/'render-1080.mp4').stat().st_mode&0o777,0o600)
            sha=file_hash(out/'render-1080.mp4')
            write_json(out/'render-engine.json',{'engine':self.engine,'render_sha256':sha,
                'execution_fingerprint':e.payload(ident)['execution']['fingerprint']})
            e.store.set_stage(ident,'render','complete',{name:file_hash(out/name) for name in ['render-1080.mp4','render-engine.json']})
            with self.d.connection() as db:db.execute('INSERT OR REPLACE INTO dashboard_renders VALUES(?,?,?,?,?,?)',(job,self.engine,ident,'complete',None,1))
        finally:e.store.db.close()
        self.engine_job=ident;self.out=out
    def create(self):return self.d.reviews.action(self.job,'review-create',{'engine':self.engine})
    def assert_uncommitted(self):
        self.fake.create.assert_not_called()
        with self.d.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM dashboard_reviews').fetchone()[0],0)
    def test_complete_without_mp4_hash_or_receipt_is_not_qa_authority(self):
        complete=self.d.renders.state(self.job,self.engine)
        for files in [{},{'render-1080.mp4':complete['files']['render-1080.mp4']}]:
            with self.subTest(files=list(files)),patch.object(self.d.renders,'state',return_value={**complete,'files':files}):
                with self.assertRaises(WorkflowError):self.create()
                self.assert_uncommitted()
    def test_changed_bytes_and_wrong_receipt_engine_are_refused(self):
        original=(self.out/'render-1080.mp4').read_bytes()
        (self.out/'render-1080.mp4').write_bytes(original+b'changed')
        with self.assertRaises(WorkflowError):self.create()
        self.assert_uncommitted();(self.out/'render-1080.mp4').write_bytes(original)
        receipt=json.loads((self.out/'render-engine.json').read_text());receipt['engine']='remotion'
        write_json(self.out/'render-engine.json',receipt)
        # Even if a malformed receipt's hash is in the engine manifest, semantic binding fails.
        e=Engine(self.d.workspace/'renders')
        e.store.set_stage(self.engine_job,'render','complete',{n:file_hash(self.out/n) for n in ['render-1080.mp4','render-engine.json']});e.store.db.close()
        with self.assertRaises(WorkflowError):self.create()
        self.assert_uncommitted()
    def test_valid_other_job_receipt_cannot_be_substituted(self):
        first=self.job;other=self.new_job('Different immutable input');self.seed(other)
        with self.d.connection() as db:db.execute('UPDATE dashboard_renders SET engine_job=? WHERE job=? AND engine=?',(self.engine_job,first,self.engine))
        with self.assertRaises(WorkflowError):self.create()
        self.assert_uncommitted()
    def test_valid_binding_is_passed_immutably_and_rechecked_after_capture(self):
        result=self.create();self.assertEqual(result['status'],'incomplete')
        args=self.fake.create.call_args
        self.assertEqual(args.kwargs['expected_render_sha256'],file_hash(self.out/'render-1080.mp4'))
        self.assertEqual(args.kwargs['render_binding']['dashboard_job'],self.job)
        self.assertEqual(args.kwargs['render_binding']['engine_job'],self.engine_job)
        (self.out/'render-engine.json').write_text('{}')
        stale=self.d.reviews.state(self.job,self.engine)
        self.assertEqual(stale['state'],'invalidated');self.assertFalse(stale['current']);self.assertEqual(stale['files'],{})
        with self.assertRaises(WorkflowError):self.d.reviews.download(self.job,self.engine,'report.json')
    def test_capture_time_receipt_replacement_does_not_commit_dashboard_binding(self):
        def swap(*args,**kwargs):
            (self.out/'render-engine.json').write_text('{}')
            return {'review_id':'1'*24}
        self.fake.create.side_effect=swap
        with self.assertRaises(WorkflowError):self.create()
        with self.d.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM dashboard_reviews').fetchone()[0],0)
    def test_input_file_tamper_refused_even_when_engine_receipt_is_valid(self):
        source=self.d.output(self.job)/('render-input-'+self.engine+'.json')
        value=json.loads(source.read_text());value['title']='Changed outside immutable job';write_json(source,value)
        with self.assertRaises(WorkflowError):self.create()
        self.assert_uncommitted()


if __name__=='__main__':unittest.main()
