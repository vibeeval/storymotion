import {base,number,list,copy,done,time,fmt,esc,fitText,textUnits,page,PALETTES,meta} from './f2b8a056cce3-shared.mjs';
export const ID='aurora-refraction-panels',SOURCE_ID='source-mg-style-12-aurora-glass',DEFAULT_PALETTE=PALETTES.blue;
export const METADATA=meta('Kırılan alan ve açılı paneller','vector-refraction','staggered-panels','seeded analytic ribbons displaced inside tilted masks','spine title / diagonal labels / field behind panels');
export const PARAMETER_SCHEMA={field_seed:[1,999],flow_rate:[.3,1.2],panel_tilt:[-18,18],refraction_amount:[12,36],panels:{minItems:2,maxItems:3,labelMaxLength:42}};
export function validateSpec(spec){const p=base(spec,ID,['field_seed','flow_rate','panel_tilt','refraction_amount','panels'],{},DEFAULT_PALETTE),r=spec.parameters;p.field_seed=number(r.field_seed,'field seed',1,999,true);p.flow_rate=number(r.flow_rate,'flow',.3,1.2);p.panel_tilt=number(r.panel_tilt,'tilt',-18,18);p.refraction_amount=number(r.refraction_amount,'refraction',12,36);p.panels=list(r.panels,2,3,'panels').map(v=>copy(v,'panel label',42,350,32,2));return done(ID,p);}
function labelLayout(p,name){
 const fit=fitText(name,{width:350,maximum:32,minimum:28,maxLines:2}),angle=Math.abs(p.panel_tilt)*Math.PI/180;
 const width=Math.max(...fit.lines.map(line=>textUnits(line)*fit.fontSize)),glyphHeight=fit.fontSize*1.4;
 // Tilt adds width*sin(angle) to a line's screen-space height. Reserve that
 // clearance at the configured maximum angle; text stays on its panel.
 const leading=glyphHeight+width*Math.tan(angle)+12/Math.cos(angle);
 return{lines:fit.lines,fontSize:fit.fontSize,leading,height:glyphHeight+(fit.lines.length-1)*leading};
}
function state(p,seconds){const q=time(p,seconds),phase=q.u*p.flow_rate*Math.PI*2,tilt=p.panel_tilt*Math.sin(Math.PI*q.u),bands=Array.from({length:3},(_,j)=>Array.from({length:13},(_,i)=>({x:100+i*73,y:690+j*230+Math.sin(i*.52+phase+p.field_seed*.17+j)*55}))),panels=p.panels.map((name,i)=>({x:145+i*185,y:550+i*330,width:405,height:280,tilt:tilt*(i%2?-1:1),shift:p.refraction_amount*Math.sin(phase+i*.7),label:name,labelLayout:labelLayout(p,name)}));return{...q,phase,tilt,blur:Math.abs(tilt)/6,bands,panels};}
export const sample=(spec,seconds)=>state(validateSpec(spec).parameters,seconds);
export function render(spec,seconds){const p=validateSpec(spec).parameters,s=state(p,seconds),c=p.palette,ribbons=(shift=0)=>s.bands.map((band,j)=>`<polyline points="${band.map(v=>`${fmt(v.x+shift)},${fmt(v.y)}`).join(' ')}" fill="none" stroke="${j%2?c.muted:c.accent}" stroke-width="${28+j*10}" stroke-linejoin="round" opacity="0.42"/>`).join('');let body=`<defs><filter id="arp-blur" x="-5%" y="-5%" width="110%" height="110%"><feGaussianBlur stdDeviation="${fmt(s.blur)}"/></filter></defs><g filter="url(#arp-blur)">${ribbons()}</g>`;body+=s.panels.map((v,i)=>{
 const label=v.labelLayout,cy=v.y+v.height/2,plateHeight=Math.max(100,label.height+20);
 const lines=label.lines.map((line,j)=>`<text data-motion-role="panel-label-line" x="${v.x+26}" y="${fmt(cy-(label.lines.length-1)*label.leading/2+label.fontSize*.35+j*label.leading)}" fill="${c.ink}" font-size="${label.fontSize}" font-weight="600">${esc(line)}</text>`).join('');
 return`<defs><clipPath id="arp-${i}"><rect x="${v.x}" y="${v.y}" width="${v.width}" height="${v.height}" rx="12"/></clipPath></defs><g transform="rotate(${fmt(v.tilt)} ${v.x+v.width/2} ${v.y+v.height/2})"><rect x="${v.x}" y="${v.y}" width="${v.width}" height="${v.height}" rx="12" fill="${c.background}" opacity="0.86"/><g clip-path="url(#arp-${i})"><g filter="url(#arp-blur)">${ribbons(v.shift)}</g></g><rect x="${v.x}" y="${v.y}" width="${v.width}" height="${v.height}" rx="12" fill="none" stroke="${c.ink}" stroke-width="2"/><rect x="${v.x+16}" y="${fmt(cy-plateHeight/2)}" width="370" height="${fmt(plateHeight)}" fill="${c.background}"/>${lines}</g>`;
 }).join('');return page(ID,p,s.seconds,body,{layout:'side'});}
