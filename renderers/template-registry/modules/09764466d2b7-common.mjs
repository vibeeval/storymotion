// Readonly B02 validation/text primitives; all group geometry below is original.
export {VERSION,keys,number,choice,text,fitText,palette,esc,fmt,svgText,clamp,smooth,lerp,deepFreeze,frameSeconds,contrastRatio} from './bf3bbe09120e-shared.mjs';
import {VERSION,validateBase,keys,number,text,fitText,esc,fmt,svgText,activeCue,sampleTime,clamp,smooth,lerp,deepFreeze,fail} from './bf3bbe09120e-shared.mjs';
export {fail};
export const DEFAULT=Object.freeze({background:'#F3F2E9',ink:'#202F35',muted:'#526169',accent:'#80522F'});
export const DARK=Object.freeze({background:'#17232D',ink:'#F2F2E5',muted:'#BACBCE',accent:'#EAC66E'});
export function base(spec,id,required,optional,colors=DEFAULT){keys(spec,['id','version','parameters'],[],'spec');keys(spec.parameters,['title','duration','narration','cues',...required],[...optional,'palette'],'parameters');list(spec.parameters.cues,'cues',1,24,v=>v);if(Object.hasOwn(spec.parameters,'palette')&&spec.parameters.palette===undefined)fail('palette: explicit undefined is not a color object');return validateBase(spec,id,required,optional,colors);}
export const result=(id,p)=>deepFreeze({id,version:VERSION,parameters:p});
export function list(value,name,min,max,map){if(!Array.isArray(value)||Object.getPrototypeOf(value)!==Array.prototype||value.length<min||value.length>max)fail(name+': bounded plain array required');const names=Reflect.ownKeys(value);if(names.length!==value.length+1||names.some(k=>typeof k!=='string'||(k!=='length'&&!/^(0|[1-9][0-9]*)$/.test(k))))fail(name+': dense array without extra properties required');for(let i=0;i<value.length;i++){const d=Object.getOwnPropertyDescriptor(value,String(i));if(!d||!Object.hasOwn(d,'value'))fail(name+': array data items required');}return value.map(map);}
export function label(value,name='label',maximum=65,width=840,lines=3){const s=text(value,name,maximum);fitText(s,{width,maximum:40,minimum:28,maxLines:lines});return s;}
export function point(value,name='point',low=0,high=1){keys(value,['x','y'],[],name);return{x:number(value.x,name+'.x',low,high),y:number(value.y,name+'.y',low,high)};}
export function ordered(values,name,min,max){const a=list(values,name,min,max,v=>number(v,name,0,1));if(a.some((v,i)=>i&&v<=a[i-1]))fail(name+': strictly increasing required');return a;}
export function context(spec,seconds){const p=spec.parameters,t=sampleTime(seconds,p.duration),active=p.duration-.8;return{p,t,u:clamp(t/active),active,hold:t>=active};}
export function metadata(name,kind,layout,motion,hierarchy){return deepFreeze({name,kind,layout_id:layout,motion_grammar:motion,typographic_hierarchy:hierarchy,original_implementation:true,strategy:'original_implementation_not_source_code_port',source_code_copied:false,native_verified:false,ui_verified:false,independent_accepted:false,product_registered:false});}
export const rect=(x,y,w,h,fill,rx=0,stroke='none',sw=0)=>`<rect x="${fmt(x)}" y="${fmt(y)}" width="${fmt(w)}" height="${fmt(h)}" rx="${fmt(rx)}" fill="${fill}" stroke="${stroke}" stroke-width="${fmt(sw)}"/>`;
export const circle=(x,y,r,fill,stroke='none',sw=0)=>`<circle cx="${fmt(x)}" cy="${fmt(y)}" r="${fmt(r)}" fill="${fill}" stroke="${stroke}" stroke-width="${fmt(sw)}"/>`;
export const line=(x1,y1,x2,y2,color,width=4)=>`<line x1="${fmt(x1)}" y1="${fmt(y1)}" x2="${fmt(x2)}" y2="${fmt(y2)}" stroke="${color}" stroke-width="${fmt(width)}" stroke-linecap="round"/>`;
export const polygon=(points,fill,stroke='none',width=0)=>`<polygon points="${points.map(p=>fmt(p.x)+','+fmt(p.y)).join(' ')}" fill="${fill}" stroke="${stroke}" stroke-width="${fmt(width)}" stroke-linejoin="round"/>`;
export const txt=(value,x,y,width=880,size=40,fill='#202F35',lines=3,anchor='start')=>svgText(value,{x,y,width,maximum:size,minimum:28,maxLines:lines,fill,anchor});
export function page(id,p,t,body,{layout='workbench',note='Özgün geometri · inceleme bekliyor'}={}){
 const c=p.palette,head={workbench:[90,158,900,62,4,'start'],arcade:[90,150,900,56,4,'start'],theatre:[540,182,900,66,3,'middle'],technical:[80,145,920,58,4,'start'],triptych:[90,165,900,60,3,'start']}[layout];
 if(!head)fail('unknown fixed layout');const cue=activeCue(p.cues,t);
 let headerFont=head[3];while(headerFont>28&&fitText(p.title,{width:head[2],maximum:headerFont,minimum:28,maxLines:head[4]}).height>225)headerFont--;const header=txt(p.title,head[0],head[1],head[2],headerFont,c.ink,head[4],head[5]);
 const accentRule=layout==='arcade'?rect(90,440,900,12,c.accent):layout==='technical'?line(80,430,1000,430,c.muted,2):layout==='theatre'?line(360,448,720,448,c.accent,5):line(90,440,990,440,c.muted,2);
 return `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920" role="img" aria-label="${esc(p.title)}" data-renderer="${id}" data-seconds="${fmt(t)}" data-layout="${layout}">${rect(0,0,1080,1920,c.background)}<g font-family="sans-serif">${header}${accentRule}<g id="graphic">${body}</g><g id="captions">${cue?txt(cue.text,90,1680,900,42,c.ink,3):''}</g>${txt(note,90,1850,900,28,c.muted,1)}</g></svg>`;
}
export function route(points,u){const lengths=points.slice(1).map((p,i)=>Math.hypot(p.x-points[i].x,p.y-points[i].y));const total=lengths.reduce((a,b)=>a+b,0);if(total<1e-9)return{...points[0],segment:0,local:0};let d=clamp(u)*total;for(let i=0;i<lengths.length;i++){if(d<=lengths[i]||i===lengths.length-1){const q=lengths[i]?d/lengths[i]:0;return{x:lerp(points[i].x,points[i+1].x,q),y:lerp(points[i].y,points[i+1].y,q),segment:i,local:q};}d-=lengths[i];}return{...points.at(-1),segment:lengths.length-1,local:1};}
export function joint(origin,length,degrees){const a=degrees*Math.PI/180;return{x:origin.x+Math.sin(a)*length,y:origin.y+Math.cos(a)*length};}
export function segment(origin,length,degrees){return[origin,joint(origin,length,degrees)];}
export function rig(shoulder,elbow,hip=0,knee=0){const neck={x:0,y:0},pelvis={x:0,y:70},armStart={x:24,y:18},armMid=joint(armStart,48,shoulder),hand=joint(armMid,44,shoulder+elbow),legStart={x:14,y:70},legMid=joint(legStart,56,hip),foot=joint(legMid,50,hip+knee);return{neck,pelvis,armStart,armMid,hand,legStart,legMid,foot};}
export const distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
export function pair(value,name,low,high){return list(value,name,2,2,v=>number(v,name,low,high));}
export function mixPose(a,b,u){return Object.fromEntries(Object.keys(a).map(k=>[k,typeof a[k]==='number'?lerp(a[k],b[k],u):u<.5?a[k]:b[k]]));}
export function rotateY(v,degrees){const a=degrees*Math.PI/180;return{x:v.x*Math.cos(a)+v.z*Math.sin(a),y:v.y,z:-v.x*Math.sin(a)+v.z*Math.cos(a)};}
export function project(v,degrees,cx=540,cy=1150,scale=1){const r=rotateY(v,degrees);return{x:cx+r.x*scale,y:cy-r.y*scale+r.z*.24*scale};}
