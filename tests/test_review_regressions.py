from pack_fixture_case import PackFixtureCase
from test_catalog_integration import session_headers
import concurrent.futures
import http.client
import io
import json
import shutil
import tempfile
import threading
import types
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from storymotion.dashboard import Dashboard,Handler
from storymotion.engine import Engine,ROOT
from storymotion.security import WorkflowError,file_hash


class ReviewRegressions(PackFixtureCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.d=Dashboard(self.root/'work')
    def tearDown(self):self.d.clear_keys();self.tmp.cleanup()
    def data(self,video=False):
        a,f=('sample-mechanism','short-explainer') if video else ('sample-flow','video-script');t=self.d.template(a,f)
        return {'account':a,'format':f,'title':'Review fixture','brief':'Review fixture brief','content':t['template']['video']['script'] if video else 'Manual fixture.',
                'caption':'Review fixture caption','provider':'local','model':'manual','task':'text','template_revision':t['revision']}
    def test_format_task_is_bound_not_just_provider_task(self):
        d=self.data();d.update(provider='elevenlabs',model='eleven_v4',task='voice')
        with self.assertRaisesRegex(WorkflowError,'formatına'):self.d.enqueue(d)
    def test_active_expiry_without_status_poll(self):
        d=Dashboard(self.root/'short',key_ttl_seconds=.04)
        d.demo_key({'provider':'openai','value':'FAKE_EXPIRY_TEST'})
        threading.Event().wait(.15)
        self.assertNotIn('openai',d.slots);self.assertFalse(d.expiry_timers);d.clear_keys()
    def test_replaced_slot_not_deleted_by_old_expiry(self):
        self.d.demo_key({'provider':'openai','value':'FAKE_FIRST_TEST'});old=self.d.slots['openai']['until']
        self.d.demo_key({'provider':'openai','value':'FAKE_SECOND_TEST'});self.d._expire_slot('openai',old)
        self.assertIn('openai',self.d.slots);self.assertEqual(len(self.d.expiry_timers),1)
    def test_tampered_download_blocked_before_any_bytes(self):
        j=self.d.enqueue(self.data());self.d.prepare(j['id']);self.d.export(j['id']);(self.d.output(j['id'])/'package.zip').write_bytes(b'tamper')
        h=Handler.__new__(Handler);h.server=types.SimpleNamespace(server_address=('127.0.0.1',4397),dashboard=self.d)
        h.headers=session_headers(h.server);h.path='/files/'+j['id']+'/package.zip';h.wfile=io.BytesIO()
        results=[];h.send=lambda code,payload:results.append((code,payload));h.send_response=lambda code:results.append((code,{}));h.headers_for=lambda *a:None;h.end_headers=lambda:None
        h.do_GET();self.assertEqual(results[0][0],400);self.assertEqual(h.wfile.getvalue(),b'')
    def test_two_instances_export_without_temp_race(self):
        j=self.d.enqueue(self.data());self.d.prepare(j['id'])
        d2=Dashboard(self.root/'work')
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results=list(pool.map(lambda d:d.export(j['id']),[self.d,d2]))
        self.assertEqual(len(results),2);self.assertFalse(list(self.d.output(j['id']).glob('.package-*.tmp')))
        self.assertEqual(file_hash(self.d.output(j['id'])/'package.zip'),self.d.job(j['id'])['manifest']['package.zip'])
    def test_check_and_export_share_lock(self):
        j=self.d.enqueue(self.data());self.d.prepare(j['id']);d2=Dashboard(self.root/'work')
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            calls=[pool.submit(self.d.check,j['id']),pool.submit(d2.export,j['id'])]
            for call in calls:call.result(timeout=5)
        self.assertIn(self.d.job(j['id'])['status'],{'checked','packaged'})
    def test_upgrade_requires_restart_then_new_identity_and_rejects_old_reuse(self):
        data=self.data();first=self.d.enqueue(data);self.d.prepare(first['id'])
        with patch('storymotion.dashboard.execution_provenance',return_value={'fingerprint':'new-code-fixture','files':{}}):
            with self.assertRaisesRegex(WorkflowError,'yeniden başlat'):self.d.enqueue(data)
            restarted=Dashboard(self.root/'work')
            try:
                second=restarted.enqueue(data);self.assertNotEqual(first['id'],second['id'])
                with self.assertRaisesRegex(WorkflowError,'sürümü'):restarted.prepare(first['id'])
            finally:restarted.clear_keys()
    def test_language_and_appearance_change_composition(self):
        data=self.data(True);first=self.d.enqueue(data);self.d.prepare(first['id']);before=(self.d.output(first['id'])/'source/index.html').read_text()
        t=self.d.template('sample-mechanism','short-explainer');t['template']['language']='en';t['template']['appearance']['palette']['background']='#E6E9F2';t['template']['appearance']['title_size']=72
        self.d.save_template({'account':'sample-mechanism','format':'short-explainer',**t})
        data=self.data(True);second=self.d.enqueue(data);self.d.prepare(second['id']);after=(self.d.output(second['id'])/'source/index.html').read_text()
        self.assertNotEqual(before,after);self.assertIn('lang="en"',after);self.assertIn('#E6E9F2',after);self.assertIn('font-size:72px',after)
    def test_planning_fields_are_explicit(self):
        t=self.d.template('sample-mechanism','short-explainer');t['template']['tone']='Planning fixture only'
        result=self.d.save_template({'account':'sample-mechanism','format':'short-explainer',**t})
        self.assertIn('tone',result['planning_only_fields']);self.assertIn('appearance',result['composition_fields'])
        j=self.d.enqueue(self.data(True));self.d.prepare(j['id'])
        self.assertIn('Planning fixture only',(self.d.output(j['id'])/'source/BRIEF.md').read_text())
    def test_bad_appearance_is_not_css_injection(self):
        t=self.d.template('sample-mechanism','short-explainer');t['template']['appearance']['palette']['background']='red;script:bad'
        with self.assertRaises(WorkflowError):self.d.save_template({'account':'sample-mechanism','format':'short-explainer',**t})
    def test_approved_audio_relocation_keeps_preparation_working(self):
        first=self.root/'input1';second=self.root/'input2';first.mkdir();second.mkdir()
        audio=first/'approved.wav'
        with wave.open(str(audio),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*64000)
        brief=json.loads((ROOT/'tests/fixtures/examples/sample-mechanism.json').read_text());brief.update(alignment='imported_timing',audio={'file':'approved.wav','sha256':file_hash(audio),'approved_by':'synthetic test only','rights_note':'generated silence, no voice'})
        (first/'brief.json').write_text(json.dumps(brief));e=Engine(self.root/'audio-work');j=e.create(first/'brief.json')['job']
        shutil.move(str(first/'approved.wav'),second/'approved.wav');shutil.move(str(first/'brief.json'),second/'brief.json');first.rmdir()
        self.assertEqual(e.create(second/'brief.json')['job'],j);e.run(j,'prepare')
        self.assertEqual(file_hash(e.directory(j)/'assets/narration.wav'),brief['audio']['sha256'])


if __name__=='__main__':unittest.main()
