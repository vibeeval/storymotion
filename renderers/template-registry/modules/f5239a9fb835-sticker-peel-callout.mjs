// Original diagonal peel mask, reflected back face and one anchored explanation.
import {VERSION,validateBase,choice,number,text,fitText,windowPair,defaulted,fail,phaseAt,smooth,sampleTime,motionTime,fmt,esc,svgText,frameShell} from './1239407120d9-shared.mjs';
import {clipHalfPlane,path,area,bounds} from './07c4eb72721d-geometry.mjs';
export const ID='sticker-peel-callout',SOURCE_ID='source-mg-style-19-paperclip';
export const DEFAULT_PALETTE=Object.freeze({background:'#EDF1F3',ink:'#253643',muted:'#5A6771',accent:'#345C86'});
export const PANEL=Object.freeze({x:170,y:740,width:740,height:460});
export const PARAMETER_SCHEMA=Object.freeze({headline:{maxLength:80},reveal_label:{maxLength:12},note:{maxLength:120},side:{enum:['left','right']},peel_depth:{minimum:260,maximum:350},curl:{minimum:.08,maximum:.18},peel_window:{normalized:true,minimumSpan:.3}});
export function validateSpec(spec) {
  const p=validateBase(spec,ID,['headline','reveal_label','note','side'],['peel_depth','curl','peel_window'],DEFAULT_PALETTE),r=spec.parameters;
  p.headline=text(r.headline,'sticker headline',80);fitText(p.headline,{width:470,maximum:48,minimum:34,maxLines:4});
  p.reveal_label=text(r.reveal_label,'reveal label',12);fitText(p.reveal_label,{width:140,maximum:28,minimum:24,maxLines:1});
  p.note=text(r.note,'note',120);fitText(p.note,{width:800,maximum:36,minimum:28,maxLines:3});
  p.side=choice(r.side,'peel side',['left','right']);p.peel_depth=number(defaulted(r.peel_depth,310),'peel depth',260,350);
  p.curl=number(defaulted(r.curl,.12),'curl',.08,.18);p.peel_window=windowPair(defaulted(r.peel_window,[.16,.76]),'peel window');
  if(p.peel_window[1]-p.peel_window[0]<.3-1e-9)fail('peel window: at least 30% required');
  return {id:ID,version:VERSION,parameters:p};
}
export function peelGeometry(depth,side,curl=.12) {
  const {width:w,height:h}=PANEL,rectangle=[{x:0,y:0},{x:w,y:0},{x:w,y:h},{x:0,y:h}],limit=w-depth;
  const front=clipHalfPlane(rectangle,1,-1,limit),removed=depth>1e-8?clipHalfPlane(rectangle,1,-1,limit,false):[];
  const back=removed.map(p=>({x:p.y+limit,y:p.x-limit}));
  const mirror=p=>({x:side==='left'?w-p.x:p.x,y:p.y});
  const crease=[{x:limit,y:0},{x:w-depth/2-depth*curl,y:depth/2+depth*curl},{x:w,y:depth}].map(mirror);
  return {front:front.map(mirror),removed:removed.map(mirror),back:back.map(mirror),crease,
    frontArea:area(front),removedArea:area(removed),backArea:area(back),panelArea:w*h,
    bounds:bounds([...front,...removed,...back].map(mirror))};
}
function state(p,seconds) {
  const time=sampleTime(seconds,p.duration),progress=phaseAt(motionTime(time,p.duration),p.duration,p.peel_window),depth=p.peel_depth*progress;
  return {seconds:time,progress,depth,phase:progress===0?'front':progress===1?'revealed':'peel',noteOpacity:smooth((progress-.55)/.45),geometry:peelGeometry(depth,p.side,p.curl)};
}
export function sample(spec,seconds) {return state(validateSpec(spec).parameters,seconds);}
export const sampleFrame=sample;
export function render(spec,seconds) {
  const p=validateSpec(spec).parameters,s=state(p,seconds),c=p.palette,g=s.geometry,right=p.side==='right';
  const [a,q,b]=g.crease,headlineX=right?50:220,tipX=right?910:170,railX=right?960:120,noteX=right?110:170;
  const crease=s.depth>1e-8?`<path d="M${fmt(a.x)} ${fmt(a.y)}Q${fmt(q.x)} ${fmt(q.y)} ${fmt(b.x)} ${fmt(b.y)}" fill="none" stroke="${c.accent}" stroke-width="3"/>`:'';
  const body=`<defs><clipPath id="sp-front"><path d="${path(g.front)}"/></clipPath><clipPath id="sp-under"><path d="${path(g.removed)}"/></clipPath></defs><g transform="translate(${PANEL.x} ${PANEL.y})"><rect width="740" height="460" fill="${c.background}" stroke="${c.muted}" stroke-width="2"/><g clip-path="url(#sp-under)">${svgText(p.reveal_label,{x:right?576:24,y:54,width:140,maximum:28,minimum:24,maxLines:1,fill:c.ink})}</g><g clip-path="url(#sp-front)"><rect width="740" height="460" fill="${c.background}"/>${svgText(p.headline,{x:headlineX,y:184,width:470,maximum:48,minimum:34,maxLines:4,fill:c.ink})}</g><path data-front-face="true" d="${path(g.front)}" fill="none" stroke="${c.ink}" stroke-width="4"/>${g.back.length?`<path data-back-face="true" d="${path(g.back)}" fill="${c.background}" stroke="${c.ink}" stroke-width="3"/><path d="${path(g.back)}" fill="${c.muted}" opacity="0.14"/>`:''}${crease}</g><g opacity="${fmt(s.noteOpacity)}"><path d="M${tipX} 740H${railX}V1310H${noteX}" fill="none" stroke="${c.accent}" stroke-width="3"/><circle cx="${tipX}" cy="740" r="6" fill="${c.accent}"/>${svgText(p.note,{x:noteX,y:1380,width:800,maximum:36,minimum:28,maxLines:3,fill:c.ink})}</g>`;
  return frameShell(ID,p,s.seconds,body);
}
export const renderFrame=render;
