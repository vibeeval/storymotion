from pack_fixture_case import PackFixtureCase
import base64,copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from storymotion.dashboard import Dashboard
from storymotion.engine import ROOT
from storymotion.security import WorkflowError,file_hash
from storymotion.audio_retime import measured_words,script_sha,validate_timed_brief
from storymotion.local_audio import import_local,MAX_AUDIO
from audio_fixture import source_job,no_media

def fixture_alignment(script,audio_sha,duration=20):
 tokens=script.split();step=(duration-.2)/len(tokens)
 return {'schema_version':1,'kind':'word_timing','script_sha256':script_sha(script),'audio_sha256':audio_sha,'method':'SYNTHETIC unit word anchors;not acoustic speech','source_alignment_sha256':'a'*64,'limitations':'Synthetic offline regression;human acceptance pending','words':[{'index':i,'text':text,'start':.1+i*step,'end':.1+(i+.9)*step} for i,text in enumerate(tokens)]}

class LocalAudio(PackFixtureCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.d=Dashboard(self.tmp.name);self.parent=source_job(self.d);self.script=self.d.job(self.parent)['payload']['input']['content'];self.audio=ROOT/'fixtures/audio-retime/synthetic-20s.wav';self.sha=file_hash(self.audio);self.alignment=fixture_alignment(self.script,self.sha)
 def tearDown(self):self.d.clear_keys();self.tmp.cleanup()
 def data(self):return {'audio_base64':base64.b64encode(self.audio.read_bytes()).decode(),'container':'wav','expected_audio_sha256':self.sha,'alignment':copy.deepcopy(self.alignment),'approved_by':'Synthetic test operator','rights_note':'Original synthetic silence;not private speech','rights_confirmed':True,'scene_word_spans':None,'viseme_required':False}
 def assert_empty(self):
  self.assertEqual(len(self.d.jobs()),1);self.assertFalse(list(self.d.workspace.glob('local-audio-*')))
  with self.d.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM dashboard_audio_revisions').fetchone()[0],0)
 def test_word_anchors_preserve_punctuation_exact_times_and_no_character_interpolation(self):
  got=measured_words(self.script,self.alignment,20,self.sha);self.assertEqual(got,self.alignment['words'])
  with no_media():result=import_local(self.d,self.parent,self.data())
  timing=result['job']['payload']['template']['template']['video']['audio_timing'];self.assertEqual(timing['words'],got);self.assertEqual(timing['alignment_provenance']['character_timing'],'not_available; no interpolation performed');self.assertFalse(result['publication_ready']);self.assertEqual(result['provider_calls'],0);self.assertFalse(result['render_started']);self.assertFalse(list(self.d.workspace.glob('local-audio-*')))
  validate_timed_brief({k:v for k,v in result['job']['payload']['template']['template']['video'].items() if k not in ('appearance','production_notes','brand_identity')})
 def test_word_schema_hash_spelling_nonfinite_duration_and_overlap_fail_without_child(self):
  changes=[lambda a:a.update(script_sha256='b'*64),lambda a:a.update(audio_sha256='b'*64),lambda a:a['words'][0].update(text='Changed.'),lambda a:a['words'][0].update(end=20.01),lambda a:a['words'][0].update(start=float('nan')),lambda a:a['words'][1].update(start=0),lambda a:a['words'][0].update(index=True),lambda a:a.update(extra='unsupported')]
  for change in changes:
   value=self.data();change(value['alignment'])
   with self.subTest(change=change),no_media(),self.assertRaises((WorkflowError,ValueError)):import_local(self.d,self.parent,value)
   self.assert_empty()
 def test_invalid_approval_hash_base64_container_paths_and_body_are_rejected_before_tools(self):
  invalid=[{'rights_confirmed':False},{'viseme_required':True},{'expected_audio_sha256':'b'*64},{'audio_base64':'https://example.invalid/audio'},{'audio_base64':'?'*140},{'container':'../../mp3'},{'approved_by':''},{'path':'/private/local.wav'}]
  with patch('storymotion.engine.probe') as probe:
   for changes in invalid:
    value=self.data();value.update(changes)
    with self.subTest(changes=list(changes)),self.assertRaises(WorkflowError):import_local(self.d,self.parent,value)
    self.assert_empty()
   probe.assert_not_called()
 def test_decode_failure_leaves_no_temporary_audio_or_immutable_child(self):
  with patch('storymotion.engine.probe',side_effect=WorkflowError('Known decode failure')),self.assertRaises(WorkflowError):import_local(self.d,self.parent,self.data())
  self.assert_empty()
 def test_repeat_same_approved_upload_reuses_exact_child_and_old_parent_is_invalidated(self):
  with no_media():first=import_local(self.d,self.parent,self.data());second=import_local(self.d,self.parent,self.data())
  self.assertEqual(first['child_job'],second['child_job']);self.assertEqual(len(self.d.jobs()),2);self.d.audio.guard(first['child_job'])
  with self.assertRaisesRegex(WorkflowError,'NEW_AUDIO'):self.d.audio.guard(self.parent)
 def test_size_limit_rejected_before_decode(self):
  value=self.data();value['audio_base64']='A'*(4*((MAX_AUDIO+2)//3)+4)
  with patch('base64.b64decode') as decode,self.assertRaises(WorkflowError):import_local(self.d,self.parent,value)
  decode.assert_not_called();self.assert_empty()
