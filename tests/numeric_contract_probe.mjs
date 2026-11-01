import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {compileStaged} from '../renderers/template-registry/registry.mjs';
import {parseSvg} from '../renderers/svg-tree.mjs';
let raw='';for await(const chunk of process.stdin)raw+=chunk;
const {cases,bundle=false}=JSON.parse(raw),results=[];
let compile=compileStaged,realm=null;
if(bundle){realm=vm.createContext({});vm.runInContext(fs.readFileSync('./renderers/template-registry/bundle.js','utf8'),realm);
 compile=(spec,row)=>{realm.rawSpec=JSON.stringify(spec);realm.hydrate=JSON.stringify({kind:row.nativeValue,path:row.path});return vm.runInContext(`(()=>{const spec=JSON.parse(rawSpec),h=JSON.parse(hydrate);if(h.kind){let p=spec.parameters;for(const k of h.path.slice(0,-1))p=p[k];p[h.path.at(-1)]={nan:NaN,infinity:Infinity,negativeInfinity:-Infinity}[h.kind];}return StoryMotionTemplates.compileStaged(spec);})()`,realm);};}
for(const row of cases){
 const spec=row.spec;
 if(row.nativeValue){let target=spec.parameters;for(const key of row.path.slice(0,-1))target=target[key];
 target[row.path.at(-1)]={nan:NaN,infinity:Infinity,negativeInfinity:-Infinity}[row.nativeValue];}
 try{
  const compiled=compile(spec,row),p=compiled.spec.parameters;
  if(row.valid===false){results.push({name:row.name,unexpected_accept:true});continue;}
  const numeric=spec.id==='dimension-construction'?['dimension_values']:spec.id==='glass-section-orbit'?['wall_thickness','height','outer_radius','ior']:['domain_bounds','series_values'];
  for(const key of numeric)assert.equal(JSON.stringify(p[key]),JSON.stringify(spec.parameters[key]),`Numeric input changed: ${row.name}/${key}`);
  const times=[0,p.duration/3,p.duration/2,p.duration,p.duration/3,0,p.duration],frames=[];
  for(const seconds of times){
   const svg=compiled.render(seconds),tree=parseSvg(svg),labels=[],nodes=[];
   const walk=n=>{if(n.attrs?.['data-full-text']){labels.push(n.attrs['data-full-text']);nodes.push(n);}for(const c of n.children??[])walk(c);};walk(tree);
   const expected=spec.id==='dimension-construction'?[
    `W · Genişlik ${p.dimension_values.width} mm`,`H · Yükseklik ${p.dimension_values.height} mm`,`D · Derinlik ${p.dimension_values.depth} mm`]:
    spec.id==='glass-section-orbit'?[`Duvar ${p.wall_thickness} birim`,`Kırılma indisi ${p.ior}`]:row.ticks;
   for(const text of expected??[]){assert.ok(labels.includes(text),`Exact numeric label missing: ${row.name}/${text}`);
    const a=nodes.find(n=>n.attrs['data-full-text']===text).attrs,w=Number(a['data-slot-width']),x=Number(a.x),left=a['text-anchor']==='end'?x-w:a['text-anchor']==='middle'?x-w/2:x;
    assert.ok(Number(a['font-size'])>=28&&left>=80&&left+w<=1000,`Unreadable/outside numeric slot: ${row.name}`);
    assert.ok(Number(a.y)+Number(a['data-estimated-height'])<=1580,`Numeric slot overlaps captions: ${row.name}`);
   }
   frames.push(svg);
  }
  assert.equal(frames[0],frames[5]);assert.equal(frames[1],frames[4]);assert.equal(frames[3],frames[6]);
  results.push({name:row.name,ok:true,frames:times.length});
 }catch(error){results.push({name:row.name,error:String(error.message)});}
}
console.log(JSON.stringify(results));
