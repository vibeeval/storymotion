import assert from 'node:assert/strict';
import {harness} from './family_gallery_dom.mjs';
let text='';for await(const bytes of process.stdin)text+=bytes;
const input=JSON.parse(text),passed=[],failures=[];
const clone=v=>JSON.parse(JSON.stringify(v)),ok=value=>({ok:true,json:async()=>clone(value)});
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const until=async fn=>{for(let i=0;i<80&&!fn();i++)await Promise.resolve();assert.ok(fn(),'Expected request not reached');};
function make(scenario=null){
 const h=harness(input),details=scenario?[scenario.detail]:input.details,listing=scenario?.listing??input.listing;
 let extra=()=>undefined;
 const base=call=>{
  if(call.path==='/api/family-jobs/neutral')return ok(listing);
  const d=details.find(v=>call.path==='/api/family-jobs/'+v.account+'/'+v.job);if(d)return ok(d);
  if(call.path.startsWith('/api/family-renders/')){
   const value=extra(call);if(value!==undefined)return value;
   if(!call.data){const job=call.path.split('/')[4];return ok(scenario?.initial??(job===input.happy.initial.prepare_job?input.happy.initial:input.other_initial));}
   throw Error('Unexpected mutation '+call.path);
  }
 };
 h.respond(base);h.route=fn=>{extra=fn;};h.detail=details[0];h.listing=listing;return h;
}
const postCalls=h=>h.calls.filter(c=>c.path.startsWith('/api/family-renders/')&&c.data);
const ack=async h=>{h.get('family-render-ack').checked=true;await h.get('family-render-ack').emit('change');};
const click=(h,id)=>h.get('family-render-'+id).emit('click');
const seed=(h,key)=>h.run('globalThis.crypto={subtle:crypto.subtle,getRandomValues:bytes=>{bytes.set('+JSON.stringify(key.match(/../g).map(v=>parseInt(v,16)))+');return bytes;}}');
async function open(h,detail=h.detail){
 await h.get('family-history-load').emit('click');const i=h.listing.jobs.findIndex(v=>v.job===detail.job);assert.ok(i>=0);
 await h.get('family-history-list').children[i].children[0].emit('click');assert.equal(h.get('family-render-panel').hidden,false);
 assert.equal(h.get('family-render-start').disabled,true);assert.equal(h.get('family-render-ack').checked,false);
}
async function ready(h,scenario=null){await h.load();await open(h,scenario?.detail);await click(h,'refresh');}
const scenarios={
 async flow(){
  const h=make(),s=input.happy;await ready(h);assert.equal(h.get('family-render-start').disabled,true);await ack(h);assert.equal(h.get('family-render-start').disabled,false);
  let mode='start';h.route(c=>c.data?ok(mode==='start'?s.started:mode==='cancel'?s.cancelling:s.retried):ok(mode==='complete'?s.complete:mode==='cancelled'?s.cancelled:s.running));
  seed(h,s.start_data.request_key);await click(h,'start');assert.deepEqual(postCalls(h)[0].data,s.start_data);
  assert.equal(h.get('family-render-start').disabled,true);assert.equal(h.get('family-render-cancel').disabled,false);assert.equal(h.get('family-render-files').children.length,0);
  await click(h,'refresh');mode='cancel';await click(h,'cancel');assert.deepEqual(postCalls(h)[1].data,s.cancel_data);
  mode='cancelled';await click(h,'refresh');assert.equal(h.get('family-render-retry').disabled,true);await ack(h);assert.equal(h.get('family-render-retry').disabled,false);
  mode='retry';seed(h,s.retry_data.request_key);await click(h,'retry');assert.deepEqual(postCalls(h)[2].data,s.retry_data);
  mode='complete';await click(h,'refresh');assert.equal(h.get('family-render-files').children.length,2);
  for(const li of h.get('family-render-files').children){const a=li.children[0];assert.ok(s.complete.files.some(f=>f.download_url===a.href));assert.ok(a.getAttribute('download'));}
  const n=postCalls(h).length;await click(h,'refresh');assert.equal(postCalls(h).length,n);
  for(const c of h.calls.filter(c=>c.path.startsWith('/api/family-renders/'))){assert.equal(c.options.credentials,'same-origin');assert.equal(c.options.cache,'no-store');if(c.data)assert.equal(c.options.headers['X-Storymotion-Local'],'1');else assert.equal(c.options.method,undefined);}
 },
 async idempotence(){
  const h=make(),s=input.happy;await ready(h);await ack(h);seed(h,s.start_data.request_key);const wait=deferred();h.route(c=>c.data?wait.promise:ok(s.initial));
  const pending=click(h,'start');await until(()=>postCalls(h).length===1);await click(h,'start');await click(h,'retry');assert.equal(postCalls(h).length,1);
  wait.reject(Error('TEST_ONLY_NETWORK_LOSS'));await pending;assert.equal(postCalls(h).length,1);assert.equal(h.get('family-render-files').children.length,0);
  await click(h,'refresh');await ack(h);assert.equal(h.get('family-render-start').disabled,false);
  h.route(c=>c.data?ok(s.replay):ok(s.running));await click(h,'start');assert.equal(postCalls(h).length,2);assert.deepEqual(postCalls(h)[1].data,postCalls(h)[0].data);
  const q=make();await ready(q);await ack(q);seed(q,s.start_data.request_key);q.route(c=>c.data?Promise.reject(Error('Lost acknowledgement')):ok(s.running));await click(q,'start');assert.equal(postCalls(q).length,1);await click(q,'refresh');assert.equal(q.get('family-render-start').disabled,true);assert.equal(q.get('family-render-cancel').disabled,false);assert.equal(postCalls(q).length,1);
 },
 async stale(){
  for(const error of [false,true]){
   const h=make(),s=input.happy;await ready(h);await ack(h);seed(h,s.start_data.request_key);const wait=deferred();h.route(c=>c.data?wait.promise:ok(input.other_initial));
   const pending=click(h,'start');await until(()=>postCalls(h).length===1);await open(h,input.details[1]);
   const binding=h.get('family-render-binding').textContent,status=h.get('family-render-status').textContent;
   if(error)wait.reject(Error('OLD_SELECTION_ERROR'));else wait.resolve(ok(s.started));await pending;
   assert.equal(h.get('family-render-binding').textContent,binding);assert.equal(h.get('family-render-status').textContent,status);assert.equal(h.get('family-render-files').children.length,0);
   await click(h,'refresh');assert.equal(h.get('family-render-binding').textContent,binding);
  }
  const h=make();await ready(h);const wait=deferred();h.route(()=>wait.promise);const pending=click(h,'refresh');await h.set('family-select','contour-trace');wait.reject(Error('OLD_READ_ERROR'));await pending;assert.equal(h.get('family-render-panel').hidden,true);
  for(const error of [false,true]){
   const q=make();await ready(q);const old=deferred();q.route(()=>old.promise);const reading=click(q,'refresh');await open(q);q.route(()=>ok(input.happy.complete));await click(q,'refresh');const status=q.get('family-render-status').textContent;
   if(error)old.reject(Error('OLD_STATUS_ERROR'));else old.resolve(ok(input.happy.running));await reading;assert.equal(q.get('family-render-status').textContent,status);assert.equal(q.get('family-render-files').children.length,2);
  }
  const q=make();await ready(q);await ack(q);seed(q,input.happy.start_data.request_key);const old=deferred();q.route(()=>old.promise);const starting=click(q,'start');await until(()=>postCalls(q).length===1);await q.set('family-account','');old.resolve(ok(input.happy.started));await starting;assert.equal(q.get('family-render-panel').hidden,true);assert.equal(postCalls(q).length,1);
 },
 async malformed(){
  const s=input.happy,mutations=[v=>v.account='second',v=>v.prepare_job='f'.repeat(24),v=>v.engine='remotion',v=>v.request_key='f'.repeat(32),v=>v.generation=true,v=>v.ref.id='f'.repeat(32),v=>v.previous_attempt='f'.repeat(32),v=>v.preparation_revision='f'.repeat(64),v=>v.provider_calls=1,v=>v.publication_ready=true];
  for(const mutate of mutations){const h=make();await ready(h);await ack(h);seed(h,s.start_data.request_key);const bad=clone(s.started);mutate(bad);h.route(c=>c.data?ok(bad):undefined);await click(h,'start');assert.ok(h.get('family-render-status').textContent.includes('doğrulanamadı'));assert.equal(h.get('family-render-files').children.length,0);assert.equal(h.get('family-render-cancel').disabled,true);assert.equal(postCalls(h).length,1);}
  for(const mutate of [v=>v.files[0].download_url='https://example.invalid/video',v=>v.files[0].download_url+='/extra',v=>v.actual_render=false,v=>v.files.push(v.files[0]),v=>v.files[0].sha256='bad',v=>v.execution_binding='f'.repeat(64)]){
   const h=make();await ready(h);const bad=clone(s.complete);mutate(bad);h.route(()=>ok(bad));await click(h,'refresh');assert.equal(h.get('family-render-files').children.length,0);assert.equal(h.get('family-render-retry').disabled,true);
  }
  const h=make();await ready(h);await ack(h);seed(h,s.start_data.request_key);h.route(c=>c.data?Promise.reject(Error('Unknown result')):ok({...s.running,request_key:'f'.repeat(32)}));await click(h,'start');await click(h,'refresh');await ack(h);assert.equal(h.get('family-render-start').disabled,true);assert.equal(h.get('family-render-retry').disabled,true);assert.equal(postCalls(h).length,1);
  for(const mutate of [v=>v.publication_ready=true,v=>v.attempt='a'.repeat(32),v=>v.request_key='a'.repeat(32),v=>v.ref={kind:'family_render'},v=>v.generation=true]){
   const q=make();await ready(q);const bad=clone(s.initial);mutate(bad);q.route(()=>ok(bad));await click(q,'refresh');await ack(q);assert.equal(q.get('family-render-start').disabled,true);assert.equal(postCalls(q).length,0);
  }
  for(const name of ['cancel','retry']){
   const q=make();await ready(q);q.route(c=>c.data?ok(s.running):ok(name==='cancel'?s.running:s.cancelled));await click(q,'refresh');await ack(q);seed(q,s.retry_data.request_key);await click(q,name);assert.ok(q.get('family-render-status').textContent.includes('doğrulanamadı'));assert.equal(q.get('family-render-files').children.length,0);assert.equal(postCalls(q).length,1);
  }
 },
 async recovery(){
  for(const name of ['failed','blocked','restart']){
   const s=input[name],h=make(s);await ready(h,s);h.route(c=>c.data?ok(s.retried):ok(s.state));await click(h,'refresh');assert.equal(postCalls(h).length,0);assert.equal(h.get('family-render-retry').disabled,true);await ack(h);assert.equal(h.get('family-render-retry').disabled,false,name);
   seed(h,s.retry_data.request_key);await click(h,'retry');assert.deepEqual(postCalls(h)[0].data,s.retry_data);h.route(()=>ok(s.complete));await click(h,'refresh');assert.equal(h.get('family-render-files').children.length,2);
  }
  const h=make();await ready(h);h.route(()=>Promise.reject(Error('Runtime status unavailable')));await click(h,'refresh');await ack(h);assert.equal(h.get('family-render-start').disabled,true);h.route(()=>ok(input.happy.initial));await click(h,'refresh');assert.equal(h.get('family-render-start').disabled,false);
 },
 async bindings(){
  const h=make();await ready(h);h.route(()=>ok({...input.happy.initial,source_current:false}));await click(h,'refresh');await ack(h);assert.equal(h.get('family-render-start').disabled,true);assert.ok(h.get('family-render-status').textContent.includes('güncel değil'));assert.equal(postCalls(h).length,0);
  const s=input.failed,q=make(s);await ready(q,s);const limit=clone(s.state);limit.generation=Number.MAX_SAFE_INTEGER;limit.ref.generation=limit.generation;q.route(()=>ok(limit));await click(q,'refresh');await ack(q);assert.equal(q.get('family-render-retry').disabled,true);assert.equal(postCalls(q).length,0);
  const r=make();await r.load();await open(r,input.details[1]);await click(r,'refresh');await ack(r);assert.ok(r.get('family-render-binding').textContent.includes('remotion'));assert.equal(r.get('family-engine').value,'hyperframes');assert.equal(r.get('family-render-start').disabled,false);
  for(const field of ['artifacts_status','prepare_status']){
   const x=make();await x.load();const bad=clone(x.detail);bad[field]='unavailable';bad.files=[];x.respond(c=>c.path==='/api/family-jobs/neutral'?ok(x.listing):c.path.endsWith('/'+bad.job)?ok(bad):undefined);await x.get('family-history-load').emit('click');const i=x.listing.jobs.findIndex(v=>v.job===bad.job);await x.get('family-history-list').children[i].children[0].emit('click');assert.equal(x.get('family-render-panel').hidden,true);assert.equal(postCalls(x).length,0);
  }
 },
 async drafts(){
  const h=make();await h.load();const raw=h.get('family-spec').value+' ';await h.set('family-spec',raw,'input');await h.set('family-claims','[] ','input');await open(h);await click(h,'refresh');await ack(h);seed(h,input.happy.start_data.request_key);h.route(c=>c.data?ok(input.happy.started):ok(input.happy.running));await click(h,'start');assert.equal(h.get('family-spec').value,raw);assert.equal(h.get('family-claims').value,'[] ');
  await h.set('family-engine','remotion');assert.equal(h.get('family-render-panel').hidden,true);assert.equal(h.get('family-spec').value,raw);
  await open(h);assert.equal(h.get('family-render-ack').checked,false);await h.set('family-select','contour-trace');await h.set('family-select','kinetic-grid');assert.equal(h.get('family-spec').value,raw);assert.equal(h.get('family-claims').value,'[] ');
 }
};
for(const name of input.groups){try{await scenarios[name]();passed.push(name);}catch(error){failures.push({group:name,error:error.stack});}}
console.log(JSON.stringify({passed,failures}));if(failures.length)process.exitCode=1;
