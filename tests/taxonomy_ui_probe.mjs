import assert from 'node:assert/strict';
import {harness} from './family_gallery_dom.mjs';
let raw='';for await(const chunk of process.stdin){raw+=chunk;if(Buffer.byteLength(raw)>8000000)throw Error('Probe input bound');}
const input=JSON.parse(raw),F=input.fixtures,reply=value=>({ok:true,json:async()=>structuredClone(value)}),clone=structuredClone;
const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r;});return {promise,resolve};};
const failures=[],passed=[];
function setup(initial=F.a0){
 const h=harness({...input,prependSources:[input.panel]});
 h.respond(call=>call.path==='/api/taxonomy/state'?reply(call.data.account==='neutral'?initial:F.b0):undefined);return h;
}
async function choose(h,selection){await h.set('taxonomy-niche',selection.niche);await h.set('taxonomy-topic',selection.topic);}
async function load(h){await h.load();await h.flush();assert.equal(h.get('family-account').value,'neutral');}
async function test(name,fn){try{await fn();passed.push(name);}catch(error){failures.push({name,error:error.stack});}}

await test('saved-selection-and-exact-prepare',async()=>{
 const h=setup();await load(h);assert.equal(h.get('family-prepare').disabled,false);assert.equal(h.get('taxonomy-panel').hidden,false);
 await choose(h,F.a1.selection);assert.equal(h.get('family-prepare').disabled,true);
 h.respond(call=>{
  if(call.path==='/api/taxonomy/select'){assert.deepEqual(call.data,F.selectRequest);return reply(F.a1);}
  if(call.path==='/api/template-families/prepare'){assert.deepEqual(call.data,F.prepareRequest);return reply(F.prepared);}
 });
 await h.get('taxonomy-apply').emit('click');assert.equal(h.get('family-prepare').disabled,false);
 assert.deepEqual(clone(h.planning().prepareStatus('neutral').token),{...F.a1.selection,revision:F.a1.revision});
 await h.get('family-form').emit('submit');assert.ok(h.get('family-result').textContent.includes('Preparation receipt'));
 assert.equal(h.calls.filter(c=>c.path==='/api/template-families/prepare').length,1);
});
await test('late-state-never-crosses-account',async()=>{
 const h=setup(),wait=deferred();h.respond(call=>call.path==='/api/taxonomy/state'?(call.data.account==='neutral'?wait.promise:reply(F.b0)):undefined);
 await h.load();await h.flush();assert.equal(h.get('family-prepare').disabled,true);
 await h.set('family-account','studio-b');await h.flush();assert.equal(h.get('family-prepare').disabled,false);
 wait.resolve(reply(F.a1));await h.flush();assert.ok(h.get('taxonomy-context').textContent.startsWith('studio-b'));
 assert.equal(h.planning().prepareStatus('studio-b').token,null);
});
await test('edits-during-saved-reply-are-retained',async()=>{
 const h=setup();await load(h);await choose(h,F.a1.selection);const wait=deferred();h.respond(call=>call.path==='/api/taxonomy/select'?wait.promise:undefined);
 const pending=h.get('taxonomy-apply').emit('click');await h.flush();
 const different=F.a0.topics.find(t=>t.niche!==F.a1.selection.niche);await choose(h,{niche:different.niche,topic:different.id});
 wait.resolve(reply(F.a1));await pending;await h.flush();assert.equal(h.get('taxonomy-topic').value,different.id);assert.equal(h.get('family-prepare').disabled,true);
 await h.get('taxonomy-revert').emit('click');assert.equal(h.get('taxonomy-topic').value,F.a1.selection.topic);assert.equal(h.get('family-prepare').disabled,false);
});
await test('interrupted-name-edits-survive-account-switch',async()=>{
 const h=setup();await load(h);await h.set('taxonomy-niche-name','Unfinished local name','input');h.get('taxonomy-niche-name').focus();
 await h.set('family-account','studio-b');await h.flush();assert.equal(h.get('taxonomy-niche-name').value,'');
 await h.set('family-account','neutral');await h.flush();assert.equal(h.get('taxonomy-niche-name').value,'Unfinished local name');assert.equal(h.get('family-prepare').disabled,true);
 assert.equal(h.calls.filter(c=>c.path==='/api/taxonomy/create').length,0);
 await h.get('taxonomy-revert').emit('click');assert.equal(h.get('taxonomy-niche-name').value,'');assert.equal(h.get('family-prepare').disabled,false);
});
await test('custom-niche-topic-and-explicit-apply',async()=>{
 const h=setup(F.a1);await load(h);const spec=h.get('family-spec').value;
 h.respond(call=>{
  if(call.path==='/api/taxonomy/create'&&call.data.kind==='niche'){assert.deepEqual(call.data,F.createNicheRequest);return reply(F.createdNiche);}
  if(call.path==='/api/taxonomy/create'){assert.deepEqual(call.data,F.createTopicRequest);return reply(F.createdTopic);}
  if(call.path==='/api/taxonomy/select'){assert.deepEqual(call.data,F.customSelectRequest);return reply(F.a4);}
 });
 await h.set('taxonomy-niche-name',F.createNicheRequest.name,'input');await h.get('taxonomy-add-niche').emit('click');
 assert.equal(h.get('taxonomy-niche').value,F.createdNiche.item.id);assert.equal(h.get('taxonomy-topic').value,'');assert.equal(h.get('family-prepare').disabled,true);
 await h.set('taxonomy-topic-name',F.createTopicRequest.name,'input');await h.get('taxonomy-add-topic').emit('click');assert.equal(h.get('taxonomy-topic').value,F.createdTopic.item.id);
 await h.get('taxonomy-apply').emit('click');assert.equal(h.get('family-prepare').disabled,false);assert.equal(h.get('family-spec').value,spec);
});
await test('late-create-cannot-replace-other-account',async()=>{
 const h=setup(F.a1);await load(h);await h.set('taxonomy-niche-name',F.createNicheRequest.name,'input');const wait=deferred();
 h.respond(call=>call.path==='/api/taxonomy/create'?wait.promise:call.path==='/api/taxonomy/state'?reply(F.b0):undefined);
 const pending=h.get('taxonomy-add-niche').emit('click');await h.flush();await h.set('family-account','studio-b');await h.flush();
 wait.resolve(reply(F.createdNiche));await pending;await h.flush();assert.ok(h.get('taxonomy-context').textContent.startsWith('studio-b'));assert.equal(h.get('taxonomy-niche-name').value,'');
 assert.equal(h.planning().prepareStatus('studio-b').blocked,false);
});
await test('failure-requires-reload-before-explicit-retry',async()=>{
 const h=setup();await load(h);await choose(h,F.a1.selection);
 h.respond(call=>call.path==='/api/taxonomy/select'?{ok:false,json:async()=>({error:'TAXONOMY_REVISION_CHANGED'})}:undefined);
 await h.get('taxonomy-apply').emit('click');assert.equal(h.get('family-prepare').disabled,true);assert.equal(h.get('taxonomy-apply').disabled,true);
 await h.set('taxonomy-topic',F.a1.selection.topic);await h.get('taxonomy-apply').emit('click');assert.equal(h.calls.filter(c=>c.path==='/api/taxonomy/select').length,1);
 h.respond(call=>call.path==='/api/taxonomy/state'?reply(F.a0):call.path==='/api/taxonomy/select'?reply(F.a1):undefined);
 await h.get('taxonomy-reload').emit('click');assert.equal(h.get('taxonomy-topic').value,F.a1.selection.topic);
 await h.get('taxonomy-apply').emit('click');assert.equal(h.calls.filter(c=>c.path==='/api/taxonomy/select').length,2);assert.equal(h.get('family-prepare').disabled,false);
});
await test('reload-retains-local-choice-and-text-focus',async()=>{
 const h=setup();await load(h);await choose(h,F.a1.selection);await h.set('taxonomy-niche-name','Still editing','input');
 const n=h.get('taxonomy-niche-name');n.focus();n.selectionStart=4;
 h.respond(call=>call.path==='/api/taxonomy/state'?reply(F.a1):undefined);await h.get('taxonomy-reload').emit('click');
 assert.equal(n.value,'Still editing');assert.equal(n.selectionStart,4);assert.equal(h.document.activeElement,n);assert.equal(h.get('family-prepare').disabled,true);
});
await test('clear-is-explicit-and-does-not-reset-template-json',async()=>{
 const h=setup(F.a4);await load(h);const edited=JSON.parse(h.get('family-spec').value);edited.parameters.title='Local JSON edit';await h.set('family-spec',JSON.stringify(edited),'input');
 h.respond(call=>{if(call.path==='/api/taxonomy/select'){assert.deepEqual(call.data,F.clearRequest);return reply(F.a5);}});
 await h.get('taxonomy-clear').emit('click');assert.equal(h.planning().prepareStatus('neutral').token,null);assert.equal(h.get('family-spec').value,JSON.stringify(edited));
});
await test('invalid-response-does-not-enable-stale-planning',async()=>{
 const h=setup();await load(h);h.respond(call=>call.path==='/api/taxonomy/state'?reply({...F.a0,account:'studio-b'}):undefined);
 await h.get('taxonomy-reload').emit('click');assert.equal(h.get('family-prepare').disabled,true);assert.equal(h.get('taxonomy-apply').disabled,true);
});
await test('account-removal-invalidates-pending-plan',async()=>{
 const h=setup();await load(h);const wait=deferred();h.respond(call=>call.path==='/api/taxonomy/state'?wait.promise:undefined);
 const pending=h.get('taxonomy-reload').emit('click');await h.flush();const catalog=clone(input.catalog);for(const f of catalog.families)f.profile_ids=['studio-b'];h.catalog(catalog);await h.load();
 assert.equal(h.get('family-account').value,'');assert.equal(h.get('taxonomy-panel').hidden,true);wait.resolve(reply(F.a1));await pending;await h.flush();assert.equal(h.get('taxonomy-context').textContent,'');
});
function unconfirmed(h){assert.ok(h.get('taxonomy-status').textContent.includes('unconfirmed'));assert.equal(h.get('family-prepare').disabled,true);assert.equal(h.get('taxonomy-apply').disabled,true);}
await test('apply-rejects-genuine-unrelated-same-account-state',async()=>{
 const h=setup();await load(h);await choose(h,F.a1.selection);h.respond(call=>call.path==='/api/taxonomy/select'?reply(F.a4):undefined);
 await h.get('taxonomy-apply').emit('click');unconfirmed(h);assert.equal(h.get('taxonomy-niche').value,F.a1.selection.niche);assert.equal(h.get('taxonomy-topic').value,F.a1.selection.topic);
 assert.equal(h.calls.filter(c=>c.path==='/api/taxonomy/select').length,1);
});
await test('clear-rejects-contradictory-nonnull-selection',async()=>{
 const h=setup(F.a4);await load(h);h.respond(call=>call.path==='/api/taxonomy/select'?reply(F.a1):undefined);
 await h.get('taxonomy-clear').emit('click');unconfirmed(h);assert.equal(h.get('taxonomy-niche').value,F.a4.selection.niche);assert.equal(h.get('taxonomy-topic').value,F.a4.selection.topic);
});
await test('create-niche-rejects-wrong-name-type-or-member',async()=>{
 const cases=[{response:F.createdNiche,name:'A different submitted name'},
  {response:F.createdTopic,name:F.createNicheRequest.name},
  {response:{...F.createdNiche,state:F.a1},name:F.createNicheRequest.name},
  {response:{...F.createdNiche,item:{...F.createdNiche.item,name:'Forged display name'}},name:F.createNicheRequest.name}];
 for(const entry of cases){const h=setup(F.a1);await load(h);await h.set('taxonomy-niche-name',entry.name,'input');h.respond(call=>call.path==='/api/taxonomy/create'?reply(entry.response):undefined);
  await h.get('taxonomy-add-niche').emit('click');unconfirmed(h);assert.equal(h.get('taxonomy-niche-name').value,entry.name);assert.equal(h.get('taxonomy-niche').value,F.a1.selection.niche);}
});
await test('create-topic-rejects-wrong-parent-or-name',async()=>{
 for(const response of [F.wrongParent,{...F.createdTopic,item:{...F.createdTopic.item,name:'Wrong topic name'}}]){
  const h=setup(F.createdNiche.state);await load(h);await h.set('taxonomy-niche',F.createdNiche.item.id);await h.set('taxonomy-topic-name',F.createTopicRequest.name,'input');
  h.respond(call=>call.path==='/api/taxonomy/create'?reply(response):undefined);await h.get('taxonomy-add-topic').emit('click');unconfirmed(h);
  assert.equal(h.get('taxonomy-topic-name').value,F.createTopicRequest.name);assert.equal(h.get('taxonomy-niche').value,F.createdNiche.item.id);
 }
});
await test('normalized-and-unicode-idempotent-create-is-valid',async()=>{
 for(const [state,request,response]of [[F.duplicate.state,F.duplicateRequest,F.duplicate],[F.unicodeBeforeDuplicate,F.unicodeDuplicateRequest,F.unicodeDuplicate]]){
  const h=setup(state);await load(h);await h.set('taxonomy-niche-name',request.name,'input');h.respond(call=>{if(call.path==='/api/taxonomy/create'){assert.deepEqual(call.data,request);return reply(response);}});
  await h.get('taxonomy-add-niche').emit('click');assert.equal(h.get('taxonomy-niche-name').value,'');assert.equal(h.get('taxonomy-niche').value,response.item.id);assert.ok(!h.get('taxonomy-status').textContent.includes('unconfirmed'));
 }
});
await test('create-response-binds-frozen-request-not-newer-input',async()=>{
 const h=setup(F.a1);await load(h);await h.set('taxonomy-niche-name',F.createNicheRequest.name,'input');const wait=deferred();
 h.respond(call=>{if(call.path==='/api/taxonomy/create'){assert.deepEqual(call.data,F.createNicheRequest);return wait.promise;}});
 const pending=h.get('taxonomy-add-niche').emit('click');await h.flush();await h.set('taxonomy-niche-name','Newer unsent name','input');wait.resolve(reply(F.createdNiche));await pending;await h.flush();
 assert.equal(h.get('taxonomy-niche-name').value,'Newer unsent name');assert.equal(h.get('taxonomy-niche').value,F.a1.selection.niche);assert.ok(!h.get('taxonomy-status').textContent.includes('unconfirmed'));assert.equal(h.get('family-prepare').disabled,true);
});
process.stdout.write(JSON.stringify({passed,failures,scope:'Actual first-party scripts in an offline DOM model; not GUI acceptance'}));if(failures.length)process.exitCode=1;
