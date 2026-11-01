// Conservative layout/seek checks, not browser font boxes or native acceptance.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import * as source from '../renderers/template-registry/modules/bc1bbb0f9f88-baseline-type-reflow.mjs';
import {compileStaged} from '../renderers/template-registry/registry.mjs';

export const reportedTimes=[1.875,2,2.125,2.222,2.25,2.375,2.5,2.625,2.75,2.875,3.111,3.5,3.625,3.875,4,4.125,4.25,4.375,4.5,4.625,4.75,4.875,4.889,5,5.125,5.25,5.375];

export function geometry(spec,api=source,times=null){
 const p=api.validateSpec(spec).parameters,words=p.copy.split(' ');
 times??=[...new Set([...Array.from({length:Math.ceil(p.duration*60)+1},(_,i)=>Math.min(i/60,p.duration)),...reportedTimes.filter(t=>t<=p.duration)])];
 for(const t of times){
  const s=api.sample(spec,t);
  assert.deepEqual(s.tokens.map(v=>v.word),words,`all copy in reading order @${t}`);
  assert.deepEqual(s.anchor,{x:110,y:730});assert.equal(s.tokens[0].x,110);assert.equal(s.tokens[0].y,730);
  for(const v of s.tokens){
   assert.ok([v.x,v.y,v.width,s.fontSize,s.tracking].every(Number.isFinite));
   assert.ok(v.x>=110-1e-7&&v.x+v.width<=960+1e-7,`horizontal field ${v.word}@${t}`);
   assert.ok(v.y>=730&&v.y<=730+8*p.baseline_step,`vertical field ${v.word}@${t}`);
   assert.ok(Math.abs((v.y-730)/p.baseline_step-Math.round((v.y-730)/p.baseline_step))<1e-7,`baseline ${v.word}@${t}`);
  }
  for(let i=0;i<s.tokens.length;i++)for(let j=i+1;j<s.tokens.length;j++){
   const a=s.tokens[i],b=s.tokens[j],dx=Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x),dy=s.fontSize*1.24-Math.abs(a.y-b.y);
   assert.ok(dx<=1e-7||dy<=1e-7,`word overlap ${a.word}/${b.word}@${t}: ${dx}x${dy}`);
  }
 }
 const forward=times.map(t=>JSON.stringify(api.sample(spec,t)));
 assert.deepEqual([...times].reverse().map(t=>JSON.stringify(api.sample(spec,t))).reverse(),forward,'reverse seeks');
 return {frames:times.length,words:words.length};
}

function bundleAPI(bundle){
 const context=vm.createContext({});vm.runInContext(fs.readFileSync(bundle,'utf8'),context);
 return spec=>{context.specJSON=JSON.stringify(spec);return vm.runInContext('StoryMotionTemplates.compileStaged(JSON.parse(specJSON))',context);};
}

if(process.argv[1]&&fileURLToPath(import.meta.url)===process.argv[1]){
 let raw='';for await(const part of process.stdin)raw+=part;const input=JSON.parse(raw);
 if(input.mode==='geometry')console.log(JSON.stringify({rows:input.specs.map(s=>geometry(s))}));
 else if(input.mode==='visible'){
  let frames=0;
  for(const spec of input.specs)for(const t of [0,...reportedTimes,spec.parameters.duration]){
   const svg=source.render(spec,t),tags=[...svg.matchAll(/<text data-motion-role="reflow-word"([^>]*)>/g)];
   assert.equal(tags.length,spec.parameters.copy.split(' ').length);
   assert.ok(!svg.includes('data-layout-allow-overlap'));
   for(const [,attrs]of tags)assert.ok(!/\b(?:opacity|visibility|display|style|mask|clip-path)=/.test(attrs));
   frames++;
  }
  console.log(JSON.stringify({frames}));
 }
 else if(input.mode==='reject'){
  for(const spec of input.specs)assert.throws(()=>source.validateSpec(spec));
  console.log(JSON.stringify({rejected:input.specs.length}));
 }
 else if(input.mode==='endpoints')console.log(JSON.stringify({hashes:input.specs.map(s=>[0,s.parameters.duration].map(t=>createHash('sha256').update(source.render(s,t)).digest('hex')))}));
 else if(input.mode==='parity'){
  const compile=bundleAPI(input.bundle);let frames=0;
  for(const spec of input.specs){
   const esm=compileStaged(spec),hf=compile(spec),times=[0,...reportedTimes.filter(t=>t<=spec.parameters.duration),spec.parameters.duration*.37,spec.parameters.duration*.73,spec.parameters.duration];
   assert.equal(JSON.stringify(esm.spec),JSON.stringify(hf.spec));
   for(const t of [...times,...times.slice().reverse()]){assert.equal(hf.render(t),esm.render(t),`${spec.id}@${t}`);frames++;}
  }
  console.log(JSON.stringify({cases:input.specs.length,frames}));
 }else throw Error('Unknown test mode');
}
