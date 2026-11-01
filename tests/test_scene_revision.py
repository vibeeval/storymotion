from pack_fixture_case import PackFixtureCase
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from storymotion.dashboard import Dashboard
from storymotion.engine import Engine,ROOT
from storymotion.security import WorkflowError,digest,write_json,file_hash
from audio_fixture import source_job,imported,no_media


class SceneRevisionTests(PackFixtureCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.d=Dashboard(self.tmp.name)
 def tearDown(self):self.d.clear_keys();self.tmp.cleanup()
 def body(self,job,prop='camera',value='locked'):
  plan=self.d.renders.edit_plan(job,'hyperframes')['edit_plan'];scene=plan['scenes'][0]
  return {'engine':'hyperframes','expected_plan_sha256':plan['plan_sha256'],'scene_id':scene['id'],'property':prop,'value':value}
 def test_explicit_visual_change_is_immutable_idempotent_and_isolated_to_scene(self):
  for account in ('sample-flow','sample-mechanism','sample-reflection','sample-series'):
   parent=source_job(self.d,account);original=self.d.job(parent);video=self.d.renders.video_input(original);body=self.body(parent,'heading','Aynı nesneye yakından bakalım.');result=self.d.edits.create(parent,body);child=result['child_job']
   self.assertEqual(self.d.edits.create(parent,body)['child_job'],child);self.assertEqual(self.d.job(parent)['payload'],original['payload']);new=self.d.renders.video_input(self.d.job(child))
   self.assertNotEqual(child,parent);self.assertEqual(new['script'],video['script']);self.assertEqual(new['cues'],video['cues']);self.assertEqual(new['scenes'][1:],video['scenes'][1:]);self.assertEqual(new['scenes'][0]['heading'],body['value']);self.assertIsNone(self.d.renders.row(child,'hyperframes'));self.assertEqual(self.d.reviews.state(child,'hyperframes')['status'],'not_started');self.assertFalse(result['render_started'])
 def test_invalid_requests_and_stale_plan_have_no_child_or_output_writes(self):
  parent=source_job(self.d);body=self.body(parent);initial=[j['id'] for j in self.d.jobs()];files=list(self.d.workspace.rglob('revision.json'))
  for change in ({'expected_plan_sha256':'a'*64},{'property':'script'},{'property':'duration'},{'scene_id':'other'},{'property':'heading','value':'<script>no</script>'},{'property':'heading','value':'Fiyatı 99 USD'},{'unexpected':'no'}):
   with self.subTest(change=change),self.assertRaises(WorkflowError):self.d.edits.create(parent,{**body,**change})
   self.assertEqual([j['id'] for j in self.d.jobs()],initial);self.assertEqual(list(self.d.workspace.rglob('revision.json')),files)
 def test_tampered_child_or_parent_binding_is_rejected(self):
  parent=source_job(self.d);child=self.d.edits.create(parent,self.body(parent))['child_job'];out=self.d.output(child);before=(out/'revision.json').read_bytes();(out/'revision.json').write_text('{}')
  with self.assertRaises(WorkflowError):self.d.renders.edit_plan(child,'remotion')
  with self.assertRaises(WorkflowError):self.d.edits.create(parent,self.body(parent))
  self.assertEqual((out/'revision.json').read_text(),'{}');(out/'revision.json').write_bytes(before)
  row=self.d.job(child);payload=row['payload'];payload['template']['template']['video']['scenes'][1]['heading']='Unexpected outside edit'
  with self.d.connection() as db:db.execute('UPDATE dashboard_jobs SET payload=? WHERE id=?',(json.dumps(payload),child))
  with self.assertRaises(WorkflowError):self.d.audio.guard(child)
 def test_revision_chain_and_open_previous_revision_do_not_transfer_review(self):
  parent=source_job(self.d);a=self.d.edits.create(parent,self.body(parent))['child_job'];b=self.d.edits.create(a,self.body(a,'heading','Yalnız bu sahne değişti.'))['child_job'];self.d.audio.guard(a);self.d.audio.guard(b);self.assertEqual(self.d.job(b)['payload']['edit_revision']['depth'],2)
  self.assertEqual(self.d.reviews.state(a,'remotion')['status'],'not_started');self.assertEqual(self.d.reviews.state(b,'remotion')['status'],'not_started')
 def test_audio_bytes_and_word_cues_are_preserved_but_scene_timing_binding_refreshes(self):
  with no_media():
   parent=source_job(self.d);audio=imported(self.d,parent)['child_job'];before=self.d.renders.video_input(self.d.job(audio));child=self.d.edits.create(audio,self.body(audio))['child_job'];new=self.d.renders.video_input(self.d.job(child))
   self.assertEqual(before['audio'],new['audio']);self.assertEqual(before['cues'],new['cues']);self.assertEqual(before['audio_timing']['words'],new['audio_timing']['words']);self.assertEqual(before['production_context'] if 'production_context' in before else None,new.get('production_context'));self.assertNotEqual(digest(before['audio_timing']),digest(new['audio_timing']));self.assertEqual(new['audio_timing']['scene_sha256'],digest(new['scenes']))
   self.assertEqual(file_hash(self.d.output(audio)/before['audio']['file']),file_hash(self.d.output(child)/new['audio']['file']))
   for engine in ('hyperframes','remotion'):
    path=self.d.output(child)/('test-'+engine+'.json');write_json(path,new);e=Engine(self.d.workspace/('engine-'+engine))
    try:
     job=e.create(path,render_engine=engine)['job'];e.run(job,'prepare');out=e.directory(job);self.assertEqual(json.loads((out/'revision.json').read_text()),new['revision_context']);self.assertEqual(json.loads((out/'edit-plan.json').read_text())['audio_timing_sha256'],digest(new['audio_timing']))
    finally:e.store.db.close()
   with self.assertRaises(WorkflowError):self.d.audio.base(child)
 def test_new_audio_on_root_invalidates_dependent_visual_revision(self):
  with no_media():
   parent=source_job(self.d);child=self.d.edits.create(parent,self.body(parent))['child_job'];imported(self.d,parent)
   with self.assertRaises(WorkflowError):self.d.audio.guard(child)
 def test_official_http_revision_action_has_origin_and_body_guards(self):
  import test_writing_context_http as http
  h=http.ContextHttpTests();h.setUp()
  try:
   job=source_job(h.d);p=h.d.renders.edit_plan(job,'remotion')['edit_plan'];body={'engine':'remotion','expected_plan_sha256':p['plan_sha256'],'scene_id':p['scenes'][0]['id'],'property':'heading','value':'Yerel bir sahne değişikliği.'};path='/api/jobs/'+job+'/scene-revise'
   h.call(path,body,403,origin='https://attacker.test');h.call(path,{**body,'property':'voice'},400);r=h.call(path,body);self.assertFalse(r['render_started']);self.assertFalse(h.d.llm.transport.calls)
  finally:h.tearDown()

 @unittest.skipUnless(__import__('shutil').which('node'),'Node required for UI contract')
 def test_ui_requires_ack_and_preserves_new_draft_while_response_is_pending(self):
  import test_llm_ui as ui
  ui.WriterUi().dom(r'''
  ready();run('tab("qa")');context.j={id:'c'.repeat(24),payload:{format:{adapter:'account-pack'}}};context.p={plan_sha256:'a'.repeat(64),scenes:[{id:'beat-1',start:0,end:4,heading:'Önce',camera:'locked'}]};run('state.job=j;sceneEditPlan(j.id,p)');
  let release;const calls=[];context.mockApi=(path,body)=>{calls.push({path,body});return new Promise(resolve=>{release=resolve;});};run('api=mockApi;refreshJobs=async()=>{}');
  $('scene-edit-heading').value='Gönderilen başlık';$('scene-edit-heading').listeners.input[0]();assert.equal(calls.length,0);assert.equal($('scene-edit-create').disabled,true);
  $('scene-edit-ack').checked=true;$('scene-edit-ack').listeners.change[0]();$('scene-edit-form').listeners.submit[0]({preventDefault(){}});await settle();assert.equal(calls.length,1);assert.equal(calls[0].body.expected_plan_sha256,'a'.repeat(64));assert.equal(calls[0].body.property,'heading');
  $('scene-edit-heading').value='Beklerken yazılan yeni metin';$('scene-edit-heading').listeners.input[0]();release({child_job:'d'.repeat(24),revision:{property:'heading',after:'Gönderilen başlık'}});await settle();await settle();
  assert.equal($('scene-edit-heading').value,'Beklerken yazılan yeni metin');assert.equal(run('state.job.id'),'c'.repeat(24));assert.equal($('scene-edit-open').hidden,false);assert.match($('scene-edit-status').textContent,/Gönderilen başlık/);assert.equal($('scene-edit-ack').checked,false);
  ''')
 @unittest.skipUnless(__import__('shutil').which('node'),'Node required for UI contract')
 def test_ui_job_change_ignores_old_revision_response_and_voice_preview_is_disabled(self):
  import test_llm_ui as ui
  ui.WriterUi().dom(r'''
  ready();context.j={id:'c'.repeat(24),payload:{format:{adapter:'account-pack'}}};context.p={plan_sha256:'a'.repeat(64),scenes:[{id:'beat-1',start:0,end:4,heading:'Önce',camera:'locked'}]};run('state.job=j;sceneEditPlan(j.id,p)');let release;context.mockApi=()=>new Promise(resolve=>{release=resolve;});run('api=mockApi;refreshJobs=async()=>{}');
  $('scene-edit-heading').value='Yeni';$('scene-edit-ack').checked=true;$('scene-edit-form').listeners.submit[0]({preventDefault(){}});await settle();run('state.job=null;sceneEditChanged(null)');release({child_job:'d'.repeat(24),revision:{property:'heading',after:'Yeni'}});await settle();await settle();assert.equal($('scene-edit-open').hidden,true);assert.equal($('scene-edit-panel').hidden,true);
  context.overlay={payload:{edit_revision:{parent_job:'e'.repeat(24)}}};assert.equal(run('voiceViewState("demo","f".repeat(32),null,overlay).canPreview'),false);
  ''')

 def test_audio_visual_child_cannot_download_another_childs_engine_output(self):
  from audio_flow_fixture import seed_final
  with no_media():
   root=source_job(self.d);audio=imported(self.d,root)['child_job'];a=self.d.edits.create(audio,self.body(audio,'heading','Özgün bir sahne başlığı.'))['child_job'];b=self.d.edits.create(audio,self.body(audio,'heading','Başka bir sahne başlığı.'))['child_job']
   for engine in ('hyperframes','remotion'):
    ids=[]
    for child in (a,b):
     with patch('audio_flow_fixture.source_job',return_value=root),patch('audio_flow_fixture.imported',return_value={'child_job':child}):_,_,ident,out,payload=seed_final(self.d,'sample-mechanism',engine)
     ids.append(ident);self.assertTrue(self.d.renders.download(child,engine,'delivery.zip'))
    with self.d.connection() as db:db.execute('UPDATE dashboard_renders SET engine_job=? WHERE job=? AND engine=?',(ids[1],a,engine))
    with self.assertRaises(WorkflowError):self.d.renders.download(a,engine,'delivery.zip')

if __name__=='__main__':unittest.main()
