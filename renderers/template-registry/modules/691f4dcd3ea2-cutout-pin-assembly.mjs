// Original layered cutouts rotate around fixed material pins; no free card flight.
import {VERSION,validateBase,keys,choice,number,text,fitText,windowPair,defaulted,fail,smooth,sampleTime,motionTime,fmt,svgText,frameShell} from './1239407120d9-shared.mjs';
import {rotate,bounds,path} from './07c4eb72721d-geometry.mjs';
export const ID='cutout-pin-assembly',SOURCE_ID='source-mg-style-06-collage';
export const DEFAULT_PALETTE=Object.freeze({background:'#F4EDE2',ink:'#352F2C',muted:'#6D5E53',accent:'#93452E'});
export const PARAMETER_SCHEMA=Object.freeze({pieces:{minItems:2,maxItems:4,item:{shape:{enum:['arch','ticket','wedge']},label:{maxLength:45},hinge:{enum:['left','right']},final_angle:{minimum:-6,maximum:6}}},fold_angle:{minimum:24,maximum:32},assembly_window:{normalized:true,minimumSpan:.3}});
export function validateSpec(spec) {
  const p=validateBase(spec,ID,['pieces'],['fold_angle','assembly_window'],DEFAULT_PALETTE),r=spec.parameters;
  if(!Array.isArray(r.pieces)||r.pieces.length<2||r.pieces.length>4)fail('pieces: 2–4 original panels required');
  p.pieces=r.pieces.map(item=>{
    keys(item,['shape','label','hinge','final_angle']);const label=text(item.label,'piece label',45);fitText(label,{width:320,maximum:30,minimum:26,maxLines:2});
    return {shape:choice(item.shape,'piece shape',['arch','ticket','wedge']),label,hinge:choice(item.hinge,'hinge',['left','right']),final_angle:number(item.final_angle,'final angle',-6,6)};
  });
  p.fold_angle=number(defaulted(r.fold_angle,28),'fold angle',24,32);
  p.assembly_window=windowPair(defaulted(r.assembly_window,[.08,.84]),'assembly window');
  if(p.assembly_window[1]-p.assembly_window[0]<.3-1e-9)fail('assembly window: at least 30% required');
  return {id:ID,version:VERSION,parameters:p};
}
export function panelGeometry(shape,hinge) {
  const sign=hinge==='left'?1:-1,points=shape==='ticket'?
    [{x:-26,y:-26},{x:370,y:-26},{x:394,y:-2},{x:394,y:130},{x:370,y:154},{x:-2,y:154},{x:-26,y:130}]:
    shape==='wedge'?[{x:-26,y:24},{x:394,y:-26},{x:394,y:154},{x:-26,y:154}]:
    [{x:-26,y:70},{x:-26,y:-26},{x:394,y:-26},{x:394,y:154},{x:-26,y:154}];
  const mirrored=points.map(p=>({x:p.x*sign,y:p.y}));
  const outline=shape==='arch'?`M${fmt(-26*sign)} 154V70Q${fmt(-26*sign)} -26 ${fmt(70*sign)} -26H${fmt(298*sign)}Q${fmt(394*sign)} -26 ${fmt(394*sign)} 70V154Z`:path(mirrored);
  return {outline,points:mirrored,sign};
}
function state(p,seconds) {
  const time=sampleTime(seconds,p.duration),start=p.assembly_window[0],span=p.assembly_window[1]-start,u=motionTime(seconds,p.duration)/p.duration;
  const pieces=p.pieces.map((piece,i)=>{
    const progress=smooth((u-start-i*span*.16)/(span*.45)),sign=piece.hinge==='left'?1:-1;
    const angle=piece.final_angle+sign*p.fold_angle*(1-progress),pivot={x:sign===1?350:730,y:660+i*160};
    const geometry=panelGeometry(piece.shape,piece.hinge),world=geometry.points.map(point=>rotate(point,angle,pivot));
    const shadow=world.map(point=>({x:point.x+7,y:point.y+8}));
    return {index:i,progress,angle,pivot,geometry,world,bounds:bounds([...world,...shadow]),labelOpacity:smooth((progress-.72)/.28)};
  });
  return {seconds:time,phase:pieces.every(piece=>piece.progress===1)?'assembled':pieces.every(piece=>piece.progress===0)?'waiting':'assembly',pieces};
}
export function sample(spec,seconds) {return state(validateSpec(spec).parameters,seconds);}
export const sampleFrame=sample;
export function render(spec,seconds) {
  const p=validateSpec(spec).parameters,s=state(p,seconds),c=p.palette;
  const layers=s.pieces.map(piece=>{
    const {pivot,angle,geometry,index}=piece,labelX=geometry.sign===1?20:-340;
    return `<g transform="translate(${pivot.x+7} ${pivot.y+8}) rotate(${fmt(angle)})" opacity="0.18"><path d="${geometry.outline}" fill="${c.muted}"/></g><g transform="translate(${pivot.x} ${pivot.y}) rotate(${fmt(angle)})"><path d="${geometry.outline}" fill="${c.background}" stroke="${c.ink}" stroke-width="4" stroke-linejoin="round"/><path d="M${geometry.sign*24} 118H${geometry.sign*330}" stroke="${c.accent}" stroke-width="5"/><g opacity="${fmt(piece.labelOpacity)}">${svgText(p.pieces[index].label,{x:labelX,y:56,width:320,maximum:30,minimum:26,maxLines:2,fill:c.ink})}</g></g><circle data-fixed-pin="${index}" cx="${pivot.x}" cy="${pivot.y}" r="12" fill="${c.accent}" stroke="${c.ink}" stroke-width="2"/>`;
  }).join('');
  return frameShell(ID,p,s.seconds,`<path d="M240 1510H840" stroke="${c.muted}" stroke-width="2"/>${layers}`);
}
export const renderFrame=render;
