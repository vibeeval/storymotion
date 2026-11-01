import assert from 'node:assert/strict';
import {harness} from './family_gallery_dom.mjs';
let raw='';for await(const chunk of process.stdin)raw+=chunk;
const input=JSON.parse(raw),clone=v=>JSON.parse(JSON.stringify(v)),ok=v=>({ok:true,json:async()=>clone(v)});
const descendants=n=>n.children.flatMap(c=>[c,...descendants(c)]),button=(h,kind,index=0)=>h.get('family-'+kind+'-cards').children[index].children[0];
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const load=(h,kind)=>h.get('family-'+kind+'-load').emit('click'),choose=(h,id)=>h.set('family-select',id);
function make(){const data=clone(input);for(const f of data.catalog.families)if(!f.profile_ids.includes('second'))f.profile_ids.push('second');
 const h=harness(data);h.genuine=call=>input.metadata[call.path]?ok(input.metadata[call.path]):undefined;h.respond(h.genuine);return h;}
const scenarios={
 async compatibilityReason(){const h=make();await h.load();await load(h,'styles');
  const reason=h.get('family-styles-apply-reason'),apply=h.get('family-styles-apply');
  assert.equal(apply.getAttribute('aria-describedby'),'family-styles-apply-reason');assert.equal(reason.getAttribute('role'),'status');assert.equal(reason.getAttribute('aria-live'),'polite');assert.equal(reason.hidden,true);assert.equal(reason.textContent,'');
  await button(h,'styles').emit('click');assert.equal(apply.disabled,true);assert.equal(reason.hidden,false);assert.ok(reason.textContent.includes('kinetic-grid'));assert.ok(reason.textContent.includes('does not support'));
  await choose(h,'contour-trace');assert.equal(reason.hidden,true);assert.equal(reason.textContent,'');await button(h,'styles').emit('click');assert.equal(apply.disabled,false);assert.equal(reason.hidden,true);assert.equal(reason.textContent,'');
  await choose(h,'torn-edge-layer-transfer');await button(h,'styles',2).emit('click');assert.equal(apply.disabled,true);assert.equal(reason.hidden,false);assert.ok(reason.textContent.includes('torn-edge-layer-transfer'));
  await h.get('family-styles-close').emit('click');assert.equal(reason.hidden,true);assert.equal(reason.textContent,'');
  for(const change of [h=>h.set('family-account','second'),h=>h.set('family-example','1'),h=>h.set('family-engine','remotion'),h=>h.set('family-search','NO_MATCH','input')]){const next=make();await next.load();await load(next,'styles');await button(next,'styles').emit('click');assert.equal(next.get('family-styles-apply-reason').hidden,false);await change(next);assert.equal(next.get('family-styles-apply-reason').hidden,true);assert.equal(next.get('family-styles-apply-reason').textContent,'');}
  assert.ok(!h.calls.some(c=>c.options.method==='POST'));
 },
 async bounds(){for(const overflow of [false,true]){const h=make();await h.load();await choose(h,'contour-trace');
  const spec=JSON.parse(h.get('family-spec').value),palette=input.metadata['/api/style-gallery/neutral'].items[0].palette;
  const base=JSON.stringify(spec),delta=Buffer.byteLength(JSON.stringify(palette,null,2))-Buffer.byteLength(JSON.stringify(spec.parameters.palette));assert.ok(delta>0);
  const target=overflow?100000:100000-delta,raw=base+' '.repeat(target-Buffer.byteLength(base));assert.equal(Buffer.byteLength(raw),target);
  await h.set('family-spec',raw,'input');await load(h,'styles');await button(h,'styles').emit('click');assert.equal(h.get('family-styles-apply').disabled,false);
  const prepare=h.get('family-prepare').disabled,claims=h.get('family-claims').value,editorStatus=h.get('family-editor-status').textContent;
  await h.get('family-styles-apply').emit('click');
  if(overflow){assert.equal(h.get('family-spec').value,raw,'Overflow must retain every original byte');assert.equal(h.get('family-prepare').disabled,prepare);assert.equal(h.get('family-editor-status').textContent,editorStatus);assert.ok(h.get('family-styles-status').textContent.includes('Palette not applied'));}
  else{assert.equal(Buffer.byteLength(h.get('family-spec').value),100000);assert.deepEqual(JSON.parse(h.get('family-spec').value),{...spec,parameters:{...spec.parameters,palette}});assert.ok(h.get('family-styles-status').textContent.includes('Palette applied'));}
  assert.equal(h.get('family-claims').value,claims);assert.ok(!h.calls.some(c=>c.options.method==='POST'));
 }},
 async focus(){for(const kind of ['styles','references']){const h=make();await h.load();await load(h,'styles');await load(h,'references');const other=kind==='styles'?'references':'styles';
  const hold=deferred(),prefix=kind==='styles'?'style-gallery':'reference-catalog';h.respond(c=>c.path.startsWith('/api/'+prefix+'/')?hold.promise:h.genuine(c));const pending=load(h,kind);
  const focused=button(h,other);focused.focus();assert.equal(h.document.activeElement,focused);hold.resolve(ok(input.metadata['/api/'+prefix+'/neutral']));await pending;
  assert.equal(h.document.activeElement,focused,'One gallery reload must not move focus in its sibling');
  const own=deferred();h.respond(c=>c.path.startsWith('/api/'+prefix+'/')?own.promise:h.genuine(c));const next=load(h,kind),item=button(h,kind),id=item.dataset.catalogItem;item.focus();own.resolve(ok(input.metadata['/api/'+prefix+'/neutral']));await next;
  assert.equal(h.document.activeElement.dataset.catalogItem,id);assert.ok(h.get('family-'+kind+'-cards').contains(h.document.activeElement),'Same-section focus must survive card replacement');
 }},
 async browse(){const h=make();assert.equal(h.get('family-references-load').disabled,true);await h.load();await load(h,'references');await load(h,'styles');
  assert.equal(h.get('family-references-cards').children.length,3);assert.equal(h.get('family-styles-cards').children.length,4);assert.ok(h.get('family-count').textContent.includes('91 / 91'));
  await button(h,'references').emit('click');assert.ok(h.get('family-references-meta').textContent.includes('Other asset rights unknown'));assert.ok(h.get('family-references-meta').textContent.includes('Missing preview'));assert.ok(h.get('family-references-meta').textContent.includes('No supported saved planning mapping'));
  const links=descendants(h.get('family-references-meta')).filter(n=>n.tagName==='A');assert.equal(links.length,3);for(const a of links){assert.ok(a.getAttribute('href').startsWith('https://github.com/'));assert.equal(a.getAttribute('rel'),'noopener noreferrer');}
  await h.set('family-references-search','pixel','input');assert.equal(h.get('family-references-cards').children.length,1);assert.equal(h.get('family-references-detail').hidden,true);
  await h.set('family-references-filter','compatible');assert.equal(h.get('family-references-cards').children.length,0);assert.equal(h.get('family-references-empty').hidden,false);
  await h.get('family-references-reset').emit('click');assert.equal(h.get('family-references-cards').children.length,3);
  await h.set('family-references-filter','unknown_rights');assert.equal(h.get('family-references-cards').children.length,3);
  await choose(h,'liquid-merge');await h.set('family-references-filter','compatible');assert.equal(h.get('family-references-cards').children.length,1);
  await button(h,'references').emit('click');await h.get('family-references-close').emit('click');assert.equal(h.get('family-references-detail').hidden,true);assert.equal(h.document.activeElement,button(h,'references'));
  assert.ok(!h.calls.some(c=>c.options.method==='POST'));assert.ok(!h.calls.some(c=>/^https?:/.test(c.path)));
 },
 async apply(){const h=make();await h.load();await choose(h,'contour-trace');
  let spec=h.get('family-spec').value;
  spec=spec.replace(/("duration"\s*:\s*)([0-9.]+)/,'$1$2e0');await h.set('family-spec',spec,'input');
  await h.set('family-claims','[ ]','input');const claims=h.get('family-claims').value;await load(h,'styles');await button(h,'styles',2).emit('click');assert.equal(h.get('family-styles-apply').disabled,false);
  const palette=input.metadata['/api/style-gallery/neutral'].items[2].palette,before=JSON.parse(spec);await h.get('family-styles-apply').emit('click');const after=h.get('family-spec').value;
  assert.deepEqual(JSON.parse(after),{...before,parameters:{...before.parameters,palette}});assert.ok(after.includes('e0'));assert.equal(h.get('family-claims').value,claims);assert.ok(h.get('family-styles-status').textContent.includes('current RAM JSON draft only'));
  assert.ok(!h.calls.some(c=>c.options.method==='POST'));await choose(h,'kinetic-grid');await load(h,'styles');await button(h,'styles').emit('click');assert.equal(h.get('family-styles-apply').disabled,true);
  await choose(h,'contour-trace');assert.equal(h.get('family-spec').value,after);await h.set('family-account','second');assert.notEqual(h.get('family-spec').value,after);await h.set('family-account','neutral');assert.equal(h.get('family-spec').value,after);
  await h.load();assert.equal(h.get('family-spec').value,after);
 },
 async stale(){for(const change of [h=>h.set('family-account','second'),h=>choose(h,'pixel-journey'),h=>h.set('family-example','1'),h=>h.set('family-engine','remotion'),h=>h.set('family-search','NO_MATCH','input')])for(const outcome of ['success','reject']){
   const h=make();await h.load();await choose(h,'contour-trace');const hold=deferred();h.respond(c=>c.path.startsWith('/api/style-gallery/')?hold.promise:h.genuine(c));const old=load(h,'styles');await change(h);h.respond(h.genuine);await load(h,'styles');const status=h.get('family-styles-status').textContent,count=h.get('family-styles-cards').children.length,spec=h.get('family-spec').value;
   if(outcome==='success')hold.resolve(ok(input.metadata['/api/style-gallery/neutral']));else hold.reject(Error('OLD_CONTEXT_ERROR'));await old;
   assert.equal(h.get('family-styles-status').textContent,status);assert.equal(h.get('family-styles-cards').children.length,count);assert.equal(h.get('family-spec').value,spec);assert.equal(h.get('family-styles-apply').disabled,true);
  }
 },
 async malformed(){for(const prefix of ['reference-catalog','style-gallery']){const kind=prefix==='style-gallery'?'styles':'references',base=input.metadata['/api/'+prefix+'/neutral'];
   const mutations=[v=>{v.account='second';},v=>{v.schema_version=true;},v=>{v.count++;},v=>{v.items.push(v.items[0]);v.count++;},v=>{v.actual_render=true;},v=>{v.items[0].extra=true;},v=>{v.items[0].planning_mapping={};},v=>{v.items[0].preview_url='https://example.test/x';},v=>{v.revision='changed';}];
   if(kind==='references')mutations.push(v=>{v.items[0].reference_urls=['javascript:alert(1)'];},v=>{v.items[0].reference_only=1;});else mutations.push(v=>{v.items[0].palette.accent='url(x)';},v=>{v.items[0].family_ids=['missing'];});
   for(const mutate of mutations){const h=make();await h.load();const bad=clone(base);mutate(bad);h.respond(c=>c.path.startsWith('/api/'+prefix+'/')?ok(bad):h.genuine(c));const spec=h.get('family-spec').value;await load(h,kind);assert.ok(h.get('family-'+kind+'-status').textContent.includes('Catalog unavailable'));assert.equal(h.get('family-'+kind+'-cards').children.length,0);assert.equal(h.get('family-spec').value,spec);h.respond(h.genuine);await load(h,kind);assert.equal(h.get('family-'+kind+'-cards').children.length,base.count);}
  }
 },
 async preserve(){const h=make();await h.load();await choose(h,'contour-trace');await load(h,'styles');await button(h,'styles').emit('click');const draft=h.get('family-spec').value;
  await h.set('family-search','NO_MATCH','input');assert.equal(h.get('family-styles-apply').disabled,true);await h.get('family-styles-apply').emit('click');assert.equal(h.get('family-spec').value,draft);await h.get('family-clear-search').emit('click');
  await load(h,'styles');await button(h,'styles').emit('click');const hold=deferred();h.respond(c=>c.path==='/api/template-families/prepare'?hold.promise:h.genuine(c));const submitted=h.get('family-form').emit('submit');assert.equal(h.get('family-styles-apply').disabled,true);await h.get('family-styles-apply').emit('click');assert.equal(h.get('family-spec').value,draft);hold.resolve(ok({account:'neutral',family:'contour-trace',engine:'hyperframes',job:'synthetic'}));await submitted;
  // Real contract fixture is loaded below, then a genuine typed field edit remains pending.
  h.respond(c=>c.path==='/api/template-families/fields'?ok(input.contract):h.genuine(c));await h.get('family-editor-load').emit('click');const node=descendants(h.get('family-editor-fields')).find(n=>n.dataset.path===JSON.stringify(['parameters','width']));assert.ok(node);node.value='300';await node.emit('input');
  await load(h,'styles');await button(h,'styles').emit('click');assert.equal(h.get('family-styles-apply').disabled,true);await h.get('family-styles-apply').emit('click');assert.equal(h.get('family-spec').value,draft);assert.equal(h.get('family-editor-apply').disabled,false);assert.equal(node.value,'300');
 }
};
await scenarios[input.group]();process.stdout.write(JSON.stringify({passed:input.group}));
