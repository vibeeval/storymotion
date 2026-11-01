// Readonly helper use; no copied runtime, dependency, source-style body or asset.
export {keys,number,choice,text,fitText,textUnits,contrastRatio,esc,fmt,clamp,smooth,lerp,fail,frameSeconds,deepFreeze} from './bf3bbe09120e-shared.mjs';
import {VERSION,validateBase,keys,number,choice,text,fitText,svgText,esc,fmt,clamp,smooth,lerp,fail,sampleTime,activeCue} from './bf3bbe09120e-shared.mjs';
export {VERSION};
export const PALETTES={paper:{background:'#F4F0E7',ink:'#24343B',muted:'#59646B',accent:'#85432E'},night:{background:'#111D29',ink:'#F2EFE7',muted:'#B5C6D2',accent:'#F0AF95'},blue:{background:'#EAF0F4',ink:'#253D50',muted:'#526875',accent:'#315D87'}};
export function meta(name,kind,layout_id,motion_grammar,typographic_hierarchy){return Object.freeze({name,kind,layout_id,motion_grammar,typographic_hierarchy,original_implementation:true,native_verified:false,independent_accepted:false,ui_verified:false,product_integrated:false,strategy:'original_implementation_not_source_code_port'});}
export function base(spec,id,required,defaults,palette){keys(spec,['id','version','parameters'],[],'spec');keys(spec.parameters,['title','duration','narration','cues',...required],['palette'],'parameters');list(spec.parameters.cues,1,24,'cues');return validateBase(spec,id,required,[],palette);}
export function list(v,min,max,name){if(!Array.isArray(v)||Object.getPrototypeOf(v)!==Array.prototype||v.length<min||v.length>max||Array.from({length:v.length},(_,i)=>Object.hasOwn(v,i)).some(x=>!x)||Reflect.ownKeys(v).some(k=>k!=='length'&&(typeof k!=='string'||!/^\d+$/u.test(k)||Number(k)>=v.length||!Object.getOwnPropertyDescriptor(v,k).enumerable||!Object.hasOwn(Object.getOwnPropertyDescriptor(v,k),'value'))))fail(`${name}: dense plain array length ${min}..${max} required`);return v;}
export function point(v,name,lo=0,hi=1){keys(v,['x','y'],[],name);return{x:number(v.x,`${name}.x`,lo,hi),y:number(v.y,`${name}.y`,lo,hi)};}
export function permutation(v,values,name){list(v,values.length,values.length,name);if(v.some(x=>!values.includes(x))||new Set(v).size!==values.length)fail(`${name}: exact permutation required`);return[...v];}
export function copy(v,name,max,width=800,size=34,lines=3){const s=text(v,name,max);fitText(s,{width,maximum:size,minimum:28,maxLines:lines});return s;}
export function done(id,p){return{id,version:VERSION,parameters:p};}
export function time(p,seconds){const t=sampleTime(seconds,p.duration),active=p.duration-.75;return{seconds:t,active,u:clamp(t/active),held:t>=active};}
export const ease=(u,start=0,end=1)=>smooth((u-start)/(end-start));
export function along(points,u){const f=clamp(u)*(points.length-1),i=Math.min(points.length-2,Math.floor(f)),p=f-i;return{x:lerp(points[i].x,points[i+1].x,p),y:lerp(points[i].y,points[i+1].y,p)};}
export function iso(x,y,z=0,origin={x:540,y:940},scale=72){return{x:origin.x+(x-y)*scale,y:origin.y+(x+y)*scale*.5-z};}
export const path=(points,close=false)=>points.map((p,i)=>`${i?'L':'M'}${fmt(p.x)} ${fmt(p.y)}`).join('')+(close?'Z':'');
export const polygon=(points,fill,stroke='none',width=2)=>`<path d="${path(points,true)}" fill="${fill}" stroke="${stroke}" stroke-width="${width}"/>`;
export const line=(a,b,color,width=2,extra='')=>`<path d="${path([a,b])}" fill="none" stroke="${color}" stroke-width="${width}" ${extra}/>`;
export function label(value,x,y,width=800,size=36,fill='#24343B',lines=3,anchor='start'){return svgText(value,{x,y,width,maximum:size,minimum:28,maxLines:lines,fill,anchor});}
export function page(id,p,t,body,{layout='rail',headline=null}={}){
 const c=p.palette,cue=activeCue(p.cues,t),i=cue?p.cues.indexOf(cue):-1;
 const title=layout==='center'?svgText(p.title,{x:540,y:175,width:860,maximum:54,minimum:38,maxLines:4,fill:c.ink,anchor:'middle'}):svgText(p.title,{x:105,y:160,width:850,maximum:layout==='side'?52:60,minimum:38,maxLines:4,fill:c.ink});
 const guide=layout==='side'?`<path d="M88 115V1490" stroke="${c.accent}" stroke-width="7"/>`:layout==='center'?`<path d="M405 490H675" stroke="${c.accent}" stroke-width="4"/>`:`<path d="M105 490H375" stroke="${c.accent}" stroke-width="5"/>`;
 return `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920" role="img" aria-label="${esc(p.title)}" data-renderer="${id}" data-seconds="${fmt(t)}"><rect width="1080" height="1920" fill="${c.background}"/><g font-family="Schibsted, sans-serif">${title}${guide}<g id="motion-body">${body}</g><path d="M100 1580H980" stroke="${c.muted}" stroke-width="1"/>${cue?`<g id="family-cue-${i}" data-cue="true">${label(cue.text,100,1650,880,42,c.ink,3)}</g>`:''}<text x="100" y="1840" fill="${c.muted}" font-size="20">ÖZGÜN YEREL KOD · GÖRSEL İNCELEME BEKLİYOR</text></g></svg>`;
}
