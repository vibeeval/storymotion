from pack_fixture_case import PackFixtureCase
"""First-run UX and neutral output, no live provider/network/media encoding."""
import json,tempfile,unittest,shutil
from pathlib import Path
from storymotion.dashboard import Dashboard
from storymotion.engine import Engine,ROOT
from storymotion.security import WorkflowError
from neutral_identity_fixture import assert_no_source_identity, source_identity_profiles

class CustomerStartTests(PackFixtureCase):
 @source_identity_profiles()
 def test_all_new_cli_fixture_outputs_are_neutral_without_customer_identity(self):
  with tempfile.TemporaryDirectory() as tmp:
   for relative in ('tests/fixtures/examples/sample-mechanism.json','tests/fixtures/examples/sample-series.json','tests/fixtures/examples/golden/sample-mechanism.json'):
    e=Engine(Path(tmp)/str(len(relative)))
    try:
     job=e.create(ROOT/relative)['job'];e.run(job,'prepare');p=e.payload(job);self.assertEqual(p['profile']['handle'],'')
     for name in ('index.html','cover.svg','caption.txt'):
      assert_no_source_identity(self,(e.directory(job)/name).read_text())
    finally:e.store.db.close()
 def test_missing_demo_key_fails_before_any_session_or_mock_dispatch(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Dashboard(tmp,llm_mode='demo',elevenlabs_mode='demo')
   try:
    for provider in ('openai','anthropic','gemini','openrouter'):
     with self.assertRaisesRegex(WorkflowError,'MALFORMED_CREDENTIAL'):d.llm.connect(provider,'')
    with self.assertRaises(WorkflowError):d.eleven.connect('')
    self.assertFalse(d.llm.connections);self.assertFalse(d.eleven.connections);self.assertFalse(d.llm.transport.calls)
   finally:d.clear_keys()
 @unittest.skipUnless(shutil.which('node'),'Node required for DOM')
 def test_starter_uses_explicit_local_adapter_and_customer_brand_without_key(self):
  import test_llm_ui as ui
  ui.WriterUi().dom(r'''
  ready();context.template={video:{title:'Örnek',brief:'Yerel teknik örnek',script:'Sabit metin.',caption:'Yerel örnek.'}};run('state.template=template;state.format={id:"account-video",adapter:"account-pack"};state.revision=0;refreshJobs=async()=>{}');$('brand-name').value='Müşteri provası';$('brand-handle').value='musteriprovasi';
  const calls=[];context.mockApi=async(path,data)=>{calls.push({path,data});return{id:'c'.repeat(24)};};run('api=mockApi');assert.equal(calls.length,0);$('starter-create').listeners.click[0]();await settle();assert.equal(calls.length,1);assert.equal(calls[0].path,'/api/jobs');assert.equal(calls[0].data.provider,'local');assert.equal(calls[0].data.model,'manual');assert.equal(calls[0].data.brand_identity.handle,'musteriprovasi');assert.equal(calls[0].data.content,'Sabit metin.');assert.ok(!Object.keys(calls[0].data).some(k=>/key|token|credential/i.test(k)));assert.match($('notice').textContent,/Sabit yerel örnek/);
  ''')
 @unittest.skipUnless(shutil.which('node'),'Node required for DOM')
 def test_player_resets_on_selection_and_errors_offer_setup_or_explicit_connection(self):
  import test_llm_ui as ui
  ui.WriterUi().dom(r'''
  ready();context.j={id:'c'.repeat(24),payload:{format:{adapter:'account-pack'}}};context.mockApi=async()=>({status:'complete',files:{'render-mobile.mp4':'a'.repeat(64)}});run('api=mockApi;state.job=j;renderJobChanged(j)');await settle();assert.equal($('render-preview').hidden,false);assert.ok($('render-preview').src.endsWith('/hyperframes/render-mobile.mp4'));run('state.job=null;renderJobChanged(null)');assert.equal($('render-preview').hidden,true);run('notice("hyperframes local runtime missing, stale or unsupported",true)');assert.match($('notice').textContent,/storymotion setup/);run('notice("MALFORMED_CREDENTIAL",true)');assert.match($('notice').textContent,/anahtar.*boş/);assert.ok('controls'in $('render-preview').attrs);assert.ok('playsinline'in $('render-preview').attrs);
  ''')

if __name__=='__main__':unittest.main()
