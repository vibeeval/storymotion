from pack_fixture_case import PackFixtureCase
from test_catalog_integration import session_headers
"""No real media. Stale/cross-job delivery must release zero bytes."""
import copy
import io
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
from storymotion.dashboard import Dashboard
from storymotion.security import WorkflowError,write_json
from audio_fixture import imported,no_media
from audio_flow_fixture import seed_final


class AudioDownloadBindingTests(PackFixtureCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.d=Dashboard(self.tmp.name)
    def tearDown(self):
        self.d.clear_keys()
        if self.d.reviews.service:self.d.reviews.service.db.close()
        self.tmp.cleanup()
    def test_superseding_revision_during_zip_validation_releases_no_bytes(self):
        from storymotion.audio_retime import verify_final_audio
        with no_media():
            parent,child,ident,out,payload=seed_final(self.d,'sample-mechanism','remotion')
            def supersede(*args,**kwargs):
                result=verify_final_audio(*args,**kwargs)
                imported(self.d,parent,rights_note='Explicit newer audio binding during validation')
                return result
            returned=None;error=None
            try:
                with patch('storymotion.audio_retime.verify_final_audio',side_effect=supersede):returned=self.d.renders.download(child,'remotion','delivery.zip')
            except WorkflowError as ex:error=str(ex)
            with self.assertRaises(WorkflowError):self.d.audio.guard(child)
            self.assertIsNotNone(error,'Old implementation released '+str(len(returned or b''))+' stale ZIP bytes')
            self.assertIsNone(returned)
    def test_superseding_revision_during_qa_report_read_releases_no_bytes(self):
        from storymotion.qa_contract import build_sampling_plan,report_template
        with no_media():
            parent,child,ident,out,payload=seed_final(self.d,'sample-flow','hyperframes')
            service=self.d.reviews.runtime()
            def fake_capture(review_id,p,media):
                service._directory(review_id).mkdir(parents=True,exist_ok=True)
                plan=build_sampling_plan(p['brief'],p['render_sha256'],p['asset_hashes'],source_fingerprint=p['source_fingerprint'],scene_keyframes=p['scene_keyframes'])
                service._persist(review_id,p,plan,report_template(plan),{})
            with patch.object(service,'_build',side_effect=fake_capture):self.d.reviews.action(child,'review-create',{'engine':'hyperframes'})
            original=service.file
            def supersede(*args,**kwargs):
                p=original(*args,**kwargs);imported(self.d,parent,rights_note='Explicit newer audio while QA report read');return p
            returned=None;error=None
            try:
                with patch.object(service,'file',side_effect=supersede):returned=self.d.reviews.download(child,'hyperframes','report.json')
            except WorkflowError as ex:error=str(ex)
            with self.assertRaises(WorkflowError):self.d.audio.guard(child)
            self.assertIsNotNone(error,'Old implementation released '+str(len(returned or b''))+' stale QA report bytes')
            self.assertIsNone(returned)
    def test_same_audio_timing_but_other_title_engine_job_releases_no_bytes(self):
        with no_media():
            parent,child_a,ident,out,payload=seed_final(self.d,'sample-mechanism','hyperframes')
            data=copy.deepcopy(self.d.job(parent)['payload']['input']);data['title']='Ayrı başlıklı sentetik iş'
            parent_b=self.d.enqueue(data)['id'];child_b=imported(self.d,parent_b)['child_job'];self.d.prepare(child_b)
            video=self.d.renders.video_input(self.d.job(child_b));write_json(self.d.output(child_b)/'render-input-hyperframes.json',video)
            self.assertEqual(video['audio_timing'],payload['brief']['audio_timing']);self.assertNotEqual(video['title'],payload['brief']['title'])
            with self.d.connection() as db:db.execute('INSERT INTO dashboard_renders VALUES(?,?,?,?,?,?)',(child_b,'hyperframes',ident,'complete',None,1))
            with self.assertRaises(WorkflowError):self.d.reviews.verified_render(child_b,'hyperframes')
            returned=None;error=None
            try:returned=self.d.renders.download(child_b,'hyperframes','delivery.zip')
            except WorkflowError as ex:error=str(ex)
            self.assertIsNotNone(error,'Old implementation released '+str(len(returned or b''))+' bytes from another title/job')
            self.assertIsNone(returned)
    def test_http_recheck_failure_never_writes_stale_delivery_body(self):
        from storymotion.dashboard import Handler
        from storymotion.audio_retime import verify_final_audio
        with no_media():
            parent,child,ident,out,payload=seed_final(self.d,'sample-mechanism','remotion')
            h=Handler.__new__(Handler);h.server=types.SimpleNamespace(dashboard=self.d,server_address=('127.0.0.1',4397));h.path='/render-files/'+child+'/remotion/delivery.zip';h.headers=session_headers(h.server)
            h.wfile=io.BytesIO();sent=[];h.send=lambda code,value:sent.append((code,value))
            def supersede(*args,**kwargs):
                result=verify_final_audio(*args,**kwargs);imported(self.d,parent,rights_note='New binding before HTTP byte release');return result
            with patch('storymotion.audio_retime.verify_final_audio',side_effect=supersede):h.do_GET()
            self.assertEqual(sent[0][0],400);self.assertEqual(h.wfile.getvalue(),b'')
    def test_head_commit_is_serialized_until_authorized_http_write_finishes(self):
        from storymotion.dashboard import Handler
        main=threading.get_ident();attempted=threading.Event();committed=threading.Event();fact={};errors=[]
        real=threading.RLock()
        class TrackedLock:
            def __enter__(inner):
                if threading.get_ident()!=main:
                    acquired=real.acquire(blocking=False);fact['mutation_blocked']=not acquired;attempted.set()
                    if not acquired:real.acquire()
                else:real.acquire()
            def __exit__(inner,*args):real.release()
        with no_media():
            parent,child,ident,out,payload=seed_final(self.d,'sample-mechanism','hyperframes')
            self.d.revision_lock=TrackedLock();threads=[];bodies=[]
            def mutate():
                try:imported(self.d,parent,rights_note='New binding after response is released');committed.set()
                except Exception as ex:errors.append(type(ex).__name__)
            class Sink:
                def write(inner,raw):
                    thread=threading.Thread(target=mutate);threads.append(thread);thread.start()
                    self.assertTrue(attempted.wait(2));self.assertTrue(fact['mutation_blocked']);self.assertFalse(committed.is_set());bodies.append(raw)
            h=Handler.__new__(Handler);h.server=types.SimpleNamespace(dashboard=self.d,server_address=('127.0.0.1',4397));h.path='/render-files/'+child+'/hyperframes/delivery.zip';h.headers=session_headers(h.server)
            h.wfile=Sink();h.send_response=lambda *a:None;h.headers_for=lambda *a:None;h.send_header=lambda *a:None;h.end_headers=lambda:None
            h.do_GET()
            for thread in threads:thread.join(3);self.assertFalse(thread.is_alive())
            self.assertFalse(errors);self.assertTrue(committed.is_set());self.assertEqual(len(bodies),1)
            with self.assertRaises(WorkflowError):self.d.audio.guard(child)
