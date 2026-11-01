// Original object anatomy drawn on held cels. No shape-to-shape morph or random jitter.
import {VERSION,validateBase,choice,number,text,fitText,windowPair,defaulted,fail,smooth,sampleTime,motionTime,fmt,svgText,frameShell} from './1239407120d9-shared.mjs';
import {path,rotate,bounds,area} from './07c4eb72721d-geometry.mjs';
export const ID='cel-contour-boil',SOURCE_ID='source-mg-style-05-cel-boil';
export const DEFAULT_PALETTE=Object.freeze({background:'#F4F0E5',ink:'#3A332D',muted:'#696051',accent:'#53613E'});
export const PARAMETER_SCHEMA=Object.freeze({object:{enum:['kettle','watering-can']},label:{maxLength:110},hold_frames:{enum:[2,3]},boil_amount:{minimum:.5,maximum:3},stroke_width:{minimum:3,maximum:7},tilt_degrees:{minimum:-18,maximum:18},action_window:{normalized:true,minimumSpan:.3}});
export function validateSpec(spec) {
  const p=validateBase(spec,ID,['object','label'],['hold_frames','boil_amount','stroke_width','tilt_degrees','action_window'],DEFAULT_PALETTE),r=spec.parameters;
  p.object=choice(r.object,'object',['kettle','watering-can']);p.label=text(r.label,'label',110);fitText(p.label,{maximum:38,minimum:28,maxLines:3});
  p.hold_frames=number(defaulted(r.hold_frames,2),'held frames',2,3,true);
  p.boil_amount=number(defaulted(r.boil_amount,1.6),'ink breathing',.5,3);
  p.stroke_width=number(defaulted(r.stroke_width,5),'stroke width',3,7);
  p.tilt_degrees=number(defaulted(r.tilt_degrees,-12),'tilt degrees',-18,18);
  p.action_window=windowPair(defaulted(r.action_window,[.12,.88]),'action window');
  if(p.action_window[1]-p.action_window[0]<.3-1e-9)fail('action window: at least 30% of clip required');
  return {id:ID,version:VERSION,parameters:p};
}
export function objectContour(p,cel) {
  return Array.from({length:64},(_,i)=>{
    const angle=i*Math.PI/32,dx=Math.cos(angle),dy=Math.sin(angle);
    const r=p.object==='kettle'?1/(Math.hypot(dx/175,dy/205)):
      1/Math.pow(Math.abs(dx/170)**6+Math.abs(dy/145)**6,1/6);
    const jitter=p.boil_amount*(Math.sin(i*.71+cel*1.63)+.5*Math.sin(i*1.21-cel*.93))/1.5;
    return {x:dx*(r+jitter),y:dy*(r+jitter)};
  });
}
function state(p,seconds) {
  const time=sampleTime(seconds,p.duration),frame=Math.floor(motionTime(time,p.duration)*30+1e-8),cel=Math.floor(frame/p.hold_frames),heldSeconds=cel*p.hold_frames/30;
  const u=(heldSeconds/p.duration-p.action_window[0])/(p.action_window[1]-p.action_window[0]);
  const pose=smooth(u/.3)*(1-smooth((u-.72)/.28)),angle=p.tilt_degrees*pose,contour=objectContour(p,cel);
  // Conservative convex envelope includes every anatomy Bézier control point.
  const extremities=[{x:-320,y:-240},{x:320,y:-240},{x:320,y:210},{x:-320,y:210}];
  const world=[...contour,...extremities].map(point=>rotate(point,angle,{x:540,y:940}));
  return {seconds:time,frame,cel,heldSeconds,angle,phase:pose===0?'rest':'tilt',contour,path:path(contour),area:area(contour),bounds:bounds(world)};
}
export function sample(spec,seconds) {return state(validateSpec(spec).parameters,seconds);}
export const sampleFrame=sample;
export function render(spec,seconds) {
  const p=validateSpec(spec).parameters,s=state(p,seconds),c=p.palette;
  const anatomy=p.object==='kettle'?'<path d="M-135 -75L-315 -125L-250 -20L-140 55Z"/><path d="M135 -130C320 -185 320 150 130 120M145 -90C255 -125 255 105 145 80" fill="none"/><path d="M-90 -200Q0 -225 90 -200L75 -184H-75Z"/><path d="M-20 -220Q0 -240 20 -220V-210H-20Z"/>':
    '<path d="M-145 65L-320 -180L-280 -220L-90 -70Z"/><path d="M140 -105C315 -200 315 160 140 110M150 -65C250 -110 250 100 150 65" fill="none"/><path d="M-75 -140Q-85 -235 40 -235Q125 -225 105 -145" fill="none"/><path d="M-70 -145H70" fill="none"/>';
  const body=`<path d="M180 1260H900" stroke="${c.muted}" stroke-width="2"/><g transform="translate(540 940) rotate(${fmt(s.angle)})" fill="${c.background}" stroke="${c.ink}" stroke-width="${fmt(p.stroke_width)}" stroke-linejoin="round" stroke-linecap="round">${anatomy}<path data-held-cel="${s.cel}" d="${s.path}"/><path d="M-105 75Q0 125 105 75" stroke="${c.accent}" fill="none"/></g>${svgText(p.label,{y:1375,maximum:38,minimum:28,maxLines:3,fill:c.ink})}`;
  return frameShell(ID,p,s.seconds,body);
}
export const renderFrame=render;
