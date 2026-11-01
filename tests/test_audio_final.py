from pack_fixture_case import PackFixtureCase
from test_catalog_integration import session_headers
import copy
import io
import json
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from storymotion.dashboard import Dashboard,Handler
from storymotion.security import WorkflowError,digest,file_hash,write_json
from storymotion.qa_contract import build_sampling_plan,report_template
from audio_fixture import ACCOUNTS,no_media
from audio_flow_fixture import seed_final


class AudioFinalBindingTests(PackFixtureCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.d=Dashboard(self.tmp.name)
    def tearDown(self):
        self.d.clear_keys()
        if self.d.reviews.service:self.d.reviews.service.db.close()
        self.tmp.cleanup()
    def fake_capture(self,ident,payload,media):
        service=self.d.reviews.runtime();service._directory(ident).mkdir(parents=True,exist_ok=True)
        plan=build_sampling_plan(payload['brief'],payload['render_sha256'],payload['asset_hashes'],
            source_fingerprint=payload['source_fingerprint'],scene_keyframes=payload['scene_keyframes'])
        service._persist(ident,payload,plan,report_template(plan),{})
    def test_eight_synthetic_final_deliveries_bind_audio_timing_mp4_mobile_and_incomplete_qa(self):
        with no_media():
            for account in ACCOUNTS:
                for engine in ['hyperframes','remotion']:
                    parent,child,ident,out,payload=seed_final(self.d,account,engine)
                    data=self.d.renders.download(child,engine,'delivery.zip')
                    with zipfile.ZipFile(io.BytesIO(data)) as z:
                        m=json.loads(z.read('delivery.json'));self.assertFalse(m['publication_ready'])
                        self.assertEqual(m['audio_timing_sha256'],digest(payload['brief']['audio_timing']))
                        self.assertEqual(m['main_render_sha256'],file_hash(out/'render-1080.mp4'))
                        self.assertEqual(m['mobile_render_sha256'],file_hash(out/'render-mobile.mp4'))
                        self.assertIn('assets/narration.wav',m['files']);self.assertIn('subtitles.srt',m['files']);self.assertIn('audio-timing.json',m['files'])
                    binding,verified,_=self.d.reviews.verified_render(child,engine)
                    self.assertEqual(binding['engine_job'],ident);self.assertEqual(verified['audio_sha256'],payload['audio_sha256'])
                    with patch.object(self.d.reviews.runtime(),'_build',side_effect=self.fake_capture):
                        review=self.d.reviews.action(child,'review-create',{'engine':engine})
                    self.assertEqual(review['status'],'incomplete');self.assertIsNone(review['approval_fingerprint']);self.assertEqual(review['coverage']['captured'],0)
    def test_tampered_mobile_timing_qa_and_zip_are_refused_on_download(self):
        for name in ['render-mobile.mp4','audio-timing.json','qa.json','delivery.zip']:
            with self.subTest(name=name),no_media():
                parent,child,ident,out,payload=seed_final(self.d,'sample-mechanism','hyperframes')
                original=(out/name).read_bytes();(out/name).write_bytes(b'changed')
                with self.assertRaises(WorkflowError):self.d.renders.download(child,'hyperframes','delivery.zip')
                (out/name).write_bytes(original)
    def test_missing_or_wrong_audio_receipt_binding_never_creates_qa(self):
        with no_media():
            parent,child,ident,out,payload=seed_final(self.d,'sample-flow','remotion')
            receipt=json.loads((out/'render-engine.json').read_text());receipt['audio_timing_sha256']='f'*64;write_json(out/'render-engine.json',receipt)
            from storymotion.engine import Engine
            e=Engine(self.d.workspace/'renders');e.store.set_stage(ident,'render','complete',{n:file_hash(out/n) for n in ['render-1080.mp4','render-engine.json']});e.store.db.close()
            with self.assertRaises(WorkflowError):self.d.reviews.action(child,'review-create',{'engine':'remotion'})
            with self.d.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM dashboard_reviews WHERE job=?',(child,)).fetchone()[0],0)
    def test_old_source_subtitle_http_download_is_blocked_after_audio_revision(self):
        from audio_fixture import source_job,imported
        with no_media():
            parent=source_job(self.d);self.d.prepare(parent);imported(self.d,parent)
            h=Handler.__new__(Handler);h.server=types.SimpleNamespace(dashboard=self.d,server_address=('127.0.0.1',4397));h.path='/files/'+parent+'/subtitles.srt';h.headers=session_headers(h.server)
            results=[];h.send=lambda code,value:results.append((code,value));h.do_GET()
            self.assertEqual(results[0][0],400);self.assertIn('FRESH_TIMING',results[0][1]['error'])
    def test_even_consistently_rehashed_zip_cannot_omit_required_audio(self):
        with no_media():
            parent,child,ident,out,payload=seed_final(self.d,'sample-mechanism','remotion')
            m=json.loads((out/'delivery.json').read_text());m['files'].pop('assets/narration.wav');write_json(out/'delivery.json',m)
            with zipfile.ZipFile(out/'delivery.zip','w') as z:
                for name in [*m['files'],'delivery.json']:z.write(out/name,name)
            from storymotion.engine import Engine
            e=Engine(self.d.workspace/'renders');e.store.set_stage(ident,'delivery','complete',{n:file_hash(out/n) for n in ['delivery.json','delivery.zip']});e.store.db.close()
            with self.assertRaisesRegex(WorkflowError,'manifest binding'):self.d.renders.download(child,'remotion','delivery.zip')
