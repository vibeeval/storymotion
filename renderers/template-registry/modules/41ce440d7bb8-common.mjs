// Original group-local validation and SVG primitives. Frozen B02 helpers are read-only.
export * from './bf3bbe09120e-shared.mjs';
import {validateBase,keys,number,text,choice,fail,deepFreeze,fitText,svgText,esc,fmt,activeCue,sampleTime,smooth,lerp} from './bf3bbe09120e-shared.mjs';
export const LIGHT=deepFreeze({background:'#F4F1E8',ink:'#1B2530',muted:'#56606B',accent:'#77512E'});
export const COOL=deepFreeze({background:'#EFF3F5',ink:'#182B39',muted:'#4F6575',accent:'#245E83'});
export const ROSE=deepFreeze({background:'#F9EFEA',ink:'#342A35',muted:'#6E5663',accent:'#92502E'});
export const DARK=deepFreeze({background:'#111A18',ink:'#D5F6DF',muted:'#9FBEAB',accent:'#ADF1C2'});
export const N=(min,max,integer=false)=>({type:'number',minimum:min,maximum:max,integer});
export const T=(maxLength=64)=>({type:'string',minLength:1,maxLength});
export const E=(...values)=>({type:'string',enum:values});
export const A=(items,minItems,maxItems=minItems)=>({type:'array',items,minItems,maxItems});
export const O=properties=>({type:'object',properties,required:Object.keys(properties),additionalProperties:false});
export const P=(x0=180,x1=900,y0=600,y1=1400)=>O({x:N(x0,x1),y:N(y0,y1)});
export const HEX={type:'string',format:'hex',maxLength:7};
const COMMON={title:T(160),duration:N(3,45),narration:T(1500),cues:A(O({start:N(0,45),end:N(0,45),text:T(95)}),1,24),palette:O({background:HEX,ink:HEX,muted:HEX,accent:HEX})};
export function schema(fields){return deepFreeze({...O({...COMMON,...fields}),required:['title','duration','narration','cues',...Object.keys(fields)],frame_rate:30,output:{width:1080,height:1920},final_hold_seconds:0.8});}
function field(value,rule,name){
 if(rule.enum)return choice(value,name,rule.enum);
 if(rule.type==='number')return number(value,name,rule.minimum,rule.maximum,rule.integer);
 if(rule.type==='string'){
  if(rule.format==='hex'){if(typeof value!=='string'||!/^#[0-9A-Fa-f]{6}$/u.test(value))fail(`${name}: six-digit hex required`);return value.toUpperCase();}
  if(rule.format==='ascii-ramp'){if(typeof value!=='string'||value.length<4||value.length>12||!/^[\x21-\x7E]+$/u.test(value)||new Set(value).size!==value.length)fail(`${name}: 4–12 unique printable ASCII characters required`);return value;}
  return text(value,name,rule.maxLength);
 }
 if(rule.type==='array'){
  if(!Array.isArray(value)||value.length<rule.minItems||value.length>rule.maxItems||Object.getPrototypeOf(value)!==Array.prototype)fail(`${name}: bounded plain array required`);
  const own=Reflect.ownKeys(value);if(own.length!==value.length+1||own.some(k=>k!=='length'&&(typeof k!=='string'||!/^\d+$/u.test(k)||!Object.hasOwn(Object.getOwnPropertyDescriptor(value,k),'value'))))fail(`${name}: dense data-only array required`);
  return Array.from(value,(v,i)=>field(v,rule.items,`${name}[${i}]`));
 }
 keys(value,rule.required,[],name);return Object.fromEntries(Object.entries(rule.properties).map(([k,r])=>[k,field(value[k],r,`${name}.${k}`)]));
}
export function parameters(spec,id,fields,defaults){keys(spec,['id','version','parameters'],[],'spec');keys(spec.parameters,['title','duration','narration','cues',...Object.keys(fields)],['palette'],'parameters');field(spec.parameters.cues,COMMON.cues,'cues');const p=validateBase(spec,id,Object.keys(fields),[],defaults);for(const [k,r]of Object.entries(fields))p[k]=field(spec.parameters[k],r,k);return p;}
export function metadata(name,layout,motion,hierarchy){return deepFreeze({name,kind:'original_svg_state',layout_id:layout,motion_grammar:motion,typographic_hierarchy:hierarchy,original_implementation:true,implementation_strategy:'original_implementation_not_source_code_port',native_verified:false,ui_verified:false,independent_accepted:false,broad_classifier_axis_parity:false});}
export const unit=(p,t)=>Math.min(sampleTime(t,p.duration),p.duration-0.8)/(p.duration-0.8);
export const at=(u,a,b)=>smooth((u-a)/(b-a));
export const mixPoint=(a,b,q)=>({x:lerp(a.x,b.x,q),y:lerp(a.y,b.y,q)});
export function bezier(a,b,c,u){return{x:(1-u)**2*a.x+2*(1-u)*u*b.x+u*u*c.x,y:(1-u)**2*a.y+2*(1-u)*u*b.y+u*u*c.y};}
export function listPath(points,closed=false){return points.map((p,i)=>`${i?'L':'M'}${fmt(p.x)} ${fmt(p.y)}`).join('')+(closed?'Z':'');}
export const dot=(p,r,fill,extra='')=>`<circle cx="${fmt(p.x)}" cy="${fmt(p.y)}" r="${fmt(r)}" fill="${fill}" ${extra}/>`;
export const segment=(a,b,stroke,width=3,extra='')=>`<path d="${listPath([a,b])}" fill="none" stroke="${stroke}" stroke-width="${fmt(width)}" ${extra}/>`;
export const box=(x,y,w,h,fill,extra='')=>`<rect x="${fmt(x)}" y="${fmt(y)}" width="${fmt(w)}" height="${fmt(h)}" fill="${fill}" ${extra}/>`;
export const path=(points,fill,stroke='none',width=1,extra='')=>`<path d="${listPath(points,true)}" fill="${fill}" stroke="${stroke}" stroke-width="${fmt(width)}" ${extra}/>`;
export function label(s,x,y,c,size=25,extra=''){return`<text x="${fmt(x)}" y="${fmt(y)}" fill="${c}" font-size="${size}" ${extra}>${esc(s)}</text>`;}
export function caption(p,t,options={}){const c=activeCue(p.cues,Math.min(sampleTime(t,p.duration),p.duration-1e-8));return c?`<g data-caption="true">${svgText(c.text,{x:90,y:1680,width:900,maximum:42,minimum:30,maxLines:3,fill:p.palette.ink,...options})}</g>`:'';}
export function svg(id,p,t,body,font='sans-serif'){return`<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920" role="img" aria-label="${esc(p.title)}" data-family="${id}" data-seconds="${fmt(sampleTime(t,p.duration))}"><rect width="1080" height="1920" fill="${p.palette.background}"/><g font-family="${font}">${body}</g></svg>`;}
export const headline=(p,options={})=>svgText(p.title,{x:90,y:210,width:900,maximum:60,minimum:38,maxLines:4,fill:p.palette.ink,...options});
export function ensure(condition,message){if(!condition)fail(message);}
export function signedArea(points){return points.reduce((a,p,i)=>{const q=points[(i+1)%points.length];return a+p.x*q.y-q.x*p.y;},0)/2;}
export const distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
export function hash(seed,index){let x=(seed^Math.imul(index+1,0x9E3779B1))>>>0;x=Math.imul(x^(x>>>16),0x85EBCA6B)>>>0;x=Math.imul(x^(x>>>13),0xC2B2AE35)>>>0;return((x^(x>>>16))>>>0)/4294967296;}
