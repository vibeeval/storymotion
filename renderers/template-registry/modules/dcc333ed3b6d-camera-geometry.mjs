// Orthographic camera paired with G04's existing screen projection. Positive
// depth points toward the above-ground viewer; opaque faces paint far to near.
const rad=v=>v*Math.PI/180,EPS=1e-8;
export function cameraCoordinates(p,yaw,elevation=28){
 const a=rad(yaw),e=rad(elevation),side=p.x*Math.cos(a)-p.y*Math.sin(a),along=p.x*Math.sin(a)+p.y*Math.cos(a);
 return {x:side,y:along*Math.sin(e)-p.z*Math.cos(e),depth:along*Math.cos(e)+p.z*Math.sin(e)};
}
export function cameraTowardViewer(yaw,elevation=28){const a=rad(yaw),e=rad(elevation);return{x:Math.sin(a)*Math.cos(e),y:Math.cos(a)*Math.cos(e),z:Math.sin(e)};}
const BOX_FACES=[
 {key:'x-negative',indices:[0,4,7,3],normal:{x:-1,y:0,z:0},shade:30},
 {key:'x-positive',indices:[1,2,6,5],normal:{x:1,y:0,z:0},shade:30},
 {key:'y-negative',indices:[0,1,5,4],normal:{x:0,y:-1,z:0},shade:0},
 {key:'y-positive',indices:[3,7,6,2],normal:{x:0,y:1,z:0},shade:0},
 {key:'top',indices:[4,5,6,7],normal:{x:0,y:0,z:1},shade:0},
 {key:'bottom',indices:[0,3,2,1],normal:{x:0,y:0,z:-1},shade:0},
];
export function visibleBoxFaces(vertices,yaw,elevation=28){
 const v=cameraTowardViewer(yaw,elevation);
 return BOX_FACES.filter(f=>f.normal.x*v.x+f.normal.y*v.y+f.normal.z*v.z>EPS).map(f=>({...f,
  indices:[...f.indices],normal:{...f.normal},depth:f.indices.reduce((s,k)=>s+cameraCoordinates(vertices[k],yaw,elevation).depth,0)/4})).sort((a,b)=>a.depth-b.depth||a.key.localeCompare(b.key));
}
const cross=(a,b,p)=>(b.x-a.x)*(p.y-a.y)-(b.y-a.y)*(p.x-a.x);
export const polygonArea=points=>points.reduce((s,a,i)=>{const b=points[(i+1)%points.length];return s+a.x*b.y-b.x*a.y;},0)/2;
export function overlapPolygon(first,second){
 const sign=Math.sign(polygonArea(second));if(!sign)return[];let output=first.map(p=>({...p}));
 for(let i=0;i<second.length&&output.length;i++){
  const a=second[i],b=second[(i+1)%second.length],input=output;output=[];
  for(let j=0;j<input.length;j++){
   const p=input[j],q=input[(j+1)%input.length],dp=sign*cross(a,b,p),dq=sign*cross(a,b,q),pin=dp>=-EPS,qin=dq>=-EPS;
   if(pin)output.push(p);
   if(pin!==qin){const t=dp/(dp-dq);output.push({x:p.x+(q.x-p.x)*t,y:p.y+(q.y-p.y)*t});}
  }
 }
 return output;
}
export function facetDepthAt(facet,point,yaw,elevation=28){
 const p=facet.screen;
 for(let i=1;i<p.length-1;i++){
  const a=p[0],b=p[i],c=p[i+1],area=cross(a,b,c);if(Math.abs(area)<EPS)continue;
  const u=cross(point,b,c)/area,v=cross(a,point,c)/area,w=1-u-v;
  return u*cameraCoordinates(facet.land[0],yaw,elevation).depth+v*cameraCoordinates(facet.land[i],yaw,elevation).depth+w*cameraCoordinates(facet.land[i+1],yaw,elevation).depth;
 }
 return null; // Edge-on polygons have no opaque interior to order.
}
export function orderTerrainFacets(facets,yaw,elevation=28){
 const visible=facets.filter(f=>f.land.length>=3),edges=visible.map(()=>new Set()),incoming=visible.map(()=>0);
 const depth=f=>f.land.reduce((s,p)=>s+cameraCoordinates(p,yaw,elevation).depth,0)/f.land.length;
 for(let i=0;i<visible.length;i++)for(let j=i+1;j<visible.length;j++){
  const a=visible[i],b=visible[j],overlap=overlapPolygon(a.screen,b.screen);
  if(overlap.length<3||Math.abs(polygonArea(overlap))<1e-5)continue;
  const deltas=overlap.map(p=>{const x=facetDepthAt(a,p,yaw,elevation),y=facetDepthAt(b,p,yaw,elevation);return x===null||y===null?0:x-y;});
  const positive=deltas.some(d=>d>EPS),negative=deltas.some(d=>d<-EPS);
  if(positive&&negative)throw RangeError('TERRAIN_DEPTH_CROSSING: intersecting opaque facets need explicit splitting');
  const far=positive?j:negative?i:null,near=positive?i:j;
  if(far!==null&&!edges[far].has(near)){edges[far].add(near);incoming[near]++;}
 }
 const ready=visible.map((f,i)=>i).filter(i=>incoming[i]===0),result=[],compare=(i,j)=>depth(visible[i])-depth(visible[j])||visible[i].index-visible[j].index;
 while(ready.length){ready.sort(compare);const i=ready.shift();result.push(visible[i]);for(const j of edges[i])if(--incoming[j]===0)ready.push(j);}
 if(result.length!==visible.length)throw RangeError('TERRAIN_DEPTH_CYCLE: unresolved opaque ordering');
 return result;
}
