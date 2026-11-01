from pack_fixture_case import PackFixtureCase
import json,shutil,unittest
from pathlib import Path
import test_llm_ui as ui
SOURCE=(Path(__file__).resolve().parents[1]/'dashboard/local-audio.js').read_text()
SETUP=r'''
ready();context.j={id:'c'.repeat(24),payload:{format:{adapter:'account-pack'}}};run('state.job=j');run(LOCAL_SOURCE);run('localAudioJobChanged(j)');
const file={name:'owned.wav',size:120,arrayBuffer:async()=>new Uint8Array(120).buffer},alignment={size:200,text:async()=>'{}'};$('local-audio-file').files=[file];$('local-audio-alignment').files=[alignment];$('local-audio-approved-by').value='Owner';$('local-audio-rights-note').value='Private test permission';$('local-audio-rights').checked=true;
context.crypto={subtle:{digest:async()=>new Uint8Array(32).buffer}};context.btoa=s=>Buffer.from(s,'binary').toString('base64');run('localAudioControls()');
'''.replace('LOCAL_SOURCE',json.dumps(SOURCE))

@unittest.skipUnless(shutil.which('node'),'Node required')
class LocalAudioUI(PackFixtureCase):
 def dom(self,body):ui.WriterUi().dom(SETUP+body)
 def test_file_selection_never_calls_api_and_rights_are_required(self):
  self.dom(r'''
  const calls=[];context.mockApi=async(...x)=>{calls.push(x);return {}};run('api=mockApi');assert.equal(calls.length,0);$('local-audio-rights').checked=false;await $('local-audio-form').listeners.submit[0]({preventDefault(){}});assert.equal(calls.length,0);assert.match($('local-audio-status').textContent,/onayı/);$('local-audio-rights').checked=true;$('local-audio-file').listeners.change[0]();assert.equal($('local-audio-rights').checked,false);assert.equal(calls.length,0);
  ''')
 def test_job_change_during_file_read_prevents_upload_and_does_not_erase_new_draft(self):
  self.dom(r'''
  let resolve;file.arrayBuffer=()=>new Promise(r=>resolve=r);let calls=0;context.mockApi=async()=>{calls++;};run('api=mockApi');const pending=$('local-audio-form').listeners.submit[0]({preventDefault(){}});await settle();run('state.jobEpoch++;state.job={id:"d".repeat(24),payload:{format:{adapter:"account-pack"}}};localAudioJobChanged(state.job)');$('local-audio-rights-note').value='New draft';resolve(new Uint8Array(120).buffer);await pending;assert.equal(calls,0);assert.equal($('local-audio-rights-note').value,'New draft');assert.equal(run('state.job.id'),'d'.repeat(24));
  ''')
 def test_consent_or_exact_file_changed_without_event_stops_before_upload(self):
  self.dom(r'''
  let resolve;alignment.text=()=>new Promise(r=>resolve=r);let calls=0;context.mockApi=async()=>{calls++;};run('api=mockApi');const pending=$('local-audio-form').listeners.submit[0]({preventDefault(){}});await settle();$('local-audio-rights').checked=false;resolve('{}');await pending;assert.equal(calls,0);
  ''')
 def test_success_upload_is_explicit_bound_and_navigates_through_select_job(self):
  self.dom(r'''
  const calls=[];let selected=null;context.select=async id=>{selected=id;};context.mockApi=async(path,data)=>{calls.push({path,data});return {child_job:'d'.repeat(24),parent_job:jobId,job:{id:'d'.repeat(24)},publication_ready:false};};run('api=mockApi;selectJob=select;refreshJobs=async()=>{}');await $('local-audio-form').listeners.submit[0]({preventDefault(){}});assert.equal(calls.length,1);assert.equal(calls[0].path,'/api/jobs/'+jobId+'/audio-import');assert.equal(calls[0].data.expected_audio_sha256,'0'.repeat(64));assert.equal(calls[0].data.container,'wav');assert.equal(calls[0].data.viseme_required,false);assert.equal(selected,'d'.repeat(24));assert.equal(run('state.job.id'),jobId);assert.ok(!JSON.stringify(calls).includes('api_key'));
  ''')
 def test_late_upload_response_cannot_select_child_after_user_changes_selection(self):
  self.dom(r'''
  let resolve,selected=null;context.select=async id=>{selected=id;};context.mockApi=()=>new Promise(r=>resolve=r);run('api=mockApi;selectJob=select');const pending=$('local-audio-form').listeners.submit[0]({preventDefault(){}});await settle();run('state.jobEpoch++;state.job={id:"e".repeat(24),payload:{format:{adapter:"account-pack"}}};localAudioJobChanged(state.job)');resolve({child_job:'d'.repeat(24),parent_job:jobId,job:{id:'d'.repeat(24)},publication_ready:false});await pending;assert.equal(selected,null);assert.equal(run('state.job.id'),'e'.repeat(24));
  ''')
