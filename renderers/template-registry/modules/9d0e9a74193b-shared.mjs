import * as B from './bf3bbe09120e-shared.mjs';
export {keys,number,text,choice,fitText,contrastRatio,esc,fmt,svgText,smooth,clamp} from './bf3bbe09120e-shared.mjs';
export const HOLD = 0.8;
export function lerp(a,b,t){return t<=0?a:t>=1?b:a+(b-a)*t;}
export function arr(v,n,lo=1,hi=16){if(!Array.isArray(v)||Object.getPrototypeOf(v)!==Array.prototype||v.length<lo||v.length>hi||Reflect.ownKeys(v).length!==v.length+1)B.fail(`${n}: dense ordinary array ${lo}..${hi}`);for(let i=0;i<v.length;i++){const d=Object.getOwnPropertyDescriptor(v,String(i));if(!d||!d.enumerable||!Object.hasOwn(d,'value'))B.fail(`${n}: dense data elements required`);}return v;}
export function pt(v,n='point'){arr(v,n,2,2);return v.map((x,i)=>B.number(x,`${n}.${i}`,0,1));}
export function pts(v,n='points',lo=2,hi=12){return arr(v,n,lo,hi).map((x,i)=>pt(x,`${n}.${i}`));}
export function nums(v,n,lo,hi,min=1,max=16){return arr(v,n,min,max).map((x,i)=>B.number(x,`${n}.${i}`,lo,hi));}
export function order(v,n,length){arr(v,n,length,length);const a=v.map((x,i)=>B.number(x,`${n}.${i}`,0,length-1,true));if(new Set(a).size!==length)B.fail(`${n}: permutation required`);return a;}
export function words(v,n,values,min=1,max=8){return arr(v,n,min,max).map((x,i)=>B.choice(x,`${n}.${i}`,values));}
export function color(v,n){if(typeof v!=='string'||!/^#[0-9a-f]{6}$/i.test(v))B.fail(`${n}: hex color`);return v.toUpperCase();}
export function colors(v,n,min=2,max=5){return arr(v,n,min,max).map((x,i)=>color(x,`${n}.${i}`));}
export function label(v,n='label'){const t=B.text(v,n,48);B.fitText(t,{width:260,maximum:34,minimum:28,maxLines:3});return t;}
const TITLE_LAYOUT={
 'engraved-hatch-growth':'specimen','single-path-identity':'folio','pictogram-limb-transition':'side','perspective-pen-wash':'folio','stroke-erase-explanation':'board','crayon-stroke-fill':'poster','halftone-evidence-lens':'specimen','paint-ridge-deposition':'folio','ink-diffusion-front':'side','ink-drum-misregister':'press','pigment-pool-drying':'folio','paper-lightbox-parallax':'lightbox','page-hinge-popups':'board','negative-space-cut':'side','screenprint-layer-pull':'press','lead-cell-lightpass':'lightbox','woodblock-wave-layers':'poster','carved-groove-print':'folio'};
export function base(spec,id,fields,palette){B.keys(spec,['id','version','parameters'],[],'spec');B.keys(spec.parameters,['title','duration','narration','cues',...fields],['palette'],'parameters');arr(spec.parameters.cues,'cues',1,24);for(const c of spec.parameters.cues)B.keys(c,['start','end','text'],[],'cue');const p=B.validateBase(spec,id,fields,[],palette),slot=layouts[TITLE_LAYOUT[id]];if(!slot)B.fail('title layout missing');B.fitText(p.title,{width:slot.w,maximum:slot.size,minimum:38,maxLines:slot.lines});return p;}
export function schema(fields){return B.deepFreeze({type:'object',additionalProperties:false,required:['title','duration','narration','cues',...Object.keys(fields)],properties:{title:{type:'string',maxLength:160},duration:{type:'number',minimum:3,maximum:45,multipleOf:1/30},narration:{type:'string',maxLength:1500},cues:{type:'array',minItems:1,maxItems:24,items:{type:'object',additionalProperties:false,required:['start','end','text'],properties:{start:{type:'number',minimum:0},end:{type:'number',minimum:0},text:{type:'string',maxLength:95}}}},palette:{type:'object',additionalProperties:false,required:['background','ink','muted','accent'],properties:Object.fromEntries(['background','ink','muted','accent'].map(k=>[k,{type:'string',pattern:'^#[0-9A-Fa-f]{6}$'}]))},...fields}});}
export const N=(lo,hi,integer=false)=>({type:integer?'integer':'number',minimum:lo,maximum:hi});
export const A=(items,lo=1,hi=16)=>({type:'array',minItems:lo,maxItems:hi,items});
export const E=values=>({type:'string',enum:values});
export const O=fields=>({type:'object',additionalProperties:false,required:Object.keys(fields),properties:fields});
export const P=A(N(0,1),2,2);export const L={type:'string',maxLength:48};export const C={type:'string',pattern:'^#[0-9A-Fa-f]{6}$'};
export function clock(p,seconds){const t=B.sampleTime(seconds,p.duration);return B.clamp(t/(p.duration-HOLD));}
export const phase=(u,a=0,b=1)=>B.smooth((u-a)/(b-a));
export const xy=([x,y])=>[150+780*x,520+860*y];
export function line(a,b,stroke,width=3,opacity=1){return `<path d="M${a.map(B.fmt).join(' ')}L${b.map(B.fmt).join(' ')}" fill="none" stroke="${stroke}" stroke-width="${B.fmt(width)}" opacity="${B.fmt(opacity)}" stroke-linecap="round"/>`;}
export function path(points,close=false){return 'M'+points.map((p,i)=>(i?'L':'')+p.map(B.fmt).join(' ')).join('')+(close?'Z':'');}
export const poly=(points,fill,stroke='none',width=1,opacity=1)=>`<path d="${path(points,true)}" fill="${fill}" stroke="${stroke}" stroke-width="${B.fmt(width)}" opacity="${B.fmt(opacity)}" stroke-linejoin="round"/>`;
export const circ=(x,y,rad,fill,stroke='none',sw=1,opacity=1)=>`<circle cx="${B.fmt(x)}" cy="${B.fmt(y)}" r="${B.fmt(rad)}" fill="${fill}" stroke="${stroke}" stroke-width="${B.fmt(sw)}" opacity="${B.fmt(opacity)}"/>`;
export const rect=(x,y,w,h,fill,stroke='none',sw=1,rx=0)=>`<rect x="${B.fmt(x)}" y="${B.fmt(y)}" width="${B.fmt(w)}" height="${B.fmt(h)}" rx="${B.fmt(rx)}" fill="${fill}" stroke="${stroke}" stroke-width="${B.fmt(sw)}"/>`;
export function captionLabel(t,x,y,fill,width=260){return B.svgText(t,{x,y,width,maximum:34,minimum:28,maxLines:3,fill,weight:500});}
const layouts={specimen:{x:90,y:190,w:900,size:58,lines:3},folio:{x:90,y:1430,w:900,size:52,lines:3},board:{x:90,y:180,w:900,size:62,lines:3},poster:{x:120,y:220,w:840,size:72,lines:3},lightbox:{x:110,y:235,w:860,size:54,lines:3},press:{x:90,y:200,w:820,size:58,lines:3},side:{x:100,y:250,w:840,size:56,lines:3}};
export function shell(id,p,seconds,body,layout='specimen'){
 const a=layouts[layout];if(!a)B.fail('layout');const t=B.sampleTime(seconds,p.duration);const cue=B.activeCue(p.cues,t===p.duration?t-1e-9:t);const c=p.palette;
 return `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920" role="img" aria-label="${B.esc(p.title)}" data-family="${id}" data-layout="${layout}" data-duration="${B.fmt(p.duration)}"><rect width="1080" height="1920" fill="${c.background}"/><g font-family="Schibsted, sans-serif">${layout==='press'?rect(65,465,950,1000,'none',c.muted,2):layout==='lightbox'?rect(95,480,890,960,'none',c.muted,3,20):layout==='specimen'?line([90,440],[990,440],c.muted,1):layout==='folio'?line([90,1355],[990,1355],c.muted,1):''}${B.svgText(p.title,{x:a.x,y:a.y,width:a.w,maximum:a.size,minimum:38,maxLines:a.lines,fill:c.ink,weight:layout==='poster'?800:600})}${body}${cue?B.svgText(cue.text,{x:95,y:1690,width:890,maximum:44,minimum:30,maxLines:3,fill:c.ink,weight:500}):''}</g></svg>`;
}
export function normalizedPolygon(v,n,min=3,max=8){return pts(v,n,min,max);}
export function permuteCheck(v,n,length){return order(v,n,length);}
export function polar(cx,cy,rx,ry,count=32){return Array.from({length:count},(_,i)=>[cx+Math.cos(i/count*2*Math.PI)*rx,cy+Math.sin(i/count*2*Math.PI)*ry]);}
