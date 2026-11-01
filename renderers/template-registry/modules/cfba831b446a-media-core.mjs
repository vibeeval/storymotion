// Original bounded data/geometry utilities. No filesystem, network, timers, evaluation, or engine imports.
import {validateCueArray,validateBase, keys, number, text, choice, fail, fitText, svgText, esc, fmt, smooth, lerp, clamp, sampleTime, deepFreeze, contrastRatio} from './1239407120d9-shared.mjs';
export {keys,number,text,choice,fail,fitText,svgText,esc,fmt,smooth,lerp,clamp,deepFreeze,contrastRatio};
export {path,area,clipHalfPlane} from './07c4eb72721d-geometry.mjs';
export const DEFAULT_PALETTE=deepFreeze({background:'#101B24',ink:'#F4F3E9',muted:'#BBCBD3',accent:'#8CD8EF'});
export const obj=(properties)=>({type:'object',additionalProperties:false,required:Object.keys(properties),properties});
export const num=(minimum,maximum,integer=false)=>({type:integer?'integer':'number',minimum,maximum});
export const str=(maxLength=160)=>({type:'string',minLength:1,maxLength});
export const arr=(items,minItems=1,maxItems=12)=>({type:'array',items,minItems,maxItems});
export const boxSchema=obj({x:num(0,1),y:num(0,1),w:num(.02,1),h:num(.02,1)});
export const pointSchema=obj({x:num(0,1),y:num(0,1)});
export const pathSchema=arr(obj({at:num(0,1),x:num(0,1),y:num(0,1),w:num(.02,1),h:num(.02,1)}),2,8);
export const remapSchema=arr(obj({at:num(0,1),time:num(0,3600)}),2,8);
export const pauseSchema=arr(obj({start:num(0,44),end:num(.1,45)}),0,6);
export const refsSchema=arr(str(36),1,6);
const hexSchema={type:'string',pattern:'^#[0-9a-fA-F]{6}$'};
const gridSchema=obj({width:num(1,8,true),height:num(1,8,true),pixels:arr(hexSchema,1,64)});
const safePathSchema={type:'string',maxLength:180,pattern:'^[A-Za-z0-9][A-Za-z0-9._/-]*$'};
const rightsSchema=obj({owner:str(120),license:str(160),proof:safePathSchema,verification:{enum:['proxy_original','pending']}});
export const mediaSchema=arr(obj({id:str(36),kind:{enum:['video','image','screen','depth']},local_path:safePathSchema,sha256:{type:'string',pattern:'^[0-9a-f]{64}$'},material_class:{enum:['original_rgb_proxy','caller_local_media']},width:num(1,8192,true),height:num(1,8192,true),duration:num(1,3600),rights:rightsSchema,proxy:gridSchema}),1,6);
export function schema(fields){const result=obj({title:str(),duration:num(3,45),narration:str(1500),cues:arr(obj({start:num(0,45),end:num(0,45),text:str(95)}),1,24),media:mediaSchema,...fields,...{palette:{...obj({background:hexSchema,ink:hexSchema,muted:hexSchema,accent:hexSchema}),optional:true}}});result.required=result.required.filter(k=>k!=='palette');delete result.properties.palette.optional;return deepFreeze(result);}
export function list(v,name,min=1,max=12){if(!Array.isArray(v)||v.length<min||v.length>max||Object.keys(v).length!==v.length||Reflect.ownKeys(v).length!==v.length+1)fail(`${name}: dense bounded array required`);for(let i=0;i<v.length;i++){const d=Object.getOwnPropertyDescriptor(v,String(i));if(!d||!Object.hasOwn(d,'value'))fail(`${name}: data entries required`);}return v;}
export function token(v,name='asset'){const s=text(v,name,36);if(!/^[a-z][a-z0-9_-]{0,35}$/u.test(s))fail(`${name}: local token required`);return s;}
export function localPath(v,name='local_path'){const s=text(v,name,180);if(!/^[A-Za-z0-9][A-Za-z0-9._/-]*$/u.test(s)||s.split('/').some(x=>!x||x==='.'||x==='..')||s.startsWith('/')||s.includes('://'))fail(`${name}: safe relative local path required`);return s;}
export function grid(v,name='grid',max=8){keys(v,['width','height','pixels'],[],name);const width=number(v.width,`${name}.width`,1,max,true),height=number(v.height,`${name}.height`,1,max,true);const pixels=list(v.pixels,`${name}.pixels`,width*height,width*height).map(c=>{if(typeof c!=='string'||!/^#[0-9a-fA-F]{6}$/u.test(c))fail(`${name}: RGB hex required`);return c.toUpperCase();});return {width,height,pixels};}
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
export function base(spec,id,fields,defaults=DEFAULT_PALETTE){preflightCueInput(spec);const p=validateBase(spec,id,['media',...fields],[],defaults);if(p.cues[0].start!==0||p.cues.at(-1).end!==p.duration||p.cues.some((q,i)=>q.end-q.start<.6||(i&&q.start!==p.cues[i-1].end))||p.cues.at(-1).start>p.duration-.8)fail('narration cues must cover duration and reserve the final readable hold');const media=list(spec.parameters.media,'media',1,6).map((m,i)=>{keys(m,['id','kind','local_path','sha256','material_class','width','height','duration','rights','proxy'],[],`media ${i}`);keys(m.rights,['owner','license','proof','verification'],[],'rights');const id=token(m.id);if(typeof m.sha256!=='string'||!/^([0-9a-f]{64})$/u.test(m.sha256))fail('media sha256 required');return {id,kind:choice(m.kind,'kind',['video','image','screen','depth']),local_path:localPath(m.local_path),sha256:m.sha256,material_class:choice(m.material_class,'material_class',['original_rgb_proxy','caller_local_media']),width:number(m.width,'media width',1,8192,true),height:number(m.height,'media height',1,8192,true),duration:number(m.duration,'media duration',1,3600),rights:{owner:text(m.rights.owner,'owner',120),license:text(m.rights.license,'license',160),proof:localPath(m.rights.proof,'rights proof'),verification:choice(m.rights.verification,'rights verification',['proxy_original','pending'])},proxy:grid(m.proxy)};});if(new Set(media.map(m=>m.id)).size!==media.length)fail('unique media IDs required');for(const m of media)if((m.material_class==='original_rgb_proxy')!==(m.rights.verification==='proxy_original'))fail('proxy rights cannot verify caller media');return {...p,media};}
export function asset(p,id){const a=p.media.find(m=>m.id===id);if(!a)fail(`unknown media handle ${id}`);return a;}
export function ref(v,p,name='media reference'){const id=token(v,name);asset(p,id);return id;}
export function refs(v,p,name='clip order',min=1,max=6){return list(v,name,min,max).map(x=>ref(x,p,name));}
export function box(v,name='crop'){keys(v,['x','y','w','h'],[],name);const b={x:number(v.x,`${name}.x`,0,1),y:number(v.y,`${name}.y`,0,1),w:number(v.w,`${name}.w`,.02,1),h:number(v.h,`${name}.h`,.02,1)};if(b.x+b.w>1+1e-9||b.y+b.h>1+1e-9)fail(`${name}: outside source`);return b;}
export function point(v,name='point'){keys(v,['x','y'],[],name);return {x:number(v.x,`${name}.x`,0,1),y:number(v.y,`${name}.y`,0,1)};}
export const FULL=deepFreeze({x:0,y:0,w:1,h:1});
export function cropPath(v,name='crop_path'){const out=list(v,name,2,8).map(k=>{keys(k,['at','x','y','w','h'],[],name);const {at,...b}=k;return {at:number(at,'path time',0,1),...box(b,name)};});ordered(out.map(x=>x.at),name,0,1);return out;}
export function ordered(v,name,start,end){if(v[0]!==start||v.at(-1)!==end||v.some((x,i)=>i&&x<=v[i-1]))fail(`${name}: ordered endpoints ${start},${end} required`);return v;}
export function cuts(v,count,duration,name='cuts'){const out=list(v,name,count+1,count+1).map(x=>number(x,name,0,duration));ordered(out,name,0,duration);if(out.some((x,i)=>i&&x-out[i-1]<.8-1e-8))fail(`${name}: each shot at least .8s`);return out;}
export function remap(v,maxTime,name='time_remap'){const a=list(v,name,2,8).map(k=>{keys(k,['at','time'],[],name);return {at:number(k.at,'remap at',0,1),time:number(k.time,'remap time',0,maxTime)};});ordered(a.map(x=>x.at),name,0,1);if(a.some((k,i)=>i&&k.time<a[i-1].time))fail('source time must be monotone');return a;}
export function pauses(v,duration,name='pauses'){let end=0;return list(v,name,0,6).map(q=>{keys(q,['start','end'],[],name);const a=number(q.start,'pause start',0,duration-.8),b=number(q.end,'pause end',0,duration-.8);if(a<end||b-a<.2||b-a>duration/2)fail('ordered bounded pause required');end=b;return {start:a,end:b};});}
export function cueArray(v,duration,name,min=1,max=8){let end=0;return list(v,name,min,max).map(q=>{keys(q,['start','end','text'],[],name);const a=number(q.start,`${name}.start`,0,duration),b=number(q.end,`${name}.end`,0,duration);if(a<end||b-a<.6||a>duration-1.1)fail(`${name}: readable cues before final hold required`);end=b;const value=text(q.text,`${name}.text`,120);fitText(value,{width:880,maximum:48,minimum:30,maxLines:4});return {start:a,end:b,text:value};});}
export function track(v,name='track'){const a=list(v,name,2,12).map(k=>{keys(k,['at','x','y'],[],name);return {at:number(k.at,'track at',0,1),...point({x:k.x,y:k.y})};});ordered(a.map(x=>x.at),name,0,1);return a;}
export function interpolate(keys,u,properties){u=clamp(u);let i=keys.findIndex(k=>k.at>=u);if(i<=0)return Object.fromEntries(properties.map(k=>[k,keys[0][k]]));if(i<0)i=keys.length-1;const a=keys[i-1],b=keys[i],q=smooth((u-a.at)/(b.at-a.at));return Object.fromEntries(properties.map(k=>[k,lerp(a[k],b[k],q)]));}
export const cropAt=(keys,u)=>interpolate(keys,u,['x','y','w','h']);
export const pointAt=(keys,u)=>interpolate(keys,u,['x','y']);
export function sourceAt(keys,u){u=clamp(u);let i=keys.findIndex(k=>k.at>=u);if(i<=0)return keys[0].time;if(i<0)i=keys.length-1;const a=keys[i-1],b=keys[i];return lerp(a.time,b.time,clamp((u-a.at)/(b.at-a.at)));}
export function clock(p,seconds){const end=p.duration-.8,t=Math.min(sampleTime(seconds,p.duration),end);return {t,u:t/end,end};}
export function pauseClock(t,windows){return t-windows.reduce((n,q)=>n+Math.max(0,Math.min(t,q.end)-q.start),0);}
export function cutIndex(cutCues,t){let i=0;while(i<cutCues.length-2&&t>=cutCues[i+1])i++;return i;}
export const rect=(x,y,w,h)=>({x,y,w,h});
export function layer(p,id,sourceTime,crop,target,extra={}){const a=asset(p,id);const time=number(sourceTime,'source time',0,a.duration);box(crop);for(const k of ['x','y','w','h'])number(target[k],`target ${k}`,0,k==='x'||k==='w'?1080:1920);return {asset_id:id,local_path:a.local_path,sha256:a.sha256,source_time:time,crop:{...crop},target:{...target},opacity:1,transform:{dx:0,dy:0,scale:1,rotation:0},...extra};}
export function projected(b,target,pt){return {x:target.x+(pt.x-b.x)/b.w*target.w,y:target.y+(pt.y-b.y)/b.h*target.h};}
export function translateCropToPoint(crop,sourcePoint,targetPoint){const b={...crop,x:sourcePoint.x-targetPoint.x*crop.w,y:sourcePoint.y-targetPoint.y*crop.h};return box(b,'continuity alignment');}
export function metadata(name,layout_id,motion_grammar,typographic_hierarchy){return deepFreeze({name,kind:'caller-local-media-pipeline',layout_id,motion_grammar,typographic_hierarchy,original_implementation:true,implementation_strategy:'original_implementation_not_source_code_port',native_verified:false,ui_verified:false,independent_accepted:false,real_media_verified:false,proxy_only_evidence:true});}
export function svg(id,p,body){return `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920" role="img" aria-label="${esc(p.title)}" data-renderer="${esc(id)}"><rect width="1080" height="1920" fill="${p.palette.background}"/><g font-family="sans-serif">${body}</g></svg>`;}
export const tx=(value,x,y,width=900,size=52,color='#F4F3E9',lines=4)=>svgText(value,{x,y,width,maximum:size,minimum:Math.min(30,size),maxLines:lines,fill:color});
export const panel=(b,color,opacity=1)=>`<rect x="${fmt(b.x)}" y="${fmt(b.y)}" width="${fmt(b.w)}" height="${fmt(b.h)}" fill="${esc(color)}" opacity="${fmt(opacity)}"/>`;
export function cueText(p,t){return p.cues.find(c=>t>=c.start&&t<c.end)?.text??'';}
export function subtitle(p,t,y=1660,x=80,width=920,size=42){const s=cueText(p,t);return s?panel(rect(x-16,y-48,width+32,210),p.palette.background)+tx(s,x,y,width,size,p.palette.ink,3):'';}
export function proxyMark(p,y=1870){return tx('TEKNİK RGB KARE · GERÇEK MEDYA KABULÜ BEKLİYOR',64,y,952,24,p.palette.muted,2);}
export function validateFrames(frames){if(frames===undefined)return [];return list(frames,'local frames',1,36).map(f=>{keys(f,['asset_id','source_time','frame'],[],'local frame');return {asset_id:token(f.asset_id),source_time:number(f.source_time,'frame time',0,3600),frame:grid(f.frame,'local RGB frame',64)};});}
// Caller supplies decoded RGB cells as plain data. Handles/paths are never dereferenced here.
export function drawLayer(p,l,key,frames){const decoded=validateFrames(frames);for(const f of decoded){const a=asset(p,f.asset_id);if(f.source_time>a.duration)fail('caller frame beyond source duration');}const supplied=decoded.find(f=>f.asset_id===l.asset_id&&Math.abs(f.source_time-l.source_time)<=1/60);if(frames!==undefined&&!supplied)fail('caller frame missing for exact frame request');const g=supplied?.frame??asset(p,l.asset_id).proxy,b=l.crop,t=l.target;const clip=`clip-${key}`;const polygon=l.mask?.map(pt=>`${fmt(pt.x)},${fmt(pt.y)}`).join(' ');const mask=l.mask!==undefined?(polygon?`<polygon points="${polygon}"/>`:''):panel(t,'#FFFFFF');const tr=l.transform;const cx=t.x+t.w/2,cy=t.y+t.h/2;let cells='';for(let j=0;j<g.height;j++)for(let i=0;i<g.width;i++){const x=i/g.width,y=j/g.height,w=1/g.width,h=1/g.height;if(x+w<=b.x||x>=b.x+b.w||y+h<=b.y||y>=b.y+b.h)continue;cells+=panel(rect(t.x+(x-b.x)/b.w*t.w,t.y+(y-b.y)/b.h*t.h,w/b.w*t.w+.05,h/b.h*t.h+.05),g.pixels[j*g.width+i]);}const blur=l.blur??0;const fid=`blur-${key}`;return `<defs><clipPath id="${clip}">${mask}</clipPath><clipPath id="${clip}-bounds">${panel(t,'#FFFFFF')}</clipPath>${blur?`<filter id="${fid}" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="${fmt(blur)}"/></filter>`:''}</defs><g clip-path="url(#${clip}-bounds)"><g clip-path="url(#${clip})" opacity="${fmt(l.opacity)}"><g transform="translate(${fmt(tr.dx)} ${fmt(tr.dy)}) translate(${fmt(cx)} ${fmt(cy)}) rotate(${fmt(tr.rotation)}) scale(${fmt(tr.scale)}) translate(${fmt(-cx)} ${fmt(-cy)})"${blur?` filter="url(#${fid})"`:''}>${cells}</g></g></g>`;}
export function drawLayers(p,layers,prefix,frames){return layers.map((l,i)=>drawLayer(p,l,`${prefix}-${i}`,frames)).join('');}
export function assertTextLayout(p,width=900,size=62,lines=4){fitText(p.title,{width,maximum:size,minimum:38,maxLines:lines});return p;}
