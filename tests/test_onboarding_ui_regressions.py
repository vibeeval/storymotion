from pack_fixture_case import PackFixtureCase
import unittest,shutil
import test_llm_ui as ui

@unittest.skipUnless(shutil.which('node'),'Node required')
class OnboardingRegressions(PackFixtureCase):
 def test_normal_brief_enqueue_also_preserves_existing_selection_and_view(self):
  ui.WriterUi().dom(r'''
  ready();run('state.revision=0;state.format={id:"account-video"};state.job={id:"d".repeat(24)};refreshJobs=async()=>{}');$('selected-job').textContent='B işi';$('render-preview').src='/B-video';$('content').value='Kaydedilmemiş metin';context.mockApi=async()=>({id:'c'.repeat(24)});run('api=mockApi');$('brief-form').listeners.submit[0]({preventDefault(){}});await settle();assert.equal(run('state.job.id'),'d'.repeat(24));assert.equal($('selected-job').textContent,'B işi');assert.equal($('render-preview').src,'/B-video');assert.equal($('content').value,'Kaydedilmemiş metin');
  ''')
 def test_late_normal_enqueue_cannot_override_new_selection_or_leave_qa_tab(self):
  ui.WriterUi().dom(r'''
  ready();run('state.revision=0;state.format={id:"account-video"};refreshJobs=async()=>{}');let resolve;context.mockApi=()=>new Promise(r=>resolve=r);run('api=mockApi');$('brief-form').listeners.submit[0]({preventDefault(){}});await settle();run('state.jobEpoch++;state.job={id:"d".repeat(24)};tab("qa")');$('selected-job').textContent='Yeni seçim';resolve({id:'c'.repeat(24)});await settle();assert.equal(run('state.job.id'),'d'.repeat(24));assert.equal($('tab-qa').hidden,false);assert.equal($('selected-job').textContent,'Yeni seçim');
  ''')
 def test_every_nonvalid_render_state_removes_stale_player(self):
  for value in ["{status:'invalidated'}","{status:'failed'}","{status:'running'}","{status:'complete',files:{}}","{status:'complete'}","{status:'complete',files:{'render-mobile.mp4':'bad'}}"]:
   ui.WriterUi().dom(r'''
   ready();context.j={id:'c'.repeat(24),payload:{format:{adapter:'account-pack'}}};context.mockApi=async()=>({status:'complete',files:{'render-mobile.mp4':'a'.repeat(64)}});run('api=mockApi;state.job=j;renderJobChanged(j)');await settle();assert.equal($('render-preview').hidden,false);
   context.mockApi=async()=>(INVALID);run('api=mockApi');await run('renderLoad(j.id,"hyperframes")');assert.equal($('render-preview').hidden,true);assert.equal($('render-preview-hint').hidden,true);assert.ok(!('src'in $('render-preview').attrs));
   '''.replace('INVALID',value))
 def test_current_render_error_clears_player_but_stale_response_cannot_clear_new_selection(self):
  ui.WriterUi().dom(r'''
  ready();context.j={id:'c'.repeat(24),payload:{format:{adapter:'account-pack'}}};context.mockApi=async()=>({status:'complete',files:{'render-mobile.mp4':'a'.repeat(64)}});run('api=mockApi;state.job=j;renderJobChanged(j)');await settle();context.mockApi=async()=>{throw Error('invalidated')};run('api=mockApi');await run('renderLoad(j.id,"hyperframes")').catch(()=>{});assert.equal($('render-preview').hidden,true);
  let resolve;context.mockApi=()=>new Promise(r=>resolve=r);run('api=mockApi');const pending=run('renderLoad(j.id,"hyperframes")');run('state.job={id:"d".repeat(24)};localRender.epoch++');$('render-preview').src='/new-selection';$('render-preview').hidden=false;resolve({status:'invalidated'});await pending;assert.equal($('render-preview').hidden,false);assert.equal($('render-preview').src,'/new-selection');
  ''')
 def test_starter_never_assigns_job_or_overwrites_existing_selection_or_draft(self):
  ui.WriterUi().dom(r'''
  ready();context.template={video:{title:'Örnek',brief:'Yerel örnek',script:'Sabit metin.',caption:'Örnek.'}};run('state.template=template;state.format={id:"account-video",adapter:"account-pack"};state.revision=0;refreshJobs=async()=>{};state.job={id:"d".repeat(24)}');$('selected-job').textContent='B işi';$('render-preview').src='/B-video';$('render-preview').hidden=false;$('content').value='Kaydedilmemiş taslak';
  let resolve;context.mockApi=()=>new Promise(r=>resolve=r);run('api=mockApi');$('starter-create').listeners.click[0]();await settle();resolve({id:'c'.repeat(24)});await settle();assert.equal(run('state.job.id'),'d'.repeat(24));assert.equal($('selected-job').textContent,'B işi');assert.equal($('render-preview').src,'/B-video');assert.equal($('content').value,'Kaydedilmemiş taslak');
  ''')
 def test_pending_starter_does_not_switch_view_after_new_job_selection_generation(self):
  ui.WriterUi().dom(r'''
  ready();context.template={video:{title:'Örnek',brief:'Yerel örnek',script:'Sabit metin.',caption:'Örnek.'}};run('state.template=template;state.format={id:"account-video",adapter:"account-pack"};state.revision=0;refreshJobs=async()=>{}');let resolve;context.mockApi=()=>new Promise(r=>resolve=r);run('api=mockApi');$('starter-create').listeners.click[0]();await settle();run('state.jobEpoch++;state.job={id:"d".repeat(24)};tab("qa")');$('selected-job').textContent='B işi';resolve({id:'c'.repeat(24)});await settle();assert.equal(run('state.job.id'),'d'.repeat(24));assert.equal($('tab-qa').hidden,false);assert.equal($('selected-job').textContent,'B işi');
  ''')
