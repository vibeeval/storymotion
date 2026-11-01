// Original radial contour interpolation. No fonts, glyph outlines or SVG assets.
import {VERSION,defaulted, validateBase, keys, choice, number, text, fitText, fail, smooth, lerp,
  sampleTime, motionTime, fmt, frameShell, svgText} from './cabbfda44beb-shared.mjs';

export const ID = 'shape-morph';
export const SOURCE_ID = 'source-mg-style-08-morph';
export const SHAPES = Object.freeze(['circle','rounded-square','triangle','star']);
export const POINT_COUNT = 120; // divisible by 3 and 10: all polygon vertices have exact slots.
export const DEFAULT_PALETTE = Object.freeze({background:'#F0EDF7',ink:'#30264B',muted:'#726687',accent:'#9160CF'});
export const PARAMETER_SCHEMA = Object.freeze({
  shapes:{minimumItems:2,maximumItems:4,item:{shape:{enum:SHAPES},label:{maxLength:65}}},
  radius:{minimum:160,maximum:300},star_inner:{minimum:0.3,maximum:0.65},
  squareness:{minimum:3,maximum:8},rotation:{minimum:-90,maximum:90},hold_fraction:{minimum:0.1,maximum:0.55},
});
export function validateSpec(spec) {
  const p=validateBase(spec,ID,['shapes'],['radius','star_inner','squareness','rotation','hold_fraction'],DEFAULT_PALETTE);
  const raw=spec.parameters;
  if (!Array.isArray(raw.shapes) || raw.shapes.length<2 || raw.shapes.length>4) fail('shapes: 2–4 steps required');
  p.shapes=raw.shapes.map((item,i)=>{
    keys(item,['shape','label'],[],`shape ${i}`);
    const shape=choice(item.shape,'shape',SHAPES),label=text(item.label,'shape label',65);
    fitText(label,{maximum:38,minimum:28,maxLines:3});
    return {shape,label};
  });
  if (p.shapes.some((item,i)=>i>0 && item.shape===p.shapes[i-1].shape)) fail('adjacent shapes must differ');
  p.radius=number(defaulted(raw.radius,250),'radius',160,300);
  p.star_inner=number(defaulted(raw.star_inner,.46),'star inner radius',.3,.65);
  p.squareness=number(defaulted(raw.squareness,5),'rounded-square exponent',3,8);
  p.rotation=number(defaulted(raw.rotation,0),'rotation',-90,90);
  p.hold_fraction=number(defaulted(raw.hold_fraction,.2),'hold fraction',.1,.55);
  return {id:ID,version:VERSION,parameters:p};
}
const cross=(a,b)=>a.x*b.y-a.y*b.x;
const direction=angle=>({x:Math.sin(angle),y:-Math.cos(angle)});
export function polygonVertices(shape,inner=.46) {
  if (shape!=='triangle' && shape!=='star') fail('polygon shape required');
  number(inner,'star inner radius',.3,.65);
  const count=shape==='triangle'?3:10;
  return Array.from({length:count},(_,i)=>{
    const d=direction(i*Math.PI*2/count),r=shape==='star' && i%2 ? inner:1;
    return {x:d.x*r,y:d.y*r};
  });
}
// Nearest positive ray/edge intersection. Regular triangles and alternating
// radial stars are star-shaped about the origin; angular ordering never flips.
export function polygonRadius(vertices,angle) {
  const ray=direction(angle); let nearest=Infinity;
  for (let i=0;i<vertices.length;i++) {
    const a=vertices[i],b=vertices[(i+1)%vertices.length],edge={x:b.x-a.x,y:b.y-a.y};
    const denominator=cross(ray,edge);
    if (Math.abs(denominator)<1e-12) continue;
    const radius=cross(a,edge)/denominator,along=cross(a,ray)/denominator;
    if (radius>0 && along>=-1e-10 && along<=1+1e-10) nearest=Math.min(nearest,radius);
  }
  if (!Number.isFinite(nearest)) fail('closed contour ray has no intersection');
  return nearest;
}
export function contourPoints(shape,{radius=250,star_inner=.46,squareness=5,rotation=0}={}) {
  choice(shape,'shape',SHAPES); number(radius,'radius',160,300);
  number(star_inner,'star inner radius',.3,.65); number(squareness,'rounded-square exponent',3,8);
  number(rotation,'rotation',-90,90);
  const vertices=shape==='triangle'||shape==='star'?polygonVertices(shape,star_inner):null;
  const turn=rotation*Math.PI/180;
  return Array.from({length:POINT_COUNT},(_,i)=>{
    const angle=i*Math.PI*2/POINT_COUNT;
    let r=1;
    if (shape==='rounded-square') {
      r=Math.pow(Math.abs(Math.sin(angle))**squareness+Math.abs(Math.cos(angle))**squareness,-1/squareness)
        *Math.pow(2,1/squareness-.5);
    } else if (vertices) r=polygonRadius(vertices,angle);
    const d=direction(angle+turn);
    return {x:d.x*r*radius,y:d.y*r*radius};
  });
}
export function signedArea(points) {
  return points.reduce((sum,a,i)=>{const b=points[(i+1)%points.length];return sum+a.x*b.y-b.x*a.y;},0)/2;
}
export function pointsPath(points) {
  if (!Array.isArray(points) || points.length!==POINT_COUNT) fail('fixed contour point count required');
  return points.map((p,i)=>`${i?'L':'M'}${fmt(p.x)} ${fmt(p.y)}`).join('')+'Z';
}
function state(p,seconds) {
  const time=sampleTime(seconds,p.duration),segments=p.shapes.length-1;
  const position=motionTime(time,p.duration)/p.duration*segments,index=Math.min(segments-1,Math.floor(position));
  const local=position-index,blend=smooth((local-p.hold_fraction)/(1-p.hold_fraction));
  const before=contourPoints(p.shapes[index].shape,p),after=contourPoints(p.shapes[index+1].shape,p);
  const points=before.map((a,i)=>({x:lerp(a.x,after[i].x,blend),y:lerp(a.y,after[i].y,blend)}));
  return {seconds:time,fromIndex:index,toIndex:index+1,fromShape:p.shapes[index].shape,
    toShape:p.shapes[index+1].shape,blend,points,path:pointsPath(points),area:signedArea(points),
    activeIndex:blend<.5?index:index+1,phase:blend===0||blend===1?'hold':'morph'};
}
export function sampleFrame(spec,seconds) { return state(validateSpec(spec).parameters,seconds); }
export function renderFrame(spec,seconds) {
  const p=validateSpec(spec).parameters,s=state(p,seconds),c=p.palette;
  const rail=p.shapes.map((item,i)=>{
    const x=180+i*720/(p.shapes.length-1),active=i===s.activeIndex;
    return `<circle cx="${fmt(x)}" cy="1320" r="${active?12:6}" fill="${active?c.accent:c.muted}"/><text x="${fmt(x)}" y="1280" text-anchor="middle" font-size="24" fill="${c.muted}">${i+1}</text>`;
  }).join('');
  const body=`<g transform="translate(540 930)"><circle r="${fmt(p.radius+30)}" fill="none" stroke="${c.muted}" opacity="0.2" stroke-dasharray="3 12"/><path data-contour-points="${POINT_COUNT}" d="${s.path}" fill="${c.accent}" fill-opacity="0.25" stroke="${c.ink}" stroke-width="5" stroke-linejoin="round"/><circle r="4" fill="${c.ink}"/></g><path d="M180 1320H900" stroke="${c.muted}" stroke-width="2"/>${rail}${svgText(p.shapes[s.activeIndex].label,{y:1400,maximum:38,minimum:28,maxLines:3,fill:c.ink})}`;
  return frameShell(ID,p,s.seconds,body);
}

// Direct public aliases retain the original validated frame API.
export const sample=sampleFrame;
export const render=renderFrame;
