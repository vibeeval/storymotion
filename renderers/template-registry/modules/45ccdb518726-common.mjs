// Original G04 geometry/layout utilities. Only the explicitly allowed B02 data
// validator/text helpers are imported read-only; no dependency or engine copy.
import {validateCueArray,VERSION,validateBase,keys,number,choice,text,fitText,palette,fail,clamp,smooth,lerp,sampleTime,activeCue,esc,fmt,svgText} from './1239407120d9-shared.mjs';
export {VERSION,validateBase,keys,number,choice,text,fitText,palette,fail,clamp,smooth,lerp,sampleTime,activeCue,esc,fmt,svgText};
export const HOLD_SECONDS=.8;
export const radians=degrees=>degrees*Math.PI/180;
export function array(value,name,min,max) {
  if(!Array.isArray(value)||Object.getPrototypeOf(value)!==Array.prototype||value.length<min||value.length>max)fail(`${name}: ${min}–${max} dense items required`);
  const expected=['length',...Array.from({length:value.length},(_,i)=>String(i))];
  if(Reflect.ownKeys(value).some(k=>typeof k!=='string'||!expected.includes(k))||expected.some(k=>!Object.hasOwn(value,k)))fail(`${name}: dense data only`);
  for(let i=0;i<value.length;i++)if(!Object.hasOwn(Object.getOwnPropertyDescriptor(value,String(i)),'value'))fail(`${name}: accessors refused`);
  return value;
}
// Descriptor-only preflight runs before shared normalization or any cue iterator.
function preflightCueInput(spec){
 if(!spec||typeof spec!=='object'||Array.isArray(spec))fail('spec: plain data required');
 const parameters=Object.getOwnPropertyDescriptor(spec,'parameters');
 if(!parameters||!parameters.enumerable||!Object.hasOwn(parameters,'value'))fail('parameters: enumerable data required');
 const raw=parameters.value;
 if(!raw||typeof raw!=='object'||Array.isArray(raw))fail('parameters: plain data required');
 const cues=Object.getOwnPropertyDescriptor(raw,'cues');
 if(!cues||!cues.enumerable||!Object.hasOwn(cues,'value'))fail('cues: enumerable data required');
 validateCueArray(cues.value);
}
export function base(spec,id,required,optional,colors){preflightCueInput(spec);const p=validateBase(spec,id,required,optional,colors);fitText(p.title,{width:900,maximum:58,minimum:40,maxLines:3});return p;}
export const normalized=(id,p)=>({id,version:VERSION,parameters:p});
export function clock(seconds,duration){const time=sampleTime(seconds,duration);return {seconds:time,u:clamp(time/(duration-HOLD_SECONDS))};}
export function project(point,{yaw=25,elevation=28,scale=70,cx=540,cy=1070}={}){
  const a=radians(yaw),e=radians(elevation),x=point.x*Math.cos(a)-point.y*Math.sin(a),y=point.x*Math.sin(a)+point.y*Math.cos(a);
  return {x:cx+scale*x,y:cy+scale*(y*Math.sin(e)-point.z*Math.cos(e))};
}
export function length3(a,b){return Math.hypot(a.x-b.x,a.y-b.y,a.z-b.z);}
export function bounds(points){return {minX:Math.min(...points.map(p=>p.x)),maxX:Math.max(...points.map(p=>p.x)),minY:Math.min(...points.map(p=>p.y)),maxY:Math.max(...points.map(p=>p.y))};}
export function path(points,close=true){return points.map((p,i)=>`${i?'L':'M'}${fmt(p.x)} ${fmt(p.y)}`).join('')+(close?'Z':'');}
export function rotate2(point,angle,cx=0,cy=0){const a=radians(angle);return {x:cx+point.x*Math.cos(a)-point.y*Math.sin(a),y:cy+point.x*Math.sin(a)+point.y*Math.cos(a)};}
export function svg(id,p,seconds,body){return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920" width="1080" height="1920" role="img" aria-label="${esc(p.title)}" data-renderer="${id}" data-seconds="${fmt(seconds)}"><rect width="1080" height="1920" fill="${p.palette.background}"/><g font-family="Schibsted, sans-serif">${body}</g></svg>`;}
export function caption(p,seconds){const cue=activeCue(p.cues,seconds);return cue?svgText(cue.text,{x:90,y:1710,width:900,maximum:42,minimum:30,maxLines:3,fill:p.palette.ink}):'';}
export function line(a,b,color,width=2,extra=''){return `<path d="M${fmt(a.x)} ${fmt(a.y)}L${fmt(b.x)} ${fmt(b.y)}" fill="none" stroke="${color}" stroke-width="${fmt(width)}" ${extra}/>`;}
export const LABEL_SCHEMA={type:'string',maxLength:45};
export const commonMetadata=(name,kind,layout,motion,hierarchy)=>Object.freeze({name,kind,layout_id:layout,motion_grammar:motion,typographic_hierarchy:hierarchy,original_implementation:true,native_verified:false,independent_accepted:false,scope:'Original bounded analytic vectors; no source code, assets or photoreal/physical simulation parity.'});
