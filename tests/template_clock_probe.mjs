// Execute the actual generated HF program, staged bundle and staged GSAP.
// This is an offline DOM model, not a native/browser/pixel acceptance test.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import vm from 'node:vm';

let raw='';for await(const chunk of process.stdin)raw+=chunk;
const {out,times,offGrid=[]}=JSON.parse(raw);
const gsap=createRequire(import.meta.url)(path.join(out,'assets/gsap.min.js')).gsap;
const node=tag=>({tag,attrs:{},children:[],setAttribute(name,value){this.attrs[name]=String(value);},
 appendChild(child){this.children.push(child);return child;},replaceChildren(...children){this.children=children;}});
const mount=node('div');
const document={getElementById(id){assert.equal(id,'family-module');return mount;},
 createElementNS(ns,tag){assert.equal(ns,'http://www.w3.org/2000/svg');return node(tag);},
 createTextNode(text){return {tag:'#text',text};}};
const context=vm.createContext({window:{__timelines:{}},document,gsap});
const plain=n=>n.tag==='#text'?{tag:n.tag,text:n.text}:
 {tag:n.tag,attrs:n.attrs,children:n.children.map(plain)};
const texts=n=>n.tag==='#text'?[n.text]:n.children.flatMap(texts);
try{
 vm.runInContext(fs.readFileSync(path.join(out,'template-registry/bundle.js'),'utf8'),context);
 const api=context.StoryMotionTemplates,compile=api.compileStaged,received=[];
 context.StoryMotionTemplates={...api,compileStaged(spec){const actual=compile(spec);return {...actual,render(seconds){received.push(seconds);return actual.render(seconds);}};}};
 const markup=fs.readFileSync(path.join(out,'index.html'),'utf8');
 const delimiter='<script>(()=>{';assert.equal(markup.split(delimiter).length,2);
 const program=markup.split(delimiter)[1].split('})();</script>')[0];
 const scene=JSON.parse(fs.readFileSync(path.join(out,'template-scene.json'),'utf8'));
 context.sceneJson=JSON.stringify(scene);
 const expected=compile(vm.runInContext('JSON.parse(sceneJson).spec',context));
 vm.runInContext('(()=>{'+program+'})();',context);
 const timeline=context.window.__timelines.root;assert.ok(timeline);
 for(const seconds of times){
  timeline.totalTime(seconds,true);
  const actual=plain(mount.children[0]);
  const wanted=plain(api.svgDom(api.parseSvg(expected.render(seconds)),document));
  assert.deepEqual(texts(actual),texts(wanted),`Cue text mismatch ${scene.family}@${seconds}`);
  assert.ok(JSON.stringify(actual)===JSON.stringify(wanted),`SVG tree mismatch ${scene.family}@${seconds}`);
  assert.equal(received.at(-1),seconds,`Clock did not recover exact frame ${scene.family}@${seconds}`);
 }
 for(const seconds of offGrid){
  timeline.totalTime(seconds,true);
  assert.equal(received.at(-1),seconds,`Arbitrary subframe changed ${scene.family}@${seconds}`);
 }
 timeline.kill();
 console.log(JSON.stringify({samples:times.length,off_grid:offGrid.length,family:scene.family,
  scope:'Actual generated inline program/staged GSAP/bundle and namespaced DOM model; no native render'}));
}finally{gsap.globalTimeline.clear();gsap.ticker.sleep();}
