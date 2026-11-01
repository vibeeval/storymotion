from pack_fixture_case import PackFixtureCase
from test_catalog_integration import session_headers
import copy
import io
import json
import tempfile
import types
import unittest
from unittest.mock import patch
from storymotion.dashboard import Dashboard,Handler
from storymotion.security import WorkflowError
from audio_fixture import alignment,source_job,imported,no_media


class CompletedVoiceBridgeTests(PackFixtureCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.d=Dashboard(self.tmp.name,elevenlabs_mode='demo');self.s=self.d.eleven
    def tearDown(self):self.d.clear_keys();self.tmp.cleanup()
    def voice(self,parent,phonetic=False):
        ref=self.s.connect('FAKE_AUDIO_BIND_CONTRACT_ONLY')['connection'];script=self.d.job(parent)['payload']['input']['content'];tts=script+' değişik' if phonetic else script
        r=self.s.preview(ref,parent,script,tts,'demo-voice','demo-model')['request'];self.s.approve(ref,r,script,len(tts),True,True)
        original=self.s.client.request
        def response(*args,**kwargs):
            data,rid=original(*args,**kwargs)
            if args[0]=='POST':data['alignment']=alignment(tts,20);data['normalized_alignment']=copy.deepcopy(data['alignment'])
            return data,rid
        # Invented provider envelope, mock measured duration/decode: no acoustic claim.
        with patch.object(self.s.client,'request',response),no_media():self.assertEqual(self.s.execute(ref,r,script,False)['status'],'completed')
        return r
    def body(self,r):return dict(request=r,approved_by='Synthetic contract operator',rights_note='Original synthetic envelope; not speech acceptance',rights_confirmed=True,scene_word_spans=None,viseme_required=False)
    def test_completed_voice_endpoint_creates_child_without_second_provider_or_render_call(self):
        parent=source_job(self.d);r=self.voice(parent);before=len(self.s.client.calls)
        h=Handler.__new__(Handler);h.server=types.SimpleNamespace(dashboard=self.d,server_address=('127.0.0.1',4397));h.path='/api/jobs/'+parent+'/audio-bind'
        data=json.dumps(self.body(r)).encode();h.headers=session_headers(h.server,write=True)
        h.headers['Content-Length']=str(len(data));h.headers['Content-Type']='application/json';h.rfile=io.BytesIO(data)
        results=[];h.send=lambda code,value:results.append((code,value))
        with no_media():h._post()
        self.assertEqual(results[0][0],200);result=results[0][1];self.assertNotEqual(result['child_job'],parent)
        self.assertFalse(result['render_started']);self.assertEqual(len(self.s.client.calls),before)
        self.assertEqual(result['job']['payload']['audio_revision']['voice_request'],r)
    def test_wrong_job_phonetic_text_extra_path_and_unconfirmed_rights_are_rejected(self):
        parent=source_job(self.d);r=self.voice(parent);other=source_job(self.d,'sample-flow')
        with no_media():
            with self.assertRaises(WorkflowError):self.d.audio.bind_voice(other,self.body(r))
            for change in [dict(file='/etc/passwd'),dict(rights_confirmed=False),dict(viseme_required=True)]:
                data=self.body(r);data.update(change)
                with self.assertRaises(WorkflowError):self.d.audio.bind_voice(parent,data)
        self.assertEqual(len(self.d.jobs()),2)
        phonetic=self.voice(other,True)
        with self.assertRaisesRegex(WorkflowError,'Phonetic'):self.d.audio.bind_voice(other,self.body(phonetic))
    def test_uncertain_result_cannot_be_bypassed_with_local_audio_import(self):
        parent=source_job(self.d);r=self.voice(parent)
        with self.s.db() as db:db.execute("UPDATE voice_requests SET status='uncertain',artifact=NULL WHERE id=?",(r,))
        with no_media(),self.assertRaisesRegex(WorkflowError,'uncertain'):imported(self.d,parent)
        self.assertEqual(len(self.d.jobs()),1)
    def test_new_voice_result_invalidates_previously_bound_child(self):
        parent=source_job(self.d)
        with no_media():child=imported(self.d,parent)['child_job']
        self.voice(parent)
        with self.assertRaisesRegex(WorkflowError,'voice binding changed'):self.d.audio.guard(child)
