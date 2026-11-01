from pack_fixture_case import PackFixtureCase
from storymotion.account_packs import render_profile
"""Bounded compiled edit execution contracts; no paid API/media encoding."""
import copy,json,shutil,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from storymotion.engine import Engine,ROOT
from storymotion.security import WorkflowError,digest
from storymotion.creative import ACCOUNTS,load_pack,validate_proposal
from storymotion.edit_plan import compile_edit_plan,verify_edit_plan,required_assets
from test_writing_context import SOURCE
from storymotion.writing_context import snapshot,bound_brief


def golden(account):return json.loads((ROOT/'tests/fixtures/examples/golden'/f'{account}.json').read_text())
def profile(account):
 p=render_profile(account);p['handle']='';return p


class EditPlanTests(PackFixtureCase):
 def test_four_families_compile_distinct_object_camera_and_cue_tracks(self):
  for account in ACCOUNTS:
   b=validate_proposal(account,golden(account));p=compile_edit_plan(profile(account),b,ROOT)
   self.assertEqual(p['actual_visual_family'],load_pack(account)['visual_family']);self.assertFalse(p['acceptance']['publication_ready']);self.assertEqual(p['acceptance']['status'],'incomplete')
   self.assertEqual(len(p['scenes']),len(b['scenes']));self.assertEqual(len(p['assets']),4)
   for source,scene in zip(b['scenes'],p['scenes']):
    self.assertEqual(scene['object_id'],source['object_id']);self.assertEqual(scene['rule_ids'],source['rule_ids']);self.assertTrue(scene['cue_indexes'])
    self.assertTrue(all(o['target']!='camera' for o in scene['object_motion']));self.assertTrue(all(o['target']=='camera' for o in scene['camera_motion']))
    for op in scene['object_motion']+scene['camera_motion']:self.assertIn('id="s'+str(b['scenes'].index(source))+'-'+op['target']+'"',scene['vector'])
 def test_topic_motif_text_does_not_claim_new_geometry_or_accepted_canon(self):
  b=golden('sample-series');b['creative']['visual_motif']='A new ship would need an authored family'
  p=compile_edit_plan(profile('sample-series'),validate_proposal('sample-series',b),ROOT)
  self.assertEqual(p['actual_visual_family'],load_pack('sample-series')['visual_family']);self.assertIn('does not create new geometry',p['scope']);self.assertEqual(b['creative']['canon_status'],'noncanonical_fixture')
 def test_two_engines_prepare_from_exact_same_plan_with_no_native_calls(self):
  with tempfile.TemporaryDirectory() as tmp,patch('storymotion.engine.checked_process',side_effect=AssertionError('No native process')):
   plans=[]
   for engine in ('hyperframes','remotion'):
    e=Engine(Path(tmp)/engine)
    try:
     job=e.create(ROOT/'tests/fixtures/examples/golden/sample-mechanism.json',render_engine=engine)['job'];e.run(job,'prepare');payload=e.payload(job);out=e.directory(job);plan=json.loads((out/'edit-plan.json').read_text());self.assertEqual(plan,payload['edit_plan']);plans.append(plan)
     self.assertIn(plan['scenes'][0]['vector'],(out/'index.html').read_text())
     if engine=='remotion':
      props=json.loads((out/'remotion-props.json').read_text());self.assertEqual(props['edit_plan'],plan);self.assertIn("from './edit-motion.mjs'",(out/'remotion-entry.jsx').read_text());self.assertEqual((out/'edit-motion.mjs').read_bytes(),(ROOT/'renderers/edit-motion.mjs').read_bytes())
    finally:e.store.db.close()
   self.assertEqual(plans[0],plans[1])
 def test_missing_or_changed_asset_rejects_before_job_store_or_build(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);shutil.copytree(ROOT/'vendor',root/'vendor');(root/'renderers').mkdir();shutil.copyfile(ROOT/'renderers/assets-lock.json',root/'renderers/assets-lock.json')
   target=root/'vendor/fonts/schibsted-grotesk-latin-ext-wght-normal.woff2';original=target.read_bytes()
   for content in (None,b'not the approved font'):
    if content is None:target.unlink()
    else:target.write_bytes(content)
    e=Engine(root/'should-not-exist')
    with patch('storymotion.edit_plan.required_assets',side_effect=lambda ignored:required_assets(root)):
     with self.assertRaisesRegex(WorkflowError,'asset missing or changed'):e.create(ROOT/'tests/fixtures/examples/golden/sample-mechanism.json')
    self.assertIsNone(e._store);self.assertFalse((root/'should-not-exist').exists())
   target.write_bytes(original)
 def test_plan_tampering_or_input_revision_is_rejected_before_prepare_outputs(self):
  with tempfile.TemporaryDirectory() as tmp:
   e=Engine(Path(tmp)/'work');_,payload=e.plan(ROOT/'tests/fixtures/examples/golden/sample-mechanism.json')
   for field in ('plan','input'):
    bad=copy.deepcopy(payload)
    if field=='plan':bad['edit_plan']['scenes'][0]['object_motion'][0]['target']='replacement'
    else:bad['brief']['scenes'][0]['camera']='locked'
    with patch('storymotion.engine.build',side_effect=AssertionError('No artifact write')):
     with self.assertRaisesRegex(WorkflowError,'Pinned edit plan'):e.perform('prepare',bad,Path(tmp)/'no-output')
    self.assertFalse((Path(tmp)/'no-output').exists())
 def test_audio_or_camera_timing_changes_make_new_plan_not_reuse_old_acceptance(self):
  b=validate_proposal('sample-mechanism',golden('sample-mechanism'));p=profile('sample-mechanism');a=compile_edit_plan(p,b,ROOT);changed=copy.deepcopy(b);changed['scenes'][0]['camera']='locked';z=compile_edit_plan(p,changed,ROOT)
  self.assertNotEqual(a['plan_sha256'],z['plan_sha256']);self.assertEqual(a['scenes'][0]['object_motion'],z['scenes'][0]['object_motion']);self.assertNotEqual(a['scenes'][0]['camera_motion'],z['scenes'][0]['camera_motion'])
  for s in changed['scenes']:s['start']*=2;s['end']*=2
  for c in changed['cues']:c['start']*=2;c['end']*=2
  changed['duration']*=2
  r=compile_edit_plan(p,changed,ROOT);self.assertNotEqual(r['plan_sha256'],z['plan_sha256']);self.assertEqual(r['scenes'][1]['start'],8)
 def test_source_claim_quote_and_unmatched_claim_survive_without_truth_approval(self):
  b=golden('sample-mechanism');b['claims']=[{'text':b['scenes'][0]['information'],'source':'test-study','scope':'Only synthetic drawing'},{'text':'A separate global claim','source':'test-study','scope':'No inferred semantic match'}]
  src=snapshot('sources','sample-mechanism',SOURCE,None);binding={'schema_version':1,'account':'sample-mechanism','sources':src,'canon':None};binding['binding_sha256']=digest(binding)
  b['production_context']=binding;b=bound_brief('sample-mechanism',b);p=compile_edit_plan(profile('sample-mechanism'),b,ROOT)
  self.assertEqual(p['source_binding_sha256'],binding['binding_sha256']);self.assertEqual(p['scenes'][0]['exact_copy_claim_indexes'],[0]);self.assertEqual(p['claims_without_exact_scene_copy'],[1]);self.assertEqual(p['claim_traceability']['source_links'][0]['excerpt'],SOURCE['test-study']['excerpt']);self.assertEqual(p['claim_traceability']['status'],'incomplete')
 def test_dashboard_preview_matches_intake_and_never_starts_runtime_or_creates_render(self):
  from storymotion.dashboard import Dashboard
  from audio_fixture import source_job
  with tempfile.TemporaryDirectory() as tmp:
   d=Dashboard(tmp)
   try:
    for account in ACCOUNTS:
     job=source_job(d,account)
     for engine in ('hyperframes','remotion'):
      with patch('storymotion.engine.checked_process',side_effect=AssertionError('No probe/render')),patch('storymotion.dashboard_render.require_engine',side_effect=AssertionError('No runtime requirement')):
       result=d.render_action(job,'edit-plan',{'engine':engine})
      self.assertEqual(result['edit_plan']['account'],account);self.assertFalse(result['render_started']);self.assertIsNone(d.renders.row(job,engine))
      p=Path(tmp)/'expected.json';p.write_text(json.dumps(d.renders.video_input(d.job(job))));_,payload=Engine(Path(tmp)/'never-created').plan(p,engine)
      self.assertEqual(payload['edit_plan'],result['edit_plan']);self.assertFalse((Path(tmp)/'never-created').exists())
    with self.assertRaises(WorkflowError):d.render_action(job,'edit-plan',{'engine':'remotion','command':'bad'})
   finally:d.clear_keys()
 def test_synthetic_audio_delivery_rejects_changed_plan_and_retime_is_fresh(self):
  from storymotion.dashboard import Dashboard
  from audio_flow_fixture import seed_final
  from audio_fixture import no_media
  with tempfile.TemporaryDirectory() as tmp,no_media():
   d=Dashboard(tmp)
   try:
    for engine in ('hyperframes','remotion'):
     parent,child,_,out,payload=seed_final(d,'sample-mechanism',engine);plan=payload['edit_plan']
     self.assertEqual(plan['audio_timing_sha256'],digest(payload['brief']['audio_timing']));self.assertEqual(plan['duration'],payload['brief']['duration'])
     self.assertTrue(d.renders.download(child,engine,'delivery.zip'))
     (out/'edit-plan.json').write_text('{}')
     with self.assertRaises(WorkflowError):d.renders.download(child,engine,'delivery.zip')
   finally:d.clear_keys()
 def test_official_http_plan_action_is_host_origin_schema_guarded_and_read_only(self):
  import test_writing_context_http as http_fixture
  from audio_fixture import source_job
  h=http_fixture.ContextHttpTests();h.setUp()
  try:
   job=source_job(h.d,'sample-mechanism');path='/api/jobs/'+job+'/edit-plan'
   with patch('storymotion.engine.checked_process',side_effect=AssertionError('No native tool')):
    h.call(path,{'engine':'remotion'},403,origin='https://attacker.test');h.call(path,{'engine':'remotion','url':'https://attacker.test'},400)
    result=h.call(path,{'engine':'remotion'});self.assertEqual(result['edit_plan']['account'],'sample-mechanism');self.assertFalse(result['render_started']);self.assertIsNone(h.d.renders.row(job,'remotion'));self.assertFalse(h.d.llm.transport.calls)
  finally:h.tearDown()
 def test_four_original_demo_briefs_prepare_as_bounded_not_real_topic_videos(self):
  with tempfile.TemporaryDirectory() as tmp:
   for account in ACCOUNTS:
    e=Engine(Path(tmp)/account)
    try:
     job=e.create(ROOT/'tests/fixtures/examples/edit-plans'/f'{account}.json')['job'];e.run(job,'prepare');p=e.payload(job)['edit_plan'];self.assertEqual(len(p['claim_traceability']['source_links']),len(p['scenes']));self.assertFalse(p['claims_without_exact_scene_copy']);self.assertFalse(p['acceptance']['publication_ready'])
    finally:e.store.db.close()
 @unittest.skipUnless(shutil.which('node'),'Node required for read-only UI contract')
 def test_dashboard_plan_requires_explicit_click_and_ignores_stale_response(self):
  import test_llm_ui as ui
  ui.WriterUi().dom(r'''
  ready();run('tab("qa")');const id='c'.repeat(24),next='d'.repeat(24);context.j={id,payload:{format:{adapter:'account-pack'}}};const calls=[];let release;
  context.mockApi=async(path,body)=>{calls.push(path);if(path.endsWith('/render-state'))return{status:'not_started',files:{}};assert.ok(path.endsWith('/edit-plan'));return new Promise(resolve=>{release=resolve;});};run('api=mockApi;state.job=j;renderJobChanged(j)');await settle();assert.ok(!calls.some(p=>p.endsWith('/edit-plan')));assert.equal($('edit-plan-read').disabled,false);
  $('edit-plan-read').listeners.click[0]();await settle();context.other={id:next,payload:{format:{adapter:'account-pack'}}};run('state.job=other;renderJobChanged(other)');
  release({edit_plan:{account:'sample-series',requested_motif_text:'owned sample-series',actual_visual_family:'hinged-latch',scenes:[{}],plan_sha256:'a'.repeat(64)}});await settle();assert.equal($('edit-plan-details').hidden,true);assert.equal($('edit-plan-data').textContent,'');assert.ok(!calls.some(p=>p.endsWith('/render')));
  $('edit-plan-read').listeners.click[0]();await settle();release({edit_plan:{account:'sample-series',requested_motif_text:'owned sample-series',actual_visual_family:'hinged-latch',scenes:[{}],plan_sha256:'e'.repeat(64)}});await settle();assert.equal($('edit-plan-details').hidden,false);assert.match($('edit-plan-summary').textContent,/İnsan.*render başlamadı/);assert.ok($('edit-plan-details').open);assert.ok(!$('edit-plan-data').textContent.includes('sample-series'));assert.match($('edit-plan-data').textContent,/Sample Series/);
  $('edit-plan-details').querySelector('summary').focus();run('state.job=null;renderJobChanged(null)');assert.equal(run('document.activeElement.id'),'render-title');assert.equal($('edit-plan-read').disabled,true);assert.equal($('edit-plan-details').hidden,true);
  ''')
 @unittest.skipUnless(shutil.which('node'),'Node required for canonical sampler')
 def test_bundled_gsap_easing_matches_canonical_sampler_in_shuffled_seek_order(self):
  plans={a:compile_edit_plan(profile(a),validate_proposal(a,golden(a)),ROOT) for a in ACCOUNTS}
  script="""import assert from 'node:assert/strict';import{createRequire}from 'node:module';import{sampleMotion}from './renderers/edit-motion.mjs';const gsap=createRequire(import.meta.url)('./vendor/gsap.min.js').gsap;let raw='';for await(const c of process.stdin)raw+=c;const plans=JSON.parse(raw);let samples=0;
  const numeric=v=>Object.fromEntries(Object.entries(v).filter(([k,x])=>typeof x==='number'));
  for(const p of Object.values(plans))for(const s of p.scenes){const ops=s.object_motion.concat(s.camera_motion),targets={},tl=gsap.timeline({paused:true});for(const op of ops){const t=targets[op.target]??=( {x:0,y:0,scale:1,rotation:0,opacity:1} );if(op.op==='set')gsap.set(t,numeric(op.values));else tl.fromTo(t,numeric(op.before),{...numeric(op.after),duration:op.duration,ease:'power2.inOut'},op.offset);}
   const d=s.end-s.start;for(const t of [d*.83,0,d*.4,d-.001,d*.12,d*.4,0]){tl.totalTime(t,false);const expected=sampleMotion(ops,t);for(const [name,values]of Object.entries(expected))for(const [key,value]of Object.entries(numeric(values)))assert.ok(Math.abs(targets[name][key]-value)<.0002,`${p.account}/${s.id}/${name}/${key}/${t}: ${targets[name][key]} vs ${value}`);samples++;}tl.kill();}
  gsap.ticker.sleep();console.log(JSON.stringify({samples,scope:'GSAP object tween math vs pure sampler;notSVGpixels/nativeframe'}));"""
  r=subprocess.run(['node','--input-type=module','-e',script],cwd=ROOT,input=json.dumps(plans),text=True,capture_output=True,timeout=15)
  self.assertEqual(r.returncode,0,r.stderr)
 @unittest.skipUnless(shutil.which('node'),'Node required for canonical sampler')
 def test_independent_seek_orders_and_endpoints_preserve_object_camera_separation(self):
  plans={a:compile_edit_plan(profile(a),validate_proposal(a,golden(a)),ROOT) for a in ACCOUNTS}
  script="""import assert from 'node:assert/strict';import{sampleMotion,applyMotion}from './renderers/edit-motion.mjs';let raw='';for await(const chunk of process.stdin)raw+=chunk;const plans=JSON.parse(raw);
  for(const plan of Object.values(plans))for(const scene of plan.scenes){const ops=scene.object_motion.concat(scene.camera_motion),length=scene.end-scene.start,times=[0,length/4,length/2,length-.001];const first=new Map(times.map(t=>[t,applyMotion(scene.vector,'s'+plan.scenes.indexOf(scene),ops,t)]));for(const t of [...times].reverse()){assert.equal(applyMotion(scene.vector,'s'+plan.scenes.indexOf(scene),ops,t),first.get(t));const object=sampleMotion(scene.object_motion,t),all=sampleMotion(ops,t);for(const key of Object.keys(object))assert.deepEqual(object[key],all[key]);}}
  const alt=plans['sample-mechanism'].scenes;assert.equal(sampleMotion(alt[0].object_motion,0).latch.rotation,0);assert.equal(sampleMotion(alt[0].object_motion,4).latch.rotation,-55);assert.equal(sampleMotion(alt[1].object_motion,4).lid.rotation,28);
  const ai=plans['sample-flow'].scenes;assert.equal(sampleMotion(ai[1].object_motion,0).paper.x,260);assert.equal(sampleMotion(ai[1].object_motion,4).paper.x,620);assert.equal(sampleMotion(ai[1].object_motion,4).gate.rotation,-85);
  assert.throws(()=>sampleMotion([],NaN));console.log('independent seek endpoints and separate camera:pass');"""
  r=subprocess.run(['node','--input-type=module','-e',script],cwd=ROOT,input=json.dumps(plans),text=True,capture_output=True,timeout=15)
  self.assertEqual(r.returncode,0,r.stderr)


if __name__=='__main__':unittest.main()
