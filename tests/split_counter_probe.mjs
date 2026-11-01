// Counter pose/geometry tests. No browser, renderer or font acceptance implied.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import fs from 'node:fs';
import vm from 'node:vm';
import * as source from '../renderers/template-registry/modules/3528802a33d8-split-counter-flip.mjs';
import {parseSvg} from '../renderers/svg-tree.mjs';

const nativeTimes=[0,.125,.444,1.333,1.5,1.625,2.222,3.111,3.625,3.75,3.875,4,4.889,5.365,5.5,5.615,5.778,6.667,7.556,8];
const all=tree=>[tree,...tree.children.flatMap(all)];
const text=node=>node.children.map(v=>v.text??text(v)).join('');
const faces=tree=>all(tree).filter(v=>v.tag==='text'&&v.attrs['font-size']==='140'&&/^\d$/.test(text(v)));
function times(p){return [...new Set([...Array.from({length:p.duration*60+1},(_,i)=>i/60),...nativeTimes.filter(t=>t<=p.duration),
 ...p.milestones.flatMap(v=>[0,.25,.5,.75,1].map(q=>v.at*(p.duration-.75)+q*p.flap_duration))])];}
function expected(p,t){
 const active=p.duration-.75,seconds=Math.max(0,Math.min(p.duration,t));let previous=p.start_value;
 for(const v of p.milestones){
  const start=v.at*active;
  if(seconds<start)return{display:previous,value:previous};
  if(seconds<start+p.flap_duration)return{display:seconds<start+p.flap_duration/2?previous:v.value,value:previous};
  previous=v.value;
 }return{display:previous,value:previous};
}
function geometry(spec){
 const p=source.validateSpec(spec).parameters,clock=times(p);let moving=0,unchanged=0;
 for(const t of clock){
  const state=source.sample(spec,t),svg=source.render(spec,t),tree=parseSvg(svg),digits=faces(tree),want=expected(p,state.seconds);
  assert.equal(digits.length,4,`exactly one digit face in each cell @${t}`);
  // At floating-point event boundaries, compare the phase actually normalized
  // by the existing clock; the explicit native-value table tests those separately.
  if(Math.min(...p.milestones.flatMap(v=>[v.at*state.active,v.at*state.active+p.flap_duration/2,v.at*state.active+p.flap_duration].map(x=>Math.abs(state.seconds-x))))>1e-7){
   assert.equal(digits.map(text).join(''),String(want.display).padStart(4,'0'),`display @${t}`);assert.equal(state.value,want.value,`settled value @${t}`);
  }
  const nodes=all(tree);assert.ok(!nodes.some(n=>Object.keys(n.attrs).some(k=>k.startsWith('data-layout-allow-'))));
  for(const d of digits)for(const key of ['clip-path','mask','style','opacity','visibility','display'])assert.ok(!(key in d.attrs),`digit is not suppressed by ${key}`);
  const groups=nodes.filter(n=>n.attrs['data-motion-role']==='counter-face');assert.equal(groups.length,4);
  const boxes=[];
  for(let i=0;i<4;i++){
   const digit=digits[i],x=Number(digit.attrs.x),y=Number(digit.attrs.y),group=groups[i],s=state.digits[i];
   assert.equal(text(digit),s.progress<.5?s.old:s.next);assert.equal(digit.attrs['text-anchor'],'middle');
   const match=/^translate\(0 845\) scale\(1 ([0-9.]+)\) translate\(0 -845\)$/.exec(group.attrs.transform);assert.ok(match);
   const scale=Number(match[1]);assert.ok(scale>=0&&scale<=1);
   if(s.old===s.next){assert.equal(scale,1,'unchanged digits remain readable during other flips');unchanged++;}
   else{assert.ok(Math.abs(scale-s.hinge)<=.001);if(scale<.99)moving++;}
   // Envelope exceeds all native digit widths (0:88.46, 1:56.6, 2:83.54,
   // 3:84.4, 6:86.18). The full 140px em box remains within its 150px cell.
   const box={left:x-70,right:x+70,top:845+(y-147-845)*scale,bottom:845+(y+42-845)*scale};
   assert.ok(box.left>=180+i*190&&box.right<=330+i*190&&box.top>=740&&box.bottom<=950);boxes.push(box);
  }
  for(let i=1;i<boxes.length;i++)assert.ok(boxes[i-1].right<boxes[i].left,'neighboring faces have separate zones');
  assert.ok(Math.abs(state.panelWidths.reduce((a,b)=>a+b,0)-780)<1e-8);
 }
 assert.ok(moving>0);const selected=nativeTimes.filter(t=>t<=p.duration);
 assert.deepEqual(selected.map(t=>source.render(spec,t)),selected.slice().reverse().map(t=>source.render(spec,t)).reverse());
 return{frames:clock.length,moving,unchanged};
}
let raw='';for await(const part of process.stdin)raw+=part;const input=JSON.parse(raw);
if(input.mode==='geometry')console.log(JSON.stringify({rows:input.specs.map(geometry)}));
else if(input.mode==='native-values'){
 const expectedRows=[[0,'0012',12],[1.333,'0012',12],[1.5,'0012',12],[1.625,'0036',12],[2.222,'0036',36],[3.625,'0036',36],[3.75,'0064',36],[3.875,'0064',64],[4.889,'0064',64],[5.365,'0064',64],[5.5,'0096',64],[5.615,'0096',96],[8,'0096',96]];
 for(const[t,value,settled]of expectedRows){assert.equal(faces(parseSvg(source.render(input.specs[0],t))).map(text).join(''),value);assert.equal(source.sample(input.specs[0],t).value,settled);}
 console.log(JSON.stringify({rows:expectedRows.length}));
}else if(input.mode==='state-hashes')console.log(JSON.stringify({hashes:input.specs.map(s=>createHash('sha256').update(JSON.stringify(Array.from({length:s.parameters.duration*60+1},(_,i)=>source.sample(s,i/60)))).digest('hex'))}));
else if(input.mode==='reject'){
 for(const s of input.specs)assert.throws(()=>source.validateSpec(s));console.log(JSON.stringify({rejected:input.specs.length}));
}else if(input.mode==='parity'){
 const context=vm.createContext({});vm.runInContext(fs.readFileSync(input.bundle,'utf8'),context);let frames=0;
 for(const spec of input.specs){context.spec=JSON.stringify(spec);const compiled=vm.runInContext('StoryMotionTemplates.compileStaged(JSON.parse(spec))',context);
  for(const t of times(spec.parameters)){assert.equal(compiled.render(t),source.render(spec,t));assert.equal(JSON.stringify(vm.runInContext(`StoryMotionTemplates.parseSvg(${JSON.stringify(compiled.render(t))})`,context)),JSON.stringify(parseSvg(source.render(spec,t))));frames++;}}
 console.log(JSON.stringify({frames}));
}else throw Error('Unknown probe mode');
