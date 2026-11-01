import {fmt,fail} from './1239407120d9-shared.mjs';
export function path(points,closed=true) {
  if(!Array.isArray(points)||points.length<2) return '';
  return points.map((p,i)=>`${i?'L':'M'}${fmt(p.x)} ${fmt(p.y)}`).join('')+(closed?'Z':'');
}
export function area(points) {
  return Math.abs(points.reduce((sum,p,i)=>{const q=points[(i+1)%points.length];return sum+p.x*q.y-p.y*q.x;},0)/2);
}
export function bounds(points) {
  if(!points.length) fail('nonempty geometry required');
  return {left:Math.min(...points.map(p=>p.x)),right:Math.max(...points.map(p=>p.x)),top:Math.min(...points.map(p=>p.y)),bottom:Math.max(...points.map(p=>p.y))};
}
export function rotate(point,degrees,pivot={x:0,y:0}) {
  const a=degrees*Math.PI/180,c=Math.cos(a),s=Math.sin(a);
  return {x:pivot.x+point.x*c-point.y*s,y:pivot.y+point.x*s+point.y*c};
}
export function clipHalfPlane(points,nx,ny,limit,keepLess=true) {
  const output=[],value=p=>nx*p.x+ny*p.y-limit,inside=v=>keepLess?v<=1e-9:v>=-1e-9;
  for(let i=0;i<points.length;i++) {
    const a=points[i],b=points[(i+1)%points.length],va=value(a),vb=value(b),ia=inside(va),ib=inside(vb);
    if(ia)output.push({...a});
    if(ia!==ib) {
      const t=va/(va-vb);output.push({x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t});
    }
  }
  return output.filter((p,i,all)=>i===0||Math.hypot(p.x-all[i-1].x,p.y-all[i-1].y)>1e-8);
}
