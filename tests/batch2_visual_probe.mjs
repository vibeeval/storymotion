// Source geometry and seek regressions; these do not certify browser pixels.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import * as aurora from '../renderers/template-registry/modules/b205d5e0ed2f-aurora-refraction-panels.mjs';
import * as ascii from '../renderers/template-registry/modules/7ae25f27401c-ascii-wave-buffer.mjs';
import * as baseline from '../renderers/template-registry/modules/bc1bbb0f9f88-baseline-type-reflow.mjs';
import {textUnits} from '../renderers/template-registry/modules/f2b8a056cce3-shared.mjs';
import {parseSvg} from '../renderers/svg-tree.mjs';

const hash=value=>createHash('sha256').update(value).digest('hex');
const times=p=>[...new Set([0,1.875,2.222,2.875,3.875,4.5,5.375,p.duration,
 ...Array.from({length:Math.ceil(p.duration*60)},(_,i)=>i/60)].filter(t=>t<=p.duration))];
function elements(tree,role){return [tree,...tree.children.flatMap(v=>elements(v,role))].filter(v=>!role||v.attrs['data-motion-role']===role);}
function noSuppression(tree){
 for(const node of elements(tree)){
  assert.ok(!Object.keys(node.attrs).some(k=>k.startsWith('data-layout-allow-')));
  if(['text','tspan'].includes(node.tag))for(const key of ['opacity','visibility','display','mask','clip-path','style'])assert.ok(!(key in node.attrs));
 }
}
function bounds(x,y,width,height,angle,cx,cy){
 const a=angle*Math.PI/180,c=Math.cos(a),s=Math.sin(a),points=[[x,y],[x+width,y],[x,y+height],[x+width,y+height]].map(([px,py])=>({x:cx+(px-cx)*c-(py-cy)*s,y:cy+(px-cx)*s+(py-cy)*c}));
 return{left:Math.min(...points.map(v=>v.x)),right:Math.max(...points.map(v=>v.x)),top:Math.min(...points.map(v=>v.y)),bottom:Math.max(...points.map(v=>v.y))};
}
function auroraGeometry(spec){
 const p=aurora.validateSpec(spec).parameters,clock=times(p);
 for(const t of clock){
  const state=aurora.sample(spec,t),svg=aurora.render(spec,t),tree=parseSvg(svg),labels=elements(tree,'panel-label-line'),boxes=[];
  assert.equal(labels.length,state.panels.reduce((n,v)=>n+v.labelLayout.lines.length,0));noSuppression(tree);
  for(const panel of state.panels){
   const layout=panel.labelLayout,cx=panel.x+panel.width/2,cy=panel.y+panel.height/2;
   assert.equal(layout.lines.join(' '),panel.label);assert.ok(layout.height+20<=panel.height);
   const texts=labels.splice(0,layout.lines.length);
   for(let j=0;j<texts.length;j++){
    const node=texts[j],x=Number(node.attrs.x),y=Number(node.attrs.y),size=Number(node.attrs['font-size']);
    assert.equal(node.children.map(v=>v.text).join(''),layout.lines[j]);
    // Conservative full ascender/descender envelope, then screen-space rotation.
    const box=bounds(x,y-size*1.05,textUnits(layout.lines[j])*size,size*1.4,panel.tilt,cx,cy);
    assert.ok(box.left>=90&&box.right<=990&&box.top>=490&&box.bottom<=1560,`label field @${t}`);boxes.push(box);
   }
  }
  for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++){
   const a=boxes[i],b=boxes[j];assert.ok(Math.min(a.right,b.right)<=Math.max(a.left,b.left)||Math.min(a.bottom,b.bottom)<=Math.max(a.top,b.top),`label overlap @${t}`);
  }
 }
 const selected=[0,1.875,2.222,5.375,p.duration].filter(t=>t<=p.duration);
 assert.deepEqual(selected.map(t=>aurora.render(spec,t)),selected.slice().reverse().map(t=>aurora.render(spec,t)).reverse());
 return clock.length;
}
function asciiGeometry(spec){
 const p=ascii.validateSpec(spec).parameters,clock=times(p);
 for(const t of clock){
  const state=ascii.sample(spec,t),tree=parseSvg(ascii.render(spec,t)),rows=elements(tree,'buffer-row');noSuppression(tree);
  assert.equal(rows.length,20);assert.equal(state.buffer.length,640);
  for(let y=0;y<20;y++){
   const row=rows[y],xs=row.attrs.x.split(' ').map(Number),copy=row.children.map(v=>v.text).join('');
   assert.deepEqual(xs,Array.from({length:32},(_,x)=>124+x*26));assert.equal(copy,state.rows[y]);assert.equal(copy.length,32);
   assert.equal(Number(row.attrs.y),670+y*32);assert.equal(row.attrs['xml:space'],'preserve');assert.ok(!('letter-spacing'in row.attrs));
   // Every cell plus a generous 40px glyph envelope stays inside the 864px panel.
   assert.ok(xs[0]>=108&&xs.at(-1)+40<=972);assert.ok(Number(row.attrs.y)+10<1340);
  }
  assert.ok(state.cursor.x>=0&&state.cursor.x<32&&state.cursor.y>=0&&state.cursor.y<20);
 }
 const selected=[0,1.875,2.222,p.duration];
 assert.deepEqual(selected.map(t=>ascii.render(spec,t)),selected.slice().reverse().map(t=>ascii.render(spec,t)).reverse());
 return clock.length;
}

let raw='';for await(const part of process.stdin)raw+=part;const input=JSON.parse(raw);
if(input.mode==='aurora')console.log(JSON.stringify({frames:input.specs.reduce((n,s)=>n+auroraGeometry(s),0)}));
else if(input.mode==='ascii')console.log(JSON.stringify({frames:input.specs.reduce((n,s)=>n+asciiGeometry(s),0)}));
else if(input.mode==='ascii-state')console.log(JSON.stringify({hashes:input.specs.map(s=>hash(JSON.stringify(times(s.parameters).map(t=>ascii.sample(s,t)))))}));
else if(input.mode==='baseline-heading'){
 let frames=0;
 for(const spec of input.specs){
  const titles=times(spec.parameters).map(t=>{
   const svg=baseline.render(spec,t);frames++;
   const header=svg.slice(svg.indexOf('<g font-family='),svg.indexOf('<g id="motion-body">'));
   assert.ok(!/\b(?:clip-path|mask|transform|opacity|visibility|display|style)=/.test(header));
   return hash(header);
  });assert.equal(new Set(titles).size,1,'static heading must not move, clip or disappear');
 }
 console.log(JSON.stringify({frames}));
}else if(input.mode==='reject'){
 for(const spec of input.specs)assert.throws(()=>({aurora:aurora,ascii:ascii}[input.family]).validateSpec(spec));
 console.log(JSON.stringify({rejected:input.specs.length}));
}else throw Error('Unknown probe mode');
