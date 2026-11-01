from pack_fixture_case import PackFixtureCase
import json,shutil,unittest
from pathlib import Path
import test_llm_ui as ui
SOURCE=(Path(__file__).resolve().parents[1]/'dashboard/local-raster.js').read_text()
SETUP=r'''
ready();context.j={id:'c'.repeat(24),payload:{account:{id:'sample-mechanism'},format:{adapter:'account-pack'},template:{template:{video:{scenes:[{id:'beat-1',heading:'Test',camera:'locked'}]}}}}};run('state.job=j');run(RASTER_SOURCE);run('rasterJobChanged(j)');
const file={name:'owned.png',size:120,arrayBuffer:async()=>new Uint8Array(120).buffer};$('raster-file').files=[file];$('raster-approved-by').value='Owner';$('raster-rights-note').value='Original neutral fixture';$('raster-rights').checked=true;context.crypto={subtle:{digest:async()=>new Uint8Array(32).buffer}};context.btoa=s=>Buffer.from(s,'binary').toString('base64');run('rasterControls()');
'''.replace('RASTER_SOURCE',json.dumps(SOURCE))
@unittest.skipUnless(shutil.which('node'),'Node required')
class RasterUI(PackFixtureCase):
 def dom(self,body):ui.WriterUi().dom(SETUP+body)
 def test_file_and_view_selection_never_auto_upload_or_render_and_rights_required(self):
  self.dom(r'''let calls=0;context.mockApi=async()=>{calls++;};run('api=mockApi');$('raster-file').listeners.change[0]();assert.equal(calls,0);assert.equal($('raster-rights').checked,false);await $('raster-form').listeners.submit[0]({preventDefault(){}});assert.equal(calls,0);$('raster-camera').value='push-in';$('raster-camera').listeners.change[0]();assert.equal(calls,0);''')
 def test_success_remains_on_source_and_requires_explicit_open(self):
  self.dom(r'''const calls=[];let selected=null;context.sel=async id=>selected=id;context.mockApi=async(path,data)=>{calls.push({path,data});return {child_job:'d'.repeat(24),parent_job:jobId,publication_ready:false};};run('api=mockApi;selectJob=sel;refreshJobs=async()=>{}');await $('raster-form').listeners.submit[0]({preventDefault(){}});assert.equal(calls.length,1);assert.equal(calls[0].data.container,'png');assert.equal(calls[0].data.expected_source_sha256,'0'.repeat(64));assert.equal(selected,null);assert.equal(run('state.job.id'),jobId);assert.equal($('raster-open').hidden,false);$('raster-open').listeners.click[0]();assert.equal(selected,'d'.repeat(24));''')
 def test_changed_selection_during_read_sends_nothing_and_preserves_draft(self):
  self.dom(r'''let resolve;file.arrayBuffer=()=>new Promise(r=>resolve=r);let calls=0;context.mockApi=async()=>calls++;run('api=mockApi');const pending=$('raster-form').listeners.submit[0]({preventDefault(){}});await settle();run('state.jobEpoch++;state.job={...j,id:"e".repeat(24)};rasterJobChanged(state.job)');$('raster-rights-note').value='New draft';resolve(new Uint8Array(120).buffer);await pending;assert.equal(calls,0);assert.equal($('raster-rights-note').value,'New draft');assert.equal(run('state.job.id'),'e'.repeat(24));''')
 def test_late_response_does_not_open_or_clobber_another_job(self):
  self.dom(r'''let resolve;context.mockApi=()=>new Promise(r=>resolve=r);run('api=mockApi');const pending=$('raster-form').listeners.submit[0]({preventDefault(){}});await settle();run('state.jobEpoch++;state.job={...j,id:"e".repeat(24)};rasterJobChanged(state.job)');$('raster-label').value='Dirty next draft';resolve({child_job:'d'.repeat(24),parent_job:jobId,publication_ready:false});await pending;assert.equal($('raster-open').hidden,true);assert.equal($('raster-label').value,'Dirty next draft');assert.equal(run('state.job.id'),'e'.repeat(24));''')
 def test_no_event_crop_or_consent_changes_prevent_dispatch(self):
  for field,value in [('raster-crop-width','0.5'),('raster-camera','push-in'),('raster-rights',False)]:
   with self.subTest(field=field):self.dom(r'''let resolve;file.arrayBuffer=()=>new Promise(r=>resolve=r);let calls=0;context.mockApi=async()=>calls++;run('api=mockApi');const pending=$('raster-form').listeners.submit[0]({preventDefault(){}});await settle();$('FIELD').PROP=VALUE;resolve(new Uint8Array(120).buffer);await pending;assert.equal(calls,0);'''.replace('FIELD',field).replace('PROP','checked' if field=='raster-rights' else 'value').replace('VALUE',json.dumps(value)))
 def test_view_change_while_waiting_keeps_new_form_and_hides_old_child(self):
  self.dom(r'''let resolve;context.mockApi=()=>new Promise(r=>resolve=r);run('api=mockApi');const pending=$('raster-form').listeners.submit[0]({preventDefault(){}});await settle();$('raster-label').value='New unsaved label';$('raster-label').listeners.input[0]();resolve({child_job:'d'.repeat(24),parent_job:jobId,publication_ready:false});await pending;assert.equal($('raster-label').value,'New unsaved label');assert.equal($('raster-open').hidden,true);assert.equal($('raster-rights').checked,false);''')
